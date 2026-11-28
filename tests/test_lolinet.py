"""Motorola and Lenovo firmware from the lolinet mirror: index pages, package names, the walk over the directories."""
import datetime
import io
import urllib.error

import pytest
from helpers import read_json, write_json

from opkv import brands, catalog, cli, lolinet

MOTO = brands.BRANDS["motorola"]
LENOVO = brands.BRANDS["lenovo"]
TODAY = datetime.date.today()


def page(*rows):
    """An h5ai index: rows are (href, name, 'YYYY-MM-DD HH:MM'); the parent link comes first, as on the mirror."""
    body = '<tr><td class="fb-n"><a href="..">Parent Directory</a></td><td class="fb-d"></td><td class="fb-s"></td></tr>'
    body += "".join(f'<tr><td class="fb-i"><img alt="x"/></td><td class="fb-n"><a href="{h}">{n}</a></td>'
                    f'<td class="fb-d">{d}</td><td class="fb-s">1 KB</td></tr>' for h, n, d in rows)
    return f"<html><body><div id='fallback'><table>{body}</table></div></body></html>"


def entry(name, day=None):
    return lolinet.Entry("/x/" + name, name, day)


class Mirror:
    """urlopen stand-in: {path: page html or an HTTP status}; every path asked for is kept."""
    def __init__(self):
        self.pages, self.asked = {}, []

    def __call__(self, req, timeout=0):
        path = req.full_url.removeprefix(lolinet.BASE)
        self.asked.append(path)
        what = self.pages.get(path, 404)
        if isinstance(what, int):
            raise urllib.error.HTTPError(req.full_url, what, "x", {}, None)
        return io.BytesIO(what.encode())


@pytest.fixture
def mirror(monkeypatch):
    m = Mirror()
    monkeypatch.setattr(lolinet.urllib.request, "urlopen", m)
    monkeypatch.setattr(lolinet.time, "sleep", lambda s: None)
    return m


def test_index_page_gives_names_links_and_dates(mirror):
    mirror.pages["/d/"] = page(("/d/a/", "a", "2026-10-31 15:20"), ("/d/f%201.zip", "f 1.zip", "2026-08-23 21:52"),
                               ("/d/odd/", "odd", "not a date"))
    got = lolinet.listing("/d/")
    assert [(e.name, e.href, e.is_dir, e.modified) for e in got] == [
        ("a", "/d/a/", True, datetime.date(2026, 10, 31)), ("f 1.zip", "/d/f%201.zip", False, datetime.date(2026, 8, 23)),
        ("odd", "/d/odd/", True, None)]


def test_missing_directory_is_empty_and_other_errors_are_raised(mirror):
    assert lolinet.listing("/nowhere/") == []
    mirror.pages["/busy/"] = 503
    with pytest.raises(urllib.error.HTTPError):
        lolinet.listing("/busy/")


@pytest.mark.parametrize("name,version,channel,model", [
    ("XT2611-3_AVR_RETEU_16_W3WW36.65-64-4_subsidy-DEFAULT_regulatory-DEFAULT_cid50_CFC.xml.zip",
     "XT2611-3_16_W3WW36.65-64-4", "RETEU", "XT2611-3"),
    ("XT2415-1_CANCUNN_RETUS_15_V1UD35H.26-14-6_subsidy-DEFAULT_regulatory-DEFAULT_cid50_R2_CFC.xml.zip",
     "XT2415-1_15_V1UD35H.26-14-6", "RETUS", "XT2415-1"),
    ("XT2611-3_AVR_RETEU_17_A171WWH.15-43_subsidy-DEFAULT_regulatory-DEFAULT_cid50_CFC.xml.zip",
     "XT2611-3_17_A171WWH.15-43", "RETEU", "XT2611-3")])
def test_motorola_retail_package_names_give_the_release(name, version, channel, model):
    rel = lolinet.motorola_release(MOTO, entry(name))
    assert (rel["version"], rel["region"], rel["model"], rel["device"], rel["origin"]) == (
        version, channel, model, "Motorola " + name.split("_")[1], "lolinet")
    assert rel["source_url"] == lolinet.BASE + "/x/" + name and rel["ota_version"] == name


@pytest.mark.parametrize("name", [
    "XT2415-3_CANCUNN_ATT_15_V1UDS35H.26-14-6-11_subsidy-ATT_RSU_regulatory-DEFAULT_cid51_CFC.xml.zip",       # a carrier build
    "XT2345-3_CANCUN_RETAIL_13_T1TNS33.42-5_subsidy-DEFAULT_regulatory-DEFAULT_cid50_CFC.xml.zip",             # Android 13
    "XT2611-3_AVR_RETEU_16_W3WW36.65-64-4_subsidy-DEFAULT_regulatory-DEFAULT_cid50_CFC.xml.7z",               # not a zip
    "README.html", "Moto_Tool.zip"])
def test_motorola_names_that_are_not_retail_android_14_zips_are_left_out(name):
    assert lolinet.motorola_release(MOTO, entry(name)) is None


@pytest.mark.parametrize("name,android,region", [
    ("TB390FU_ROW_OPEN_USER_Q00012.1_A16_ZUI_18.0.10.335_ST_260618.zip", "16", "ROW"),
    ("TB330FU_ROW_OPEN_USER_V15.155_U_ZUI_16.0.198_ST_241220_SVC.zip", "14", "ROW"),
    ("TB336FU_ROW_OPEN_USER_M1317.3_W_ZUI_17.5.10.085_ST_251230.zip", "16", "ROW")])
def test_lenovo_tablet_zips_give_the_release(name, android, region):
    rel = lolinet.lenovo_release(LENOVO, entry(name), "Idea_Tab_Pro_Gen_2_2026")
    assert rel["version"] == name[:-4] and rel["region"] == region and rel["model"] == name.split("_")[0]
    assert rel["device"] == "Lenovo Idea Tab Pro Gen 2 2026"
    assert catalog.os_major(rel["version"]) == int(android)


@pytest.mark.parametrize("name", [
    "TB570FU_ROW_OPEN_USER_V1457.5_T_ZUI_15.0.756_ST_230830.zip",                  # Android 13
    "TB710FU_CN_OPEN_USER_Q00019.0_A16_ZUI_17.5.04.414_ST_260320.7z",              # a 7z can not be read in part
    "SP_Flash_Tool_V5_TB330_POGOPIN.zip", "QFil-V3.zip", "d-52C_S_S301014_202302261433_JP.zip"])
def test_lenovo_names_that_are_not_android_14_tablet_zips_are_left_out(name):
    assert lolinet.lenovo_release(LENOVO, entry(name), "Tab") is None


MOTO_FILE = "XT2611-3_AVR_RETEU_16_W3WW36.65-64-4_subsidy-DEFAULT_regulatory-DEFAULT_cid50_CFC.xml.zip"
CARRIER = "XT2611-1_AVR_ATT_16_W3WW36.65-64-4_subsidy-ATT_RSU_regulatory-DEFAULT_cid51_CFC.xml.zip"


def motorola_tree(mirror, old="2026-01-02 10:00", new="2026-11-18 20:37"):
    root = "/firmware/lenomola/"
    mirror.pages[root] = page((root + "2026/", "2026", new), (root + "2020/", "2020", old), (root + "_obsoleted_/", "_obsoleted_", old))
    mirror.pages[root + "2026/"] = page((root + "2026/avr/", "avr", new), (root + "2026/lamy/", "lamy", old))
    mirror.pages[root + "2026/avr/official/"] = page((root + "2026/avr/official/RETEU/", "RETEU", new),
                                                      (root + "2026/avr/official/ATT/", "ATT", new))
    mirror.pages[root + "2026/avr/official/RETEU/"] = page((root + "2026/avr/official/RETEU/" + MOTO_FILE, MOTO_FILE, new))
    mirror.pages[root + "2026/avr/official/ATT/"] = page((root + "2026/avr/official/ATT/" + CARRIER, CARRIER, new))
    mirror.pages[root + "2026/lamy/official/"] = page((root + "2026/lamy/official/RETIN/", "RETIN", old))
    return root


def test_walk_lists_retail_firmware_of_the_years_since_2022(mirror):
    motorola_tree(mirror)
    got = lolinet.releases(MOTO)
    assert [(r["device"], r["region"], r["version"]) for r in got] == [("Motorola AVR", "RETEU", "XT2611-3_16_W3WW36.65-64-4")]
    assert "/firmware/lenomola/2020/" not in mirror.asked and "/firmware/lenomola/_obsoleted_/" not in mirror.asked
    assert "/firmware/lenomola/2026/avr/official/ATT/" not in mirror.asked                       # a carrier folder is not opened


def test_walk_with_a_cutoff_only_follows_what_changed(mirror):
    motorola_tree(mirror)
    got = lolinet.releases(MOTO, since=datetime.date(2026, 11, 1))
    assert [r["region"] for r in got] == ["RETEU"]
    assert not any("lamy" in p and p.endswith("official/") for p in mirror.asked)      # the device nobody touched is not opened


def test_walk_with_a_cutoff_skips_old_files_of_a_fresh_folder(mirror):
    root = motorola_tree(mirror)
    mirror.pages[root + "2026/avr/official/RETEU/"] = page((root + "2026/avr/official/RETEU/" + MOTO_FILE, MOTO_FILE, "2026-01-01 00:00"))
    assert lolinet.releases(MOTO, since=datetime.date(2026, 11, 1)) == []


def test_unreadable_directory_is_reported_and_the_rest_is_kept(mirror, capsys):
    root = motorola_tree(mirror)
    mirror.pages[root + "2026/avr/official/RETIN/"] = 503
    mirror.pages[root + "2026/avr/official/"] = page((root + "2026/avr/official/RETEU/", "RETEU", "2026-11-18 20:37"),
                                                      (root + "2026/avr/official/RETIN/", "RETIN", "2026-11-18 20:37"))
    assert [r["region"] for r in lolinet.releases(MOTO)] == ["RETEU"]
    assert "directories not read" in capsys.readouterr().err


def test_lenovo_walk_names_the_device_after_its_folder(mirror):
    root = "/firmware/lenowow/"
    f = "TB390FU_ROW_OPEN_USER_Q00012.1_A16_ZUI_18.0.10.335_ST_260618.zip"
    mirror.pages[root] = page((root + "2026/", "2026", "2026-08-27 22:24"))
    mirror.pages[root + "2026/"] = page((root + "2026/Idea_Tab_Pro_Gen_2_2026/", "Idea_Tab_Pro_Gen_2_2026", "2026-08-24 20:17"))
    tab = root + "2026/Idea_Tab_Pro_Gen_2_2026/"
    mirror.pages[tab] = page((tab + "TB390FU/", "TB390FU", "2026-08-24 13:10"))
    mirror.pages[tab + "TB390FU/"] = page((tab + "TB390FU/" + f, f, "2026-08-24 13:10"))
    (rel,) = lolinet.releases(LENOVO)
    assert (rel["device"], rel["model"], rel["region"], rel["version"]) == (
        "Lenovo Idea Tab Pro Gen 2 2026", "TB390FU", "ROW", f[:-4])


def test_discover_adds_the_mirror_firmware_to_the_catalog_once(tmp_path, mirror, monkeypatch):
    motorola_tree(mirror)
    cat = write_json(tmp_path / "catalog.json", {"api_version": "1", "releases": []})
    for _ in range(2):                                                                  # the second run finds nothing new
        assert cli.main(["discover", "--brand", "motorola", "--data-dir", str(tmp_path), "--catalog", cat, "--lolinet-days", "0"]) == 0
    (rel,) = read_json(tmp_path / "catalog.json")["releases"]
    assert (rel["device"], rel["origin"]) == ("Motorola AVR", "lolinet") and rel["source_url"].startswith(lolinet.BASE)


def test_discover_window_comes_from_the_option(tmp_path, mirror):
    motorola_tree(mirror, new=(TODAY - datetime.timedelta(days=3)).isoformat() + " 10:00")
    cat = write_json(tmp_path / "catalog.json", {"api_version": "1", "releases": []})
    cli.main(["discover", "--brand", "motorola", "--data-dir", str(tmp_path), "--catalog", cat, "--lolinet-days", "2"])
    assert read_json(tmp_path / "catalog.json")["releases"] == []
    cli.main(["discover", "--brand", "motorola", "--data-dir", str(tmp_path), "--catalog", cat, "--lolinet-days", "5"])
    assert len(read_json(tmp_path / "catalog.json")["releases"]) == 1
