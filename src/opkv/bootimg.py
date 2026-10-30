"""Android boot.img header parsing + 'Linux version' extraction."""
from __future__ import annotations

import re
import struct
import zlib

import lz4.block
import lz4.frame

BOOT_MAGIC = b"ANDROID!"
BANNER_RE = re.compile(rb"Linux version \d+\.\d+[\x20-\x7e]{10,1200}")


def kernel_span(buf: bytes) -> tuple[int, int] | None:
    """(offset, size) of kernel inside boot.img from the first >=4096 bytes."""
    if buf[:8] != BOOT_MAGIC:
        return None
    ksize = struct.unpack_from("<I", buf, 8)[0]
    ver = struct.unpack_from("<I", buf, 40)[0] if len(buf) >= 44 else 0
    if ver >= 3 and ver < 16:           # v3/v4: fixed 4096 page
        page = 4096
    else:                                # v0-v2: page_size @36 (header_version @40)
        page = struct.unpack_from("<I", buf, 36)[0]
        if ver > 4:
            return None
    return page, ksize


def _lz4_legacy(data: bytes) -> bytes:
    out, i = [], 4
    while i + 4 <= len(data):
        n = struct.unpack_from("<I", data, i)[0]; i += 4
        if n == 0 or i + n > len(data):
            break
        out.append(lz4.block.decompress(data[i:i + n], uncompressed_size=8 << 20)); i += n
    return b"".join(out)


def decompress_kernel(k: bytes) -> list[bytes]:
    """Candidate decompressed payloads of a (possibly compressed) kernel blob."""
    outs = []
    if k[:2] == b"\x1f\x8b":
        try: outs.append(zlib.decompressobj(31).decompress(k))
        except zlib.error: pass
    if k[:4] == b"\x02\x21\x4c\x18":
        try: outs.append(_lz4_legacy(k))
        except Exception: pass
    if k[:4] == b"\x04\x22\x4d\x18":
        try: outs.append(lz4.frame.decompress(k))
        except Exception: pass
    # embedded gzip stream (e.g. Image with appended .gz / vmlinuz-like)
    i = k.find(b"\x1f\x8b\x08")
    if i > 0:
        try: outs.append(zlib.decompressobj(31).decompress(k[i:]))
        except zlib.error: pass
    return outs


def find_linux_version(boot: bytes) -> str | None:
    span = kernel_span(boot[:4096])
    kernel = boot[span[0]: span[0] + span[1]] if span else boot
    for blob in [kernel, *decompress_kernel(kernel)]:
        # banner appears multiple times (e.g. proc_banner fmt string "%s version %s"); take full one
        for m in BANNER_RE.finditer(blob):
            s = m.group().decode("ascii", "replace").strip()
            if "(" in s and "#" in s:
                return s
        m = BANNER_RE.search(blob)
        if m:
            return m.group().decode("ascii", "replace").strip()
    return None
