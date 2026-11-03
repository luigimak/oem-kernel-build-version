import io
import json
import urllib.request

import pytest
from helpers import read_json, release, row, write_json

from opkv import cli, ota_query, sources


def variant(region, model, letter="A"):
    return {"displayName": region, "productModel": model, "productName": f"{model}{region}", "versionLetter": letter}


def device(name, *variants, groups=("Android 15", "Android 16")):
    return {"name": name, "firmwareGroups": {g: list(variants) for g in groups}}


def answer(version, letter="A"):
    return {"version": version, "letter": letter}


def ou_release(rid, version, region, device_label, **kw):
    model = version.split("_")[0]
    return {"id": rid, "device": device_label, "region": region, "model": model, "version": version,
            "ota_version": f"{model}_11.F.53_2530_202609141846", "build_timestamp": "2026-09-14T18:46:00",
            "source_url": "https://example.invalid/ou.zip", "md5": "e" * 32, "size": 7, "is_latest": True,
            "origin": "oxygen-updater", **kw}


@pytest.fixture
def discover(tmp_path, monkeypatch):
    """`opkv discover` with the three network boundaries stubbed (OTA Pulse device list, OTA servers, Oxygen Updater).

    Returns go(catalog_releases, results_rows, devices=[], answers={}, ou=[], no_ou=True) -> catalog releases after the run;
    the (model, region, letter) of every OTA query is left in go.queries.
    """
    state = {"devices": [], "answers": {}, "ou": [], "violet": []}
    queries = []

    def fake_urlopen(req, *args, **kwargs):
        return io.BytesIO(json.dumps(state["devices"]).encode())

    def fake_query(q, timeout=30):
        queries.append((q.model, q.region_name, q.letter))
        hit = state["answers"].get((q.model, q.region_name))
        if not hit or hit["letter"] != q.letter:
            raise ota_query.OtaQueryError("server 2004: no update")
        return {"versionName": hit["version"], "realOtaVersion": f"{q.model}_11.{q.letter}.75_1750_202610181120",
                "securityPatch": "2026-10-05",
                "components": [{"componentPackets": {"manualUrl": f"https://example.invalid/{q.model}.zip",
                                                     "md5": "c" * 32, "size": "5000"}}]}

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(ota_query, "query", fake_query)
    monkeypatch.setattr(sources, "ou_releases", lambda brand, workers=6: state["ou"])

    def fake_violet(brand, pause=0.3):
        return [dict(r) for r in state["violet"]]

    monkeypatch.setattr(sources, "violet_releases", fake_violet)

    def go(catalog_releases, results_rows, devices=(), answers=None, ou=(), no_ou=True, violet=(), scan=False):
        state.update(devices=list(devices), answers=answers or {}, ou=list(ou), violet=list(violet))
        cat = tmp_path / "catalog.json"
        write_json(cat, {"api_version": "1", "releases": catalog_releases})
        out = tmp_path / "oneplus.json"
        write_json(out, results_rows)
        argv = ["discover", "--brand", "oneplus", "--data-dir", str(tmp_path), "--catalog", str(cat)]
        assert cli.main(argv + (["--no-ou"] if no_ou else []) + ([] if violet else ["--no-violet"])
                                  + (["--rescan-days", "1"] if scan else ["--no-scan"])) == 0
        return read_json(cat)["releases"]

    go.queries = queries
    return go


def test_known_firmware_with_another_ota_letter_is_not_added_again(discover, capsys):
    known = release("cat1", version="CPH2745_17.0.0.102(EX01)", region="IN", device="OP 15",
                    ota_version="CPH2745_11.A.75_1750_202610181120", source_url="https://example.invalid/old.zip")
    releases = discover([known], [], devices=[device("OnePlus 15", variant("IN", "CPH2745", "C"))],
                        answers={("CPH2745", "IN"): answer("CPH2745_17.0.0.102(EX01)", "C")})
    assert [r["id"] for r in releases] == ["cat1"]
    assert releases[0]["source_url"] == "https://example.invalid/CPH2745.zip"        # the expired link is refreshed
    assert "new releases from OTA query: 0" in capsys.readouterr().out


def test_model_listed_under_two_devices_is_queried_once_and_keeps_the_catalog_label(discover):
    # OTA Pulse also lists the global OnePlus 13 model (CPH2653) under "OnePlus 13s"
    old = release("old", version="CPH2653_15.0.0.401(EX01)", region="GLO", device="OP 13")
    listing = [device("OnePlus 13s", variant("GLO", "CPH2653")), device("OnePlus 13", variant("GLO", "CPH2653"))]
    releases = discover([old], [], devices=listing, answers={("CPH2653", "GLO"): answer("CPH2653_16.0.0.210(EX01)")})
    assert discover.queries == [("CPH2653", "GLO", "A")]
    assert {r["version"]: r["device"] for r in releases} == {"CPH2653_15.0.0.401(EX01)": "OP 13",
                                                             "CPH2653_16.0.0.210(EX01)": "OP 13"}


def test_new_model_without_catalog_entry_is_labelled_from_the_ota_pulse_name(discover):
    releases = discover([], [], devices=[device("OnePlus Pad2 Pro", variant("EU", "OPD2511"))],
                        answers={("OPD2511", "EU"): answer("OPD2511_15.0.0.100(EX01)")})
    assert [(r["device"], r["origin"]) for r in releases] == [("OP PAD 2 PRO", "ota-query")]


def test_firmware_already_in_results_is_not_new_but_stays_retryable(discover, capsys):
    failed = row("q-old", version="CPH2745_17.0.0.102(EX01)", region="IN", device="OP 15", ok=False)
    releases = discover([], [failed], devices=[device("OnePlus 15", variant("IN", "CPH2745"))],
                        answers={("CPH2745", "IN"): answer("CPH2745_17.0.0.102(EX01)")})
    assert [r["version"] for r in releases] == ["CPH2745_17.0.0.102(EX01)"]
    assert "new releases from OTA query: 0" in capsys.readouterr().out


def test_other_ota_letters_seen_in_the_catalog_are_tried_when_the_first_has_no_update(discover):
    known = release("cat1", version="CPH2745_17.0.0.100(EX01)", region="IN", device="OP 15",
                    ota_version="CPH2745_11.C.70_1700_202610010000")
    releases = discover([known], [], devices=[device("OnePlus 15", variant("IN", "CPH2745", "A"))],
                        answers={("CPH2745", "IN"): answer("CPH2745_17.0.0.102(EX01)", "C")})
    assert discover.queries == [("CPH2745", "IN", "A"), ("CPH2745", "IN", "C")]
    assert {r["version"] for r in releases} == {"CPH2745_17.0.0.100(EX01)", "CPH2745_17.0.0.102(EX01)"}


def test_firmware_older_than_android_14_is_ignored(discover):
    releases = discover([], [], devices=[device("OnePlus 12", variant("EU", "CPH2581"))],
                        answers={("CPH2581", "EU"): answer("CPH2581_13.1.0.500(EX01)")})
    assert releases == []


def test_failed_oxygen_updater_row_is_offered_again_for_a_retry(discover):
    version = "CPH2399_14.0.0.3101(EX01)"
    failed = row("ou-1", version=version, region="EU", device="OP NORD 2T", ok=False)
    releases = discover([], [failed], ou=[ou_release("ou-1", version, "EU", "OP NORD 2T")], no_ou=False)
    assert [r["id"] for r in releases] == ["ou-1"]


def test_oxygen_updater_release_takes_the_catalog_label_of_its_model(discover):
    known = release("cat1", version="OPD2504_15.0.0.100(EX01)", region="GLO", device="OP PAD GO 2")
    ou = ou_release("ou-2", "OPD2504_15.0.0.200(EX01)", "GLO", "OP PAD GO 2 WIFI")
    releases = discover([known], [], ou=[ou], no_ou=False)
    assert {r["id"]: r["device"] for r in releases} == {"cat1": "OP PAD GO 2", "ou-2": "OP PAD GO 2"}


def test_oxygen_updater_completes_the_metadata_of_a_known_firmware(discover):
    known = release("cat1", version="CPH2399_14.0.0.3101(EX01)", region="EU", device="OP NORD 2T", md5="", size=0)
    ou = ou_release("ou-3", "CPH2399_14.0.0.3101(EX01)", "EU", "OP NORD 2T")
    releases = discover([known], [], ou=[ou], no_ou=False)
    assert [(r["id"], r["md5"], r["size"]) for r in releases] == [("cat1", "e" * 32, 7)]


def violet_release(version, device="OPPO FIND N3"):
    model = version.split("_")[0]
    return {"id": "vt-" + model, "device": device, "region": "CN", "model": model, "version": version,
            "ota_version": version, "build_timestamp": "", "source_url": "", "md5": "", "size": 0,
            "origin": "violettoolbox", "violet": {"brand": "OPPO", "series": "Find", "device": "x", "name": version}}


def test_violettoolbox_firmware_is_added_to_the_catalog_with_its_reference(discover, capsys):
    v = violet_release("PHN110_14.0.0.850(CN01)")
    releases = discover([], [], violet=[v])
    assert [(r["id"], r["origin"], r["source_url"], r["violet"]) for r in releases] == [
        ("vt-PHN110", "violettoolbox", "", v["violet"])]
    assert "from VioletToolBox: 1" in capsys.readouterr().out


def test_violettoolbox_firmware_already_read_is_left_out(discover):
    v = violet_release("PHN110_14.0.0.850(CN01)")
    done = row("a", version=v["version"], region="CN", device="OPPO FIND N3")
    assert discover([], [done], violet=[v]) == []


def test_violettoolbox_reference_is_added_to_a_failed_firmware_the_catalog_knows(discover):
    v = violet_release("PHN110_14.0.0.850(CN01)")
    old = release("cat1", version=v["version"], region="CN", device="OPPO FIND N3", source_url="https://example.invalid/old.zip")
    failed = row("cat1", version=v["version"], region="CN", device="OPPO FIND N3", ok=False)
    releases = discover([old], [failed], violet=[v])
    assert [(r["id"], r["source_url"], r["violet"]) for r in releases] == [
        ("cat1", "https://example.invalid/old.zip", v["violet"])]


def test_failed_firmware_missing_from_every_source_is_searched_letter_by_letter(discover):
    version = "CPH2701_16.0.5.1301(EX01)"
    failed = row("ou-9", version=version, region="ID", device="OPPO RENO 15", ok=False, android_version="16")
    releases = discover([], [failed], answers={("CPH2701", "ID"): answer(version, "C")}, scan=True)
    assert [(r["version"], r["region"], r["origin"], r["source_url"]) for r in releases] == [
        (version, "ID", "ota-scan", "https://example.invalid/CPH2701.zip")]
    assert [q[2] for q in discover.queries] == ["A", "B", "C"]             # it stops at the letter that answers


def test_failed_firmware_nobody_answers_for_is_tried_with_all_letters(discover):
    failed = row("ou-9", version="CPH2701_16.0.5.1301(EX01)", region="ID", device="OPPO RENO 15", ok=False,
                 android_version="16")
    assert discover([], [failed], scan=True) == []
    assert {q[2] for q in discover.queries} == set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def test_failed_firmware_known_to_the_catalog_only_gets_a_new_link(discover):
    version = "CPH2701_16.0.5.1301(EX01)"
    old = release("cat1", version=version, region="ID", device="OPPO RENO 15", source_url="https://example.invalid/old.zip")
    failed = row("cat1", version=version, region="ID", device="OPPO RENO 15", ok=False, android_version="16")
    releases = discover([old], [failed], answers={("CPH2701", "ID"): answer(version, "F")}, scan=True)
    assert [(r["id"], r["source_url"]) for r in releases] == [("cat1", "https://example.invalid/CPH2701.zip")]


def test_failed_firmware_that_got_a_link_from_another_source_is_not_searched(discover):
    v = violet_release("PHN110_14.0.0.850(CN01)")
    failed = row("cat1", version=v["version"], region="CN", device="OPPO FIND N3", ok=False, android_version="14")
    discover([], [failed], violet=[v], scan=True)
    assert discover.queries == []


def test_failed_firmware_with_a_region_the_servers_do_not_know_is_not_searched(discover):
    failed = row("a", version="CPH2701_16.0.5.1301(EX01)", region="APC", ok=False, android_version="16")
    discover([], [failed], scan=True)
    assert discover.queries == []


def test_rows_take_turns_when_they_are_searched_every_few_days():
    import datetime
    rows = [{"version": f"CPH27{i:02d}_16.0.5.1301(EX01)", "region": "ID"} for i in range(40)]
    week = [datetime.date(2026, 11, 1) + datetime.timedelta(days=d) for d in range(7)]
    searched = [r["version"] for day in week for r in rows if cli._due(r, 7, day)]
    assert sorted(searched) == sorted(r["version"] for r in rows)        # each one exactly once a week
    assert all(cli._due(r, 1, week[0]) for r in rows)                     # every day when asked to
