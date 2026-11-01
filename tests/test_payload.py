import bz2
import lzma
import struct

import pytest
import zstandard
from builders import boot_image, payload as build_payload

from opkv import payload


def read(http_server, data, **kw):
    http_server.files["/payload.bin"] = data
    return payload.read_header_and_manifest(http_server.url("/payload.bin"), 0)


def test_manifest_lists_partitions_with_their_operations(http_server):
    hdr, man = read(http_server, build_payload({"boot": b"b" * 10_000, "init_boot": b"i" * 100}, chunk=4096))
    assert hdr.version == 2 and man.block_size == 4096
    assert sorted(man.partitions) == ["boot", "init_boot"]
    ops = man.partitions["boot"].ops
    assert [op.type for op in ops] == [8, 8, 8]
    assert ops[1].data_offset == ops[0].data_length                      # blobs are laid out one after the other
    assert hdr.blob_offset == 24 + hdr.manifest_size + hdr.sig_size


def test_bad_magic_is_reported(http_server):
    with pytest.raises(ValueError, match="bad payload magic"):
        read(http_server, b"NOPE" + bytes(100))


def test_version_1_header_has_no_signature_size(http_server):
    manifest = b"\x18\x80\x20"                                      # field 3 (block_size) = 4096
    hdr, man = read(http_server, b"CrAU" + struct.pack(">QQ", 1, len(manifest)) + manifest + bytes(16))
    assert (hdr.version, hdr.sig_size, hdr.blob_offset, man.block_size) == (1, 0, 20 + len(manifest), 4096)


@pytest.mark.parametrize("compress", [lzma.compress, bz2.compress, zstandard.ZstdCompressor().compress])
def test_replace_operations_are_decoded_whatever_their_compression(compress):
    op = payload.Op(8)
    assert payload.decode_op(op, compress(b"kernel" * 100), 4096) == b"kernel" * 100


def test_raw_replace_operation_is_returned_as_is():
    assert payload.decode_op(payload.Op(0), b"raw", 4096) == b"raw"


def test_delta_operation_needs_a_source_image():
    with pytest.raises(NotImplementedError, match="op type 3"):
        payload.decode_op(payload.Op(3), b"\x00\x01", 4096)


def partition(http_server, data, **kw):
    hdr, man = read(http_server, build_payload({"boot": data}, **kw))
    return hdr, man


def test_partition_is_streamed_in_order(http_server):
    data = boot_image(noise=30_000)
    hdr, man = partition(http_server, data, chunk=4096)
    assert b"".join(payload.stream_partition(http_server.url("/payload.bin"), hdr, man, "boot")) == data


def test_contiguous_operations_are_fetched_with_one_request(http_server):
    data = boot_image(noise=30_000)
    hdr, man = partition(http_server, data, chunk=4096)
    before = len(http_server.requests)
    b"".join(payload.stream_partition(http_server.url("/payload.bin"), hdr, man, "boot"))
    assert len(http_server.requests) - before == 1


def test_zero_operation_yields_blocks_of_zeros():
    man = payload.Manifest(4096, {"boot": payload.Partition("boot", [payload.Op(6, dst_blocks=2)])})
    assert list(payload.stream_partition("http://unused.invalid/", None, man, "boot")) == [bytes(8192)]


def test_incremental_ota_is_refused(http_server):
    hdr, man = partition(http_server, b"x" * 100, op_type=4)
    with pytest.raises(NotImplementedError, match="incremental OTA"):
        list(payload.stream_partition(http_server.url("/payload.bin"), hdr, man, "boot"))


def test_prefix_stops_at_the_length_the_header_asks_for(http_server):
    data = boot_image(noise=30_000)
    hdr, man = partition(http_server, data + b"tail" * 5000, chunk=4096)
    got = payload.read_partition_prefix(http_server.url("/payload.bin"), hdr, man, "boot", lambda head: len(data))
    assert got == data


def test_header_is_inspected_once_not_after_every_chunk(monkeypatch):
    chunks = [b"A" * 4096] + [b"B" * 4096] * 50
    asked = []

    def need(head):
        asked.append(len(head))
        return 4096 * 10

    monkeypatch.setattr(payload, "stream_partition", lambda *a: iter(chunks))
    assert payload.read_partition_prefix("u", None, None, "boot", need) == b"".join(chunks[:10])
    assert asked == [4096]


def test_header_is_not_asked_before_4096_bytes_are_in(monkeypatch):
    asked = []
    monkeypatch.setattr(payload, "stream_partition", lambda *a: iter([b"a" * 100, b"b" * 5000, b"c" * 10]))
    got = payload.read_partition_prefix("u", None, None, "boot", lambda head: asked.append(len(head)) or None)
    assert asked == [4096] and got == b"a" * 100 + b"b" * 5000 + b"c" * 10      # no target: the whole partition
