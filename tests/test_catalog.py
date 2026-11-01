import io
import json
import urllib.request

import pytest

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


@pytest.mark.parametrize("device,wanted", [
    ("OP 13", True), ("OP 10 PRO", True), ("OP 12R", True), ("OP OPEN", True), ("OP PAD 2", True), ("OP NORD 4", True),
    ("OP NORD 2T", True), ("OP NORD CE 2 LITE", True), ("OP ACE 5", True), ("OP N6", True),
    ("OP 9", False), ("OP 9 PRO", False), ("OP 8T", False), ("OP 7", False), ("OP ONE", False), ("OP X", False),
    ("OP NORD", False), ("OP NORD 2", False), ("OP NORD CE", False), ("OP NORD N10", False), ("OP NORD N100", False),
    ("OPPO FIND X9", False), ("REALME GT 7", False), ("XIAOMI 15", False), ("", False)])
def test_only_oneplus_10_series_and_newer_are_wanted(device, wanted):
    assert catalog.is_oneplus({"device": device}) is wanted


def test_load_reads_a_file_with_or_without_the_releases_wrapper(tmp_path):
    wrapped = tmp_path / "a.json"
    wrapped.write_text(json.dumps({"releases": [{"id": "1"}]}))
    bare = tmp_path / "b.json"
    bare.write_text(json.dumps([{"id": "2"}]))
    assert catalog.load(str(wrapped)) == [{"id": "1"}] and catalog.load(str(bare)) == [{"id": "2"}]


def test_load_reads_a_url(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout=0: io.BytesIO(b'{"releases": [{"id": "3"}]}'))
    assert catalog.load("https://example.invalid/catalog.json") == [{"id": "3"}]


def test_releases_without_a_download_link_or_older_than_android_14_are_not_listed(tmp_path):
    gone = {**_release("gone"), "source_url": ""}
    old = _release("old", version="CPH2449_13.1.0.500(EX01)")
    other = {**_release("other"), "device": "Xiaomi 15"}
    assert catalog.oneplus_releases(_catalog(tmp_path, gone, old, other, _release("ok"))) == [_release("ok")]
