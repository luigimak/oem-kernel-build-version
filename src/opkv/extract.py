"""url (OTA zip) -> Linux version, reading only the needed bytes."""
from __future__ import annotations

import re
import struct
import zipfile
from dataclasses import dataclass, asdict

from . import bootimg, payload
from . import resolver
from .rangehttp import RangeFile
from .safe import redact


@dataclass
class Result:
    ok: bool = False
    linux_version: str | None = None
    kernel_release: str | None = None   # e.g. 5.10.66-android12-9-gac8d8aa8630a-ab8773791
    build: str | None = None            # e.g. #1 SMP PREEMPT Mon Jun 27 16:41:59 UTC 2022
    compiler: str | None = None         # e.g. Android (...) clang version 12.0.5 ..., LLD 12.0.5
    source: str | None = None       # "payload.bin" | "boot.img"
    bytes_fetched: int = 0
    requests: int = 0
    error: str | None = None

    def dict(self): return asdict(self)


def _boot_need(buf: bytes) -> int | None:
    sp = bootimg.kernel_span(buf)
    return None if sp is None else sp[0] + sp[1]


def _data_offset(rf: RangeFile, zi: zipfile.ZipInfo) -> int:
    rf.seek(zi.header_offset)
    h = rf.read(30)
    n, m = struct.unpack("<HH", h[26:30])
    return zi.header_offset + 30 + n + m


def extract(url: str) -> Result:
    res = Result()   # the URL is never stored in the result
    try:
        url = resolver.resolve(url)
        rf = RangeFile(url)
        zf = zipfile.ZipFile(rf)
        names = {i.filename: i for i in zf.infolist()}
        if "payload.bin" in names:
            zi = names["payload.bin"]
            if zi.compress_type != zipfile.ZIP_STORED:
                raise ValueError("payload.bin is compressed in zip")
            off = _data_offset(rf, zi)
            hdr, man = payload.read_header_and_manifest(url, off)
            pname = next((n for n in ("boot", "boot_a") if n in man.partitions), None)
            if not pname:
                raise ValueError(f"no boot partition: {sorted(man.partitions)[:8]}...")
            boot = payload.read_partition_prefix(url, hdr, man, pname, _boot_need)
            res.source = "payload.bin"
        else:
            cand = [n for n in names if n.endswith("boot.img") and "vendor_boot" not in n and "init_boot" not in n]
            if not cand:
                raise ValueError("neither payload.bin nor boot.img in zip")
            zi = names[sorted(cand, key=len)[0]]
            res.source = "boot.img"
            with zf.open(zi) as f:
                head = f.read(4096)
                sp = bootimg.kernel_span(head)
                need = (sp[0] + sp[1]) if sp else zi.file_size
                boot = head + f.read(max(0, need - len(head)))
        ver = bootimg.find_linux_version(boot)
        if not ver:
            raise ValueError("Linux version string not found")
        res.linux_version = ver
        m = re.match(r"Linux version (\S+)", ver)
        res.kernel_release = m.group(1) if m else None
        b = re.search(r"(#\d+ .*)$", ver)
        res.build = b.group(1).strip() if b else None
        c = re.search(r"\((?:[^()]*@[^()]*)\) \((.*)\) #\d+ ", ver)
        res.compiler = c.group(1) if c else None
        res.ok = True
        res.bytes_fetched, res.requests = rf.bytes_fetched, rf.requests
    except Exception as e:  # noqa: BLE001 - report per-URL, keep batch going
        res.error = redact(f"{type(e).__name__}: {e}")
    return res
