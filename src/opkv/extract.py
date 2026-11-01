"""url (OTA zip) -> Linux version, reading only the needed bytes."""
from __future__ import annotations

import re
import struct
import zipfile
from dataclasses import dataclass, asdict

from . import bootimg, payload, rangehttp, resolver
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
    android_version: str | None = None  # e.g. 16 (from META-INF/com/android/metadata)
    size: int | None = None         # package size in bytes (Content-Range of the remote file)
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


_SDK_TO_ANDROID = {30: "11", 31: "12", 32: "12", 33: "13", 34: "14", 35: "15", 36: "16", 37: "17"}


def android_from_metadata(text: str) -> str | None:
    """Android release from an OTA metadata file: post-build release, else post-sdk-level."""
    kv = dict(l.split("=", 1) for l in text.splitlines() if "=" in l)
    m = re.search(r":(\d+(?:\.\d+)?)/", kv.get("post-build", ""))
    if m:
        return m.group(1)
    try:
        return _SDK_TO_ANDROID.get(int(kv.get("post-sdk-level", "")))
    except ValueError:
        return None


def _android(zf: zipfile.ZipFile) -> str | None:
    try:
        return android_from_metadata(zf.read("META-INF/com/android/metadata").decode("utf-8", "replace"))
    except KeyError:
        return None


def extract_android(url: str) -> Result:
    """Cheap pass: read only the OTA metadata (a few KB) to get the Android version."""
    res = Result()
    rangehttp.reset_traffic()
    try:
        rf = RangeFile(resolver.resolve(url))
        res.size = rf.size
        zf = zipfile.ZipFile(rf)
        res.android_version = _android(zf)
        res.ok = res.android_version is not None
        if not res.ok:
            res.error = "no Android version in OTA metadata"
    except Exception as e:  # noqa: BLE001
        res.error = redact(f"{type(e).__name__}: {e}")
    res.requests, res.bytes_fetched = rangehttp.traffic()
    return res


def fill_banner(res: Result, boot: bytes) -> None:
    """Parse the Linux version banner of a (possibly truncated) boot.img into res."""
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


def extract(url: str) -> Result:
    res = Result()   # the URL is never stored in the result
    rangehttp.reset_traffic()
    try:
        url = resolver.resolve(url)
        rf = RangeFile(url)
        res.size = rf.size
        zf = zipfile.ZipFile(rf)
        names = {i.filename: i for i in zf.infolist()}
        res.android_version = _android(zf)
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
            name = bootimg.pick_boot_name(names)
            if not name:
                raise ValueError("neither payload.bin nor boot.img in zip")
            zi = names[name]
            res.source = "boot.img"
            with zf.open(zi) as f:
                head = f.read(4096)
                sp = bootimg.kernel_span(head)
                need = (sp[0] + sp[1]) if sp else zi.file_size
                boot = head + f.read(max(0, need - len(head)))
        fill_banner(res, boot)
        res.ok = True
    except Exception as e:  # noqa: BLE001 - report per-URL, keep batch going
        res.error = redact(f"{type(e).__name__}: {e}")
    res.requests, res.bytes_fetched = rangehttp.traffic()
    return res
