import struct
from opkv import bootimg


def _boot(kernel: bytes, ver=4):
    h = bytearray(4096)
    h[:8] = b"ANDROID!"
    struct.pack_into("<I", h, 8, len(kernel))
    struct.pack_into("<I", h, 40, ver)
    return bytes(h) + kernel


def _header(ksize=777, page=2048, ver=2):
    h = bytearray(4096)
    h[:8] = b"ANDROID!"
    struct.pack_into("<I", h, 8, ksize)
    struct.pack_into("<I", h, 36, page)
    struct.pack_into("<I", h, 40, ver)
    return bytes(h)


def test_span_v4():
    assert bootimg.kernel_span(_boot(b"x" * 100)[:4096]) == (4096, 100)


def test_span_v0_to_v2_reads_the_page_size_from_the_header():
    assert [bootimg.kernel_span(_header(ver=v)) for v in (0, 1, 2)] == [(2048, 777)] * 3


def test_span_v3_and_later_use_a_4096_page_whatever_the_header_says():
    assert [bootimg.kernel_span(_header(ver=v)) for v in (3, 4, 15)] == [(4096, 777)] * 3


def test_span_of_an_unknown_header_version_is_none():
    assert bootimg.kernel_span(_header(ver=16)) is None and bootimg.kernel_span(_header(ver=0xFFFFFFFF)) is None


def test_span_of_something_that_is_not_a_boot_image_is_none():
    assert bootimg.kernel_span(b"NOTABOOT" + bytes(4096)) is None
    assert bootimg.kernel_span(b"") is None


def test_span_of_a_truncated_header_is_none():
    assert bootimg.kernel_span(b"ANDROID!" + bytes(10)) is None


def test_boot_image_names_are_picked_without_vendor_or_init_boot():
    assert bootimg.pick_boot_name(["boot.img"]) == "boot.img"
    assert bootimg.pick_boot_name([]) is None


def test_lz4_frame_kernel():
    import lz4.frame
    k = lz4.frame.compress(b"\0" * 64 + b"Linux version 6.1.2-x (a@b) (c) #1 SMP Tue\n")
    assert "6.1.2-x" in bootimg.find_linux_version(_boot(k))


def test_gzip_stream_after_an_uncompressed_head():
    import gzip
    k = b"\0" * 100 + gzip.compress(b"\0" * 64 + b"Linux version 6.1.3-y (a@b) (c) #1 SMP Tue\n")
    assert "6.1.3-y" in bootimg.find_linux_version(_boot(k))


def test_legacy_lz4_kernel_with_several_blocks():
    import lz4.block
    blocks = [lz4.block.compress(b"\0" * 5000, store_size=False),
              lz4.block.compress(b"\0" * 10 + b"Linux version 5.10.9-z (a@b) (c) #1 SMP Tue\n", store_size=False)]
    k = b"\x02\x21\x4c\x18" + b"".join(struct.pack("<I", len(b)) + b for b in blocks)
    assert "5.10.9-z" in bootimg.find_linux_version(_boot(k))


def test_corrupt_compressed_kernel_is_not_fatal():
    k = b"\x1f\x8b\x08" + b"garbage" * 10 + b"\0Linux version 5.4.1-raw (a@b) (c) #1 SMP Tue\n"
    assert "5.4.1-raw" in bootimg.find_linux_version(_boot(k))


def test_truncated_banner_is_returned_when_nothing_better_exists():
    got = bootimg.find_linux_version(_boot(b"\0Linux version 6.12.58-x (kleaf@build-host) (A<\0"))
    assert got == "Linux version 6.12.58-x (kleaf@build-host) (A<"


def test_no_banner_means_none():
    assert bootimg.find_linux_version(_boot(b"\0" * 500)) is None


def test_raw_kernel_without_a_boot_header_is_searched_whole():
    assert "5.15.1" in bootimg.find_linux_version(b"\0" * 10 + b"Linux version 5.15.1-x (a@b) (c) #1 SMP Mon\n")


def test_raw_banner():
    k = b"\0" * 10 + b"Linux version 5.15.1-android13 (a@b) (clang) #1 SMP Mon Jan 1 UTC 2024\n" + b"\0"
    assert bootimg.find_linux_version(_boot(k)).startswith("Linux version 5.15.1-android13")


def test_gzip_banner():
    import gzip
    k = gzip.compress(b"\0" * 64 + b"Linux version 6.1.2-x (a@b) (c) #1 SMP Tue\n")
    assert "6.1.2-x" in bootimg.find_linux_version(_boot(k))


def test_prefers_complete_banner_over_truncated_raw_match():
    import lz4.block, struct
    banner = b"Linux version 6.12.69-x (a@b) (clang 19) #1 SMP PREEMPT Wed Jul 15 11:18:49 UTC 2026\n"
    comp = lz4.block.compress(b"\0" * 32 + banner, store_size=False)
    # legacy lz4 container whose compressed bytes also contain a truncated raw copy of the banner
    k = b"\x02\x21\x4c\x18" + struct.pack("<I", len(comp)) + comp
    k += b"junk Linux version 6.12.58-x (kleaf@build-host) (A<\x00\xf0"
    assert bootimg.find_linux_version(_boot(k)).endswith("2026")


def test_android_from_metadata():
    from opkv.extract import android_from_metadata as f
    assert f("post-build=OnePlus/CPH2653EEA/OP5D55L1:16/BP2A.250605.015/V.R4T3:user/release-keys\npost-sdk-level=36") == "16"
    assert f("post-build=OnePlus/PLK110/OP60FFL1:17/CP2A.260605.016/B.3bd:user/release-keys") == "17"
    assert f("post-sdk-level=33") == "13"
    assert f("nothing=here") is None
