import struct
from opkv import bootimg


def _boot(kernel: bytes, ver=4):
    h = bytearray(4096)
    h[:8] = b"ANDROID!"
    struct.pack_into("<I", h, 8, len(kernel))
    struct.pack_into("<I", h, 40, ver)
    return bytes(h) + kernel


def test_span_v4():
    assert bootimg.kernel_span(_boot(b"x" * 100)[:4096]) == (4096, 100)


def test_raw_banner():
    k = b"\0" * 10 + b"Linux version 5.15.1-android13 (a@b) (clang) #1 SMP Mon Jan 1 UTC 2024\n" + b"\0"
    assert bootimg.find_linux_version(_boot(k)).startswith("Linux version 5.15.1-android13")


def test_gzip_banner():
    import gzip
    k = gzip.compress(b"\0" * 64 + b"Linux version 6.1.2-x (a@b) (c) #1 SMP Tue\n")
    assert "6.1.2-x" in bootimg.find_linux_version(_boot(k))
