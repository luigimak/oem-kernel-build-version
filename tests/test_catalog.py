import json

from opkv import catalog
from opkv.catalog import os_major, wanted_version


def _release(rid, version="CPH2645_15.0.0.840(EX01)", region="EU"):
    return {"id": rid, "device": "OP 13R", "region": region, "model": version.split("_")[0], "version": version,
            "ota_version": "CPH2645_11.C.60_1600_202507081931", "source_url": "https://example.invalid/ota.zip"}


def _catalog(tmp_path, *releases):
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({"api_version": "1", "releases": list(releases)}))
    return str(path)


def test_same_firmware_under_two_ids_is_listed_once(tmp_path):
    src = _catalog(tmp_path, _release("aaa"), _release("bbb"))
    assert [r["id"] for r in catalog.oneplus_releases(src)] == ["aaa"]


def test_same_version_in_another_region_is_a_different_firmware(tmp_path):
    src = _catalog(tmp_path, _release("aaa", region="EU"), _release("bbb", region="GLO"))
    assert [r["id"] for r in catalog.oneplus_releases(src)] == ["aaa", "bbb"]


def test_catalog_model_typo_does_not_hide_a_duplicate(tmp_path):
    src = _catalog(tmp_path, _release("aaa"), _release("bbb", version="CCPH2645_15.0.0.840(EX01)"))
    assert [r["id"] for r in catalog.oneplus_releases(src)] == ["aaa"]


def test_os_major():
    assert os_major("CPH2653_16.0.10.600(EX01)") == 16
    assert os_major("junk") is None


def test_wanted_version():
    assert wanted_version("CPH2449_13.1.0.500(EX01)") is False
    assert wanted_version("CPH2449_14.0.0.100(EX01)") is True
    assert wanted_version("CPH2449_13.1.0.500(EX01)", "14") is True
    assert wanted_version("junk") is False
