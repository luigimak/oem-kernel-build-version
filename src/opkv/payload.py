"""Minimal Android payload.bin (CrAU) reader: manifest + partial partition extraction.

Protobuf is decoded by hand (only the fields we need) to avoid protoc/protobuf deps.
"""
from __future__ import annotations

import bz2
import lzma
import struct
from collections import deque
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

import zstandard

from .rangehttp import add_traffic, fetch_range, reset_traffic, traffic

MAGIC = b"CrAU"


# --- protobuf wire decoding -------------------------------------------------
def _varint(b: bytes, i: int) -> tuple[int, int]:
    r = s = 0
    while True:
        c = b[i]; i += 1
        r |= (c & 0x7F) << s
        if not c & 0x80:
            return r, i
        s += 7


def _fields(b: bytes) -> Iterator[tuple[int, int, Any]]:
    i = 0
    while i < len(b):
        tag, i = _varint(b, i)
        fn, wt = tag >> 3, tag & 7
        v: Any
        if wt == 0:
            v, i = _varint(b, i)
        elif wt == 2:
            ln, i = _varint(b, i)
            v = b[i:i + ln]; i += ln
        elif wt == 1:
            v = b[i:i + 8]; i += 8
        elif wt == 5:
            v = b[i:i + 4]; i += 4
        else:
            raise ValueError(f"unsupported wire type {wt}")
        yield fn, wt, v


@dataclass
class Op:
    type: int
    data_offset: int = 0
    data_length: int = 0
    dst_blocks: int = 0


@dataclass
class Partition:
    name: str
    ops: list[Op] = field(default_factory=list)


@dataclass
class Manifest:
    block_size: int
    partitions: dict[str, Partition]


def parse_manifest(raw: bytes) -> Manifest:
    block_size = 4096
    parts: dict[str, Partition] = {}
    for fn, _, v in _fields(raw):
        if fn == 3:
            block_size = v
        elif fn == 13:
            p = Partition("")
            for pf, _, pv in _fields(v):
                if pf == 1:
                    p.name = pv.decode()
                elif pf == 8:
                    op = Op(0)
                    for of, _, ov in _fields(pv):
                        if of == 1: op.type = ov
                        elif of == 2: op.data_offset = ov
                        elif of == 3: op.data_length = ov
                        elif of == 6:
                            nb = 0
                            for ef, _, ev in _fields(ov):
                                if ef == 2: nb = ev
                            op.dst_blocks += nb
                    p.ops.append(op)
            parts[p.name] = p
    return Manifest(block_size, parts)


@dataclass
class Header:
    version: int
    manifest_size: int
    sig_size: int
    blob_offset: int  # absolute offset (in the remote file) of the data blobs


def read_header_and_manifest(url: str, payload_off: int) -> tuple[Header, Manifest]:
    h = fetch_range(url, payload_off, payload_off + 23)
    if h[:4] != MAGIC:
        raise ValueError(f"bad payload magic {h[:4]!r}")
    version, msize = struct.unpack(">QQ", h[4:20])
    sig = struct.unpack(">I", h[20:24])[0] if version >= 2 else 0
    hdr_len = 24 if version >= 2 else 20
    start = payload_off + hdr_len
    manifest = parse_manifest(fetch_range(url, start, start + msize - 1))
    return Header(version, msize, sig, start + msize + sig), manifest


# --- operation decoding -----------------------------------------------------
def decode_op(op: Op, data: bytes, block_size: int) -> bytes:
    """Decode a REPLACE-family op. Compression sniffed from magic (robust to type ids)."""
    if data[:6] == b"\xfd7zXZ\x00":
        out = lzma.LZMADecompressor().decompress(data)
    elif data[:3] == b"BZh":
        out = bz2.BZ2Decompressor().decompress(data)
    elif data[:4] == b"\x28\xb5\x2f\xfd":
        out = zstandard.ZstdDecompressor().decompressobj().decompress(data)
    elif op.type in (0, 1, 8, 14, 15):
        out = data  # REPLACE (raw)
    else:
        raise NotImplementedError(f"op type {op.type} (delta/copy) needs source image")
    return out


def _plan(part_ops: list[Op], blob_offset: int, name: str, cap: int) -> Iterator[tuple]:
    """The reads a partition needs, in order: ("zero", bytes) or ("blob", start, length, ops). Contiguous blob ops are
    coalesced up to `cap` bytes. An op that needs a source image ends the plan with ("error", exception)."""
    ops = part_ops
    i = 0
    while i < len(ops):
        op = ops[i]
        if op.type in (6, 7):  # ZERO / DISCARD
            yield ("zero", op.dst_blocks)
            i += 1
            continue
        if op.type in (2, 3, 4, 5, 9, 10, 11, 12, 13):
            yield ("error", NotImplementedError(f"incremental OTA (op type {op.type}) in {name}"))
            return
        j = i
        total = op.data_length
        while (j + 1 < len(ops) and ops[j + 1].type not in (6, 7)
               and ops[j + 1].data_offset == ops[j].data_offset + ops[j].data_length
               and total + ops[j + 1].data_length <= cap):
            j += 1
            total += ops[j].data_length
        yield ("blob", blob_offset + op.data_offset, total, ops[i:j + 1])
        i = j + 1


def _fetch_counted(url: str, start: int, end: int) -> tuple[bytes, tuple[int, int]]:
    """fetch_range on a helper thread: the data and the traffic it took, for the thread that asked."""
    reset_traffic()
    return fetch_range(url, start, end), traffic()


def stream_partition(url: str, hdr: Header, man: Manifest, name: str, parallel: int = 1) -> Iterator[bytes]:
    """Yield decoded partition bytes in order (full OTA only). With `parallel` > 1 the next blocks are already being
    fetched while the current one is decoded (smaller blocks, at most `parallel` of them read ahead and wasted)."""
    bs = man.block_size
    plan = _plan(man.partitions[name].ops, hdr.blob_offset if hdr else 0, name, (4 << 20) if parallel <= 1 else (1 << 20))

    def decode(step: tuple, blob: bytes | None) -> Iterator[bytes]:
        if step[0] == "zero":
            yield b"\0" * (step[1] * bs)
            return
        pos = 0
        for o in step[3]:
            yield decode_op(o, (blob or b"")[pos:pos + o.data_length], bs)
            pos += o.data_length

    if parallel <= 1:
        for step in plan:
            if step[0] == "error":
                raise step[1]
            yield from decode(step, fetch_range(url, step[1], step[1] + step[2] - 1) if step[0] == "blob" else None)
        return
    ex = ThreadPoolExecutor(parallel)
    try:
        ahead: deque = deque()

        def refill() -> None:
            while len(ahead) < parallel and (step := next(plan, None)) is not None:
                fut = ex.submit(_fetch_counted, url, step[1], step[1] + step[2] - 1) if step[0] == "blob" else None
                ahead.append((step, fut))

        refill()
        while ahead:
            step, fut = ahead.popleft()
            if step[0] == "error":
                raise step[1]
            blob = None
            if fut is not None:
                blob, (nreq, nbytes) = fut.result()
                add_traffic(nreq, nbytes)
            refill()
            yield from decode(step, blob)
    finally:
        ex.shutdown(wait=False, cancel_futures=True)


def read_partition_prefix(url: str, hdr: Header, man: Manifest, name: str,
                          need: Callable[[bytes], int | None], parallel: int = 1) -> bytes:
    """Stream the partition until as many bytes as need() asks for are in. need() sees the first 4096 bytes
    (the header), once; when it gives no target the whole partition is returned."""
    buf = bytearray()
    tgt, asked = None, False
    for chunk in stream_partition(url, hdr, man, name, parallel):
        buf += chunk
        if not asked and len(buf) >= 4096:
            asked, tgt = True, need(bytes(buf[:4096]))
        if tgt is not None and len(buf) >= tgt:
            return bytes(buf[:tgt])
    return bytes(buf)
