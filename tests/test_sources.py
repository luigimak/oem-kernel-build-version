import hashlib

import pytest

from opkv import brands, sources


def update(version, ota="CPH2653_11.C.70_1700_202510060039", url="https://example.invalid/x.zip"):
    return {"version_number": version, "ota_version_number": ota, "download_url": url, "md5sum": "m" * 32, "download_size": 123}


@pytest.fixture
def oxygen(monkeypatch):
    """Oxygen Updater API stub: oxygen(devices, methods={device id: [...]}, updates={(device id, method id): {...}})."""
    def install(devices, methods, updates, broken=()):
        def fake_get(url, headers, timeout=40):
            path = url[len(sources.OU_BASE):]
            parts = path.split("/")
            if parts[0] == "devices":
                return devices
            if int(parts[1]) in broken:
                raise OSError("connection reset")
            if parts[0] == "updateMethods":
                return methods[int(parts[1])]
            return updates[(int(parts[1]), int(parts[2]))]

        monkeypatch.setattr(sources, "_get", fake_get)

    return install


FULL = [{"id": 10, "name": "Full update"}, {"id": 11, "name": "Incremental update"}]


def test_latest_full_release_of_each_oneplus_device_is_listed(oxygen):
    oxygen([{"id": 1, "name": "OnePlus 13 (EU)"}, {"id": 2, "name": "OnePlus Nord CE4 Lite (IN)"},
            {"id": 3, "name": "OnePlus 8 (EU)"}, {"id": 4, "name": "Oppo Find X9 (EU)"}],
           {1: FULL, 2: FULL},
           {(1, 10): update("CPH2653_16.0.0.210(EX01)"),
            (2, 10): update("CPH2465_15.0.0.100(EX01)", ota="CPH2465_11.C.10_1000_202501010000")})
    rels = {r["device"]: r for r in sources.ou_releases(brands.BRANDS["oneplus"], workers=1)}
    assert sorted(rels) == ["OP 13", "OP NORD CE 4 LITE"]        # OnePlus 8 is too old, Oppo is not OnePlus
    r = rels["OP 13"]
    key = "|".join(("CPH2653", "CPH2653_11.C.70_1700_202510060039", "EU"))
    assert r["id"] == "ou-" + hashlib.sha1(key.encode()).hexdigest()[:20]
    assert (r["region"], r["model"], r["version"], r["build_timestamp"], r["origin"]) == (
        "EU", "CPH2653", "CPH2653_16.0.0.210(EX01)", "2025-10-06T00:39:00", "oxygen-updater")
    assert (r["md5"], r["size"], r["source_url"]) == ("m" * 32, 123, "https://example.invalid/x.zip")


def test_releases_older_than_android_14_and_without_link_are_skipped(oxygen):
    oxygen([{"id": 1, "name": "OnePlus 12 (EU)"}, {"id": 2, "name": "OnePlus 12R (EU)"}], {1: FULL, 2: FULL},
           {(1, 10): update("CPH2581_13.1.0.500(EX01)"), (2, 10): update("CPH2585_14.0.0.100(EX01)", url=None)})
    assert sources.ou_releases(brands.BRANDS["oneplus"], workers=1) == []


def test_a_device_that_fails_does_not_stop_the_others_and_is_reported(oxygen, capsys):
    oxygen([{"id": 1, "name": "OnePlus 13 (EU)"}, {"id": 2, "name": "OnePlus 12 (EU)"}],
           {1: FULL, 2: FULL}, {(1, 10): update("CPH2653_16.0.0.210(EX01)")}, broken=(2,))
    assert [r["device"] for r in sources.ou_releases(brands.BRANDS["oneplus"], workers=1)] == ["OP 13"]
    err = capsys.readouterr().err
    assert "warning: Oxygen Updater: 1 of 2 devices could not be read" in err and "OP 12 EU: OSError" in err


def test_failures_become_a_workflow_annotation_in_github_actions(oxygen, capsys, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    oxygen([{"id": 1, "name": "OnePlus 13 (EU)"}], {1: FULL}, {}, broken=(1,))
    assert sources.ou_releases(brands.BRANDS["oneplus"], workers=1) == []
    assert "::warning title=Oxygen Updater::Oxygen Updater: 1 of 1 devices could not be read" in capsys.readouterr().out


def test_antirollchecker_index_maps_version_and_region_to_md5(monkeypatch):
    db = {"CPH2653": {"versions": {"CPH2653_16.0.0.210(EX01)": {"md5": "a" * 32, "regions": ["EU", "GLO"]},
                                   "CPH2653_15.0.0.100(EX01)": {"md5": "", "regions": ["EU"]}}},
          "CPH9999": {}}
    monkeypatch.setattr(sources, "_get", lambda url, headers, timeout=40: db)
    assert sources.arb_index() == {("CPH2653_16.0.0.210(EX01)", "EU"): "a" * 32,
                                   ("CPH2653_16.0.0.210(EX01)", "GLO"): "a" * 32}


def test_each_brand_lists_only_its_own_oxygen_updater_devices(oxygen):
    oxygen([{"id": 1, "name": "OnePlus 13 (EU)"}, {"id": 2, "name": "OPPO Find X10 Pro (EU)"},
            {"id": 3, "name": "realme 16 Pro+ (IN)"}, {"id": 4, "name": "realme 8 Pro (IN)"}],
           {1: FULL, 2: FULL, 3: FULL, 4: FULL},
           {(1, 10): update("CPH2653_16.0.0.210(EX01)"), (2, 10): update("CPH2700_16.0.0.100(EX01)"),
            (3, 10): update("RMX5200_16.0.0.100(EX01)"), (4, 10): update("RMX3081_11.0.0.100(EX01)")})
    found = {key: [(r["device"], r["region"]) for r in sources.ou_releases(brands.BRANDS[key], workers=1)]
             for key in brands.BRANDS}
    assert found == {"oneplus": [("OP 13", "EU")], "oppo": [("OPPO FIND X10 PRO", "EU")],
                     "realme": [("Realme 16 PRO+", "IN")]}        # the Android 11 realme is too old


@pytest.fixture
def violet(monkeypatch):
    """VioletToolBox stub: violet({(series, device): [version names]})."""
    def install(tree):
        def fake_get(url, headers, timeout=40):
            from urllib.parse import unquote
            path, _, query = url[len(sources.VT_BASE) + 1:].partition("?")
            q = {k: unquote(v).replace("+", " ") for k, v in (p.split("=", 1) for p in query.split("&"))}
            if path == "series":
                return {"items": sorted({s for s, _ in tree})}
            if path == "devices":
                return {"items": [d for s, d in tree if s == q["series"]]}
            return {"items": [{"name": n} for n in tree[(q["series"], q["device"])]]}

        monkeypatch.setattr(sources, "_get", fake_get)

    return install


def test_violet_names_and_devices_are_read():
    assert sources.violet_version("ColorOS PHN110_14.0.0.850(CN01) C.22") == {
        "version": "PHN110_14.0.0.850(CN01)", "model": "PHN110", "ota_version": "PHN110_11.C.22"}
    assert sources.violet_version("OPD2601_16.0.10.600(CN01)")["ota_version"] == "OPD2601_16.0.10.600(CN01)"
    assert sources.violet_version("ColorOS PEMM00_11_A.15") is None                    # no real version number
    assert sources.violet_version("RealmeUI RMX3706_13.1.0.118(SP01CN01) A.48") is None   # not a plain CN firmware
    assert sources.violet_device("[\u666e\u901a]OPPO A55 \u5168\u7f51\u901a\u7248 (PEMM00)") == "OPPO A55"
    assert sources.violet_device("[\u666e\u901a]\u771f\u6211 Realme GT7 Pro\uff08RMX5010\uff09") == "Realme GT7 PRO"


def test_violet_lists_android_14_plus_chinese_firmware_once_with_a_reference_and_no_link(violet):
    violet({("Find", "[\u666e\u901a]OPPO Find N3 (PHN110)"): [
                "ColorOS PHN110_13.2.0.300(CN01) A.48", "ColorOS PHN110_14.0.0.850(CN01) C.22",
                "ColorOS PHN110_15.0.0.860(CN01) F.57"],
            ("Find", "[\u666e\u901a]OPPO Find N3 (PHN110) 2"): ["ColorOS PHN110_15.0.0.860(CN01) F.57"]})
    rels = sources.violet_releases(brands.BRANDS["oppo"], pause=0)
    assert [(r["version"], r["region"], r["device"], r["source_url"]) for r in rels] == [
        ("PHN110_14.0.0.850(CN01)", "CN", "OPPO FIND N3", ""), ("PHN110_15.0.0.860(CN01)", "CN", "OPPO FIND N3", "")]
    assert rels[0]["violet"] == {"brand": "OPPO", "series": "Find", "device": "[\u666e\u901a]OPPO Find N3 (PHN110)",
                                 "name": "ColorOS PHN110_14.0.0.850(CN01) C.22"}
    assert rels[0]["id"].startswith("vt-") and rels[0]["origin"] == "violettoolbox"


def test_violet_link_is_asked_with_the_reference_and_may_be_missing(monkeypatch):
    import io
    import json as _json
    asked = []

    def fake_urlopen(req, timeout=0):
        asked.append(_json.loads(req.data))
        return io.BytesIO(_json.dumps({"links": ["https://example.invalid/vt.zip"] if len(asked) == 1 else []}).encode())

    monkeypatch.setattr(sources.urllib.request, "urlopen", fake_urlopen)
    ref = {"brand": "OPPO", "series": "Find", "device": "d", "name": "v"}
    assert sources.violet_link(ref) == "https://example.invalid/vt.zip"
    assert sources.violet_link(ref) == ""
    assert asked[0] == {"packageType": "full", "brand": "OPPO", "series": "Find", "device": "d", "version": "v"}


def test_violet_old_oneplus_models_are_not_listed(violet):
    violet({("number", "[\u666e\u901a]OnePlus 9 (LE2110)"): ["ColorOS LE2110_14.0.0.100(CN01) A.01"]})
    assert sources.violet_releases(brands.BRANDS["oneplus"], pause=0) == []


def test_violet_down_is_reported_and_does_not_stop_the_run(monkeypatch, capsys):
    def down(url, headers, timeout=40):
        raise OSError("unreachable")

    monkeypatch.setattr(sources, "_get", down)
    assert sources.violet_releases(brands.BRANDS["oppo"], pause=0) == []
    assert "VioletToolBox: OPPO not read" in capsys.readouterr().err
