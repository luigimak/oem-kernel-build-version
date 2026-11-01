"""Android boot.img header parsing + 'Linux version' extraction."""
from __future__ import annotations

import re
import struct
import zlib

import lz4.block
import lz4.frame

BOOT_MAGIC = b"ANDROID!"
BANNER_RE = re.compile(rb"Linux version \d+\.\d+[\x20-\x7e]{10,1200}")
_OTHER_BOOT = ("vendor_boot", "init_boot", "vendor_kernel_boot")      # partitions that carry no kernel


def pick_boot_name(names) -> str | None:
    """The kernel's boot image among the members of an OTA zip or archive: `boot.img`, else the
    shortest other `*boot.img` that is not a vendor/init boot partition."""
    names = list(names)
    plain = [n for n in names if n.rsplit("/", 1)[-1] == "boot.img"]
    other = [n for n in names if n.endswith("boot.img") and not any(x in n for x in _OTHER_BOOT)]
    pool = plain or other
    return min(pool, key=len) if pool else None


def kernel_span(buf: bytes) -> tuple[int, int] | None:
    """(offset, size) of kernel inside boot.img from the first >=4096 bytes."""
    if buf[:8] != BOOT_MAGIC or len(buf) < 44:
        return None
    ksize = struct.unpack_from("<I", buf, 8)[0]
    ver = struct.unpack_from("<I", buf, 40)[0]            # header_version
    if 3 <= ver < 16:                    # v3/v4 (and what follows): fixed 4096-byte page
        page = 4096
    elif ver <= 2:                       # v0-v2: page_size @36
        page = struct.unpack_from("<I", buf, 36)[0]
    else:                                # not a boot image header version
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
    # Decompressed candidates first: in a compressed stream the banner can show up split by
    # literal runs, so a raw match may be truncated. Raw kernel last.
    blobs = [*decompress_kernel(kernel), kernel]
    partial: str | None = None
    for blob in blobs:
        for m in BANNER_RE.finditer(blob):
            s = m.group().decode("ascii", "replace").strip()
            if "(" in s and re.search(r"#\d+ ", s):      # complete banner: release (user@host) (toolchain) #N ...
                return s
            if partial is None or len(s) > len(partial):
                partial = s
    return partial
