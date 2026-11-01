import hashlib

import pytest

from opkv import sources


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
    rels = {r["device"]: r for r in sources.ou_releases(workers=1)}
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
    assert sources.ou_releases(workers=1) == []


def test_a_device_that_fails_does_not_stop_the_others_and_is_reported(oxygen, capsys):
    oxygen([{"id": 1, "name": "OnePlus 13 (EU)"}, {"id": 2, "name": "OnePlus 12 (EU)"}],
           {1: FULL, 2: FULL}, {(1, 10): update("CPH2653_16.0.0.210(EX01)")}, broken=(2,))
    assert [r["device"] for r in sources.ou_releases(workers=1)] == ["OP 13"]
    err = capsys.readouterr().err
    assert "warning: Oxygen Updater: 1 of 2 devices could not be read" in err and "OP 12 EU: OSError" in err


def test_failures_become_a_workflow_annotation_in_github_actions(oxygen, capsys, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    oxygen([{"id": 1, "name": "OnePlus 13 (EU)"}], {1: FULL}, {}, broken=(1,))
    assert sources.ou_releases(workers=1) == []
    assert "::warning title=Oxygen Updater::Oxygen Updater: 1 of 1 devices could not be read" in capsys.readouterr().out


def test_antirollchecker_index_maps_version_and_region_to_md5(monkeypatch):
    db = {"CPH2653": {"versions": {"CPH2653_16.0.0.210(EX01)": {"md5": "a" * 32, "regions": ["EU", "GLO"]},
                                   "CPH2653_15.0.0.100(EX01)": {"md5": "", "regions": ["EU"]}}},
          "CPH9999": {}}
    monkeypatch.setattr(sources, "_get", lambda url, headers, timeout=40: db)
    assert sources.arb_index() == {("CPH2653_16.0.0.210(EX01)", "EU"): "a" * 32,
                                   ("CPH2653_16.0.0.210(EX01)", "GLO"): "a" * 32}
