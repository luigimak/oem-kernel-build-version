"""Synthetic firmware: boot image, payload.bin, OTA zip, boot.7z. No real firmware is needed to test the pipeline."""
import io
import lzma
import random
import struct
import zipfile

from helpers import BANNER

METADATA = ("post-build=OnePlus/CPH2653EEA/OP5D55L1:16/BP2A.250605.015/V.R4T3:user/release-keys\n"
            "post-sdk-level=36\n")


def boot_image(banner=BANNER, version=4, noise=0):
    """Android boot image: 4096-byte header + a raw kernel (`noise` incompressible bytes, then the
    strings with the Linux version banner)."""
    kernel = random.Random(0).randbytes(noise) + b"\0" + banner.encode() + b"\n" + b"\0" * 64
    header = bytearray(4096)
    header[:8] = b"ANDROID!"
    struct.pack_into("<I", header, 8, len(kernel))
    struct.pack_into("<I", header, 40, version)
    return bytes(header) + kernel


def _varint(n):
    out = bytearray()
    while True:
        low, n = n & 0x7F, n >> 7
        out.append(low | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _varint_field(num, n):
    return _varint(num << 3) + _varint(n)


def _bytes_field(num, data):
    return _varint(num << 3 | 2) + _varint(len(data)) + data


def payload(partitions, chunk=32 * 1024, op_type=8, block_size=4096):
    """payload.bin (CrAU v2) of full-OTA REPLACE_XZ operations, `chunk` bytes of partition data per operation."""
    blobs, parts = bytearray(), b""
    for name, data in partitions.items():
        ops = b""
        for off in range(0, len(data), chunk):
            blob = lzma.compress(data[off:off + chunk], format=lzma.FORMAT_XZ)
            op = _varint_field(1, op_type) + _varint_field(2, len(blobs)) + _varint_field(3, len(blob))
            ops += _bytes_field(8, op)
            blobs += blob
        parts += _bytes_field(13, _bytes_field(1, name.encode()) + ops)
    manifest = _varint_field(3, block_size) + parts
    return b"CrAU" + struct.pack(">QQI", 2, len(manifest), 0) + manifest + bytes(blobs)


def zip_bytes(files, compression=zipfile.ZIP_STORED):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


def ota_zip(boot=None, metadata=METADATA, **payload_args):
    """A full OTA package: stored payload.bin with a boot partition, plus the OTA metadata file."""
    files = {"payload.bin": payload({"boot": boot or boot_image()}, **payload_args)}
    if metadata is not None:
        files["META-INF/com/android/metadata"] = metadata
    return zip_bytes(files)


def boot_7z(tmp_path, members):
    """A .7z archive (as published in the spike0en archive) holding {name: bytes}."""
    import py7zr
    path = tmp_path / "boot.7z"
    with py7zr.SevenZipFile(path, "w") as z:
        for name, data in members.items():
            z.writestr(data, name)
    return path.read_bytes()
