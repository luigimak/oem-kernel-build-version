import concurrent.futures
import zipfile

import pytest
from builders import boot_image, ota_zip, payload, zip_bytes
from helpers import BANNER

from opkv import extract

KERNEL = "6.6.89-android15-8-gabc123"


def test_extracts_the_kernel_banner_from_a_full_ota(http_server):
    http_server.files["/ota.zip"] = ota_zip()
    res = extract.extract(http_server.url("/ota.zip"))
    assert res.ok, res.error
    assert res.source == "payload.bin"
    assert res.linux_version == BANNER
    assert res.kernel_release == KERNEL
    assert res.build == "#1 SMP PREEMPT Mon Jun 2 10:00:00 UTC 2025"
    assert res.compiler == "Android clang version 18.0.0, LLD 18.0.0"
    assert res.android_version == "16"
    assert res.size == len(http_server.files["/ota.zip"])


def test_reported_traffic_is_what_the_server_sent(http_server):
    http_server.files["/ota.zip"] = ota_zip(boot_image(noise=50_000), chunk=8192)    # several payload operations
    res = extract.extract(http_server.url("/ota.zip"))
    assert res.ok, res.error
    assert res.requests == len([r for r in http_server.requests if r[0] == "GET"])
    assert res.bytes_fetched == http_server.sent["/ota.zip"] > 50_000


def test_traffic_is_counted_per_extraction_when_they_run_in_parallel(http_server):
    http_server.files["/a.zip"] = ota_zip(boot_image(noise=20_000), chunk=4096)
    http_server.files["/b.zip"] = ota_zip(boot_image(noise=90_000), chunk=16384)
    urls = [http_server.url("/a.zip"), http_server.url("/b.zip")]
    with concurrent.futures.ThreadPoolExecutor(2) as ex:
        a, b = ex.map(extract.extract, urls)
    assert (a.bytes_fetched, b.bytes_fetched) == (http_server.sent["/a.zip"], http_server.sent["/b.zip"])


def test_failed_extraction_still_reports_the_traffic_spent(http_server):
    http_server.files["/ota.zip"] = ota_zip(op_type=4)           # SOURCE_COPY: needs the previous build
    res = extract.extract(http_server.url("/ota.zip"))
    assert not res.ok and "incremental OTA" in res.error
    assert res.requests > 0 and res.bytes_fetched == http_server.sent["/ota.zip"]


def test_payload_compressed_inside_the_zip_is_reported(http_server):
    http_server.files["/ota.zip"] = zip_bytes({"payload.bin": payload({"boot": boot_image()})}, zipfile.ZIP_DEFLATED)
    assert "payload.bin is compressed in zip" in extract.extract(http_server.url("/ota.zip")).error


def test_ota_without_boot_partition_is_reported(http_server):
    http_server.files["/ota.zip"] = zip_bytes({"payload.bin": payload({"system": b"x" * 100})})
    assert "no boot partition" in extract.extract(http_server.url("/ota.zip")).error


def test_zip_with_neither_payload_nor_boot_image_is_reported(http_server):
    http_server.files["/ota.zip"] = zip_bytes({"readme.txt": b"hi"})
    assert "neither payload.bin nor boot.img in zip" in extract.extract(http_server.url("/ota.zip")).error


@pytest.mark.parametrize("compression", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
def test_zip_with_a_plain_boot_image_is_read(http_server, compression):
    members = {"vendor_boot.img": boot_image(BANNER.replace("6.6.89", "5.4.1")), "boot.img": boot_image()}
    http_server.files["/ota.zip"] = zip_bytes(members, compression)
    res = extract.extract(http_server.url("/ota.zip"))
    assert res.ok, res.error
    assert (res.source, res.kernel_release) == ("boot.img", KERNEL)


def test_missing_ota_metadata_leaves_the_android_version_empty(http_server):
    http_server.files["/ota.zip"] = ota_zip(metadata=None)
    res = extract.extract(http_server.url("/ota.zip"))
    assert res.ok and res.android_version is None


def test_unreachable_package_is_reported_without_its_url(http_server):
    res = extract.extract(http_server.url("/gone.zip?Signature=SECRET"))
    assert not res.ok and "404" in res.error and "SECRET" not in res.error


def test_server_without_range_support_is_reported(http_server):
    http_server.files["/ota.zip"] = ota_zip()
    http_server.ignore_range = True
    res = extract.extract(http_server.url("/ota.zip"))
    assert not res.ok and "Content-Range" in res.error


def test_android_version_pass_does_not_read_the_payload(http_server):
    http_server.files["/ota.zip"] = ota_zip(boot_image(noise=400_000))
    res = extract.extract_android(http_server.url("/ota.zip"))
    assert res.ok and res.android_version == "16"
    assert res.size == len(http_server.files["/ota.zip"])
    assert res.bytes_fetched < 100_000 < len(http_server.files["/ota.zip"])


def test_android_version_pass_reports_a_package_without_metadata(http_server):
    http_server.files["/ota.zip"] = ota_zip(metadata=None)
    res = extract.extract_android(http_server.url("/ota.zip"))
    assert not res.ok and res.error == "no Android version in OTA metadata"


def test_android_version_from_the_sdk_level_when_post_build_has_no_release():
    assert extract.android_from_metadata("post-sdk-level=34") == "14"
    assert extract.android_from_metadata("post-sdk-level=junk") is None
