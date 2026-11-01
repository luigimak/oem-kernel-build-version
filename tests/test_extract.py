from builders import boot_image, ota_zip, payload, zip_bytes
from helpers import BANNER

from opkv import extract


def test_extracts_the_kernel_banner_from_a_full_ota(http_server):
    http_server.files["/ota.zip"] = ota_zip()
    res = extract.extract(http_server.url("/ota.zip"))
    assert res.ok, res.error
    assert res.source == "payload.bin"
    assert res.linux_version == BANNER
    assert res.kernel_release == "6.6.89-android15-8-gabc123"
    assert res.build == "#1 SMP PREEMPT Mon Jun 2 10:00:00 UTC 2025"
    assert res.compiler == "Android clang version 18.0.0, LLD 18.0.0"
    assert res.android_version == "16"
    assert res.size == len(http_server.files["/ota.zip"])
