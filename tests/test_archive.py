import json
import sys

import pytest
from builders import boot_7z, boot_image
from helpers import BANNER, read_json, result, row, write_json

from opkv import archive, bootimg, cli

V = "CPH2653_16.0.0.210(EX01)"


def rel(version=V, region="EU"):
    return {"version": version, "region": region, "asset_url": f"https://example.invalid/{version}-{region}.7z"}


@pytest.fixture
def archive_run(tmp_path, monkeypatch):
    """`opkv archive` with the GitHub listing and the asset download stubbed.

    go(rows, releases, *flags) -> (downloaded asset URLs, results rows after the run)
    """
    downloaded, listing = [], []

    def fake_extract(url):
        downloaded.append(url)
        return result(source="boot.img")

    monkeypatch.setattr(archive, "releases", lambda repo, token=None: listing)
    monkeypatch.setattr(archive, "extract_asset", fake_extract)

    def go(rows, releases, *flags):
        listing[:] = releases
        out = tmp_path / "oneplus.json"
        write_json(out, rows)
        assert cli.main(["archive", "--brand", "oneplus", "--data-dir", str(tmp_path), "--workers", "1", *flags]) == 0
        return downloaded, read_json(out)

    return go


def test_missing_firmware_is_added_with_the_device_label_of_its_model(archive_run):
    rows = [row(f"a{i}", version=f"CPH2653_15.0.0.{i}00(EX01)", region="GLO", device="13") for i in range(3)]
    rows.append(row("odd", version="CPH2653_15.0.0.900(EX01)", region="EU", device="13S"))
    downloaded, out = archive_run(rows, [rel()])
    new = [r for r in out if r["version"] == V]
    assert len(downloaded) == 1 and len(new) == 1
    assert (new[0]["device"], new[0]["origin"], new[0]["android_version"]) == ("13", "spike0en-archive", "16")
    assert new[0]["id"].startswith("sp-")


def test_firmware_already_stored_is_not_downloaded(archive_run):
    downloaded, out = archive_run([row("a", version=V, region="EU")], [rel()])
    assert downloaded == [] and [r["id"] for r in out] == ["a"]


def test_failed_row_of_the_same_firmware_is_retried_from_the_archive(archive_run):
    downloaded, out = archive_run([row("old", version=V, region="EU", ok=False)], [rel()])
    assert len(downloaded) == 1
    assert [(r["version"], r["ok"]) for r in out] == [(V, True)]


def test_firmware_listed_twice_is_downloaded_once(archive_run):
    # the archive publishes the global package as ROW and GLO: both are recorded as GLO
    downloaded, out = archive_run([row("a", version="CPH2653_15.0.0.100(EX01)", region="GLO")],
                                  [rel(region="GLO"), rel(region="GLO")])
    assert len(downloaded) == 1 and len(out) == 2


def test_model_without_any_stored_row_is_skipped(archive_run):
    downloaded, out = archive_run([row("a")], [rel("CPH9999_15.0.0.100(EX01)")])
    assert downloaded == [] and len(out) == 1


def test_dry_run_lists_without_downloading(archive_run, capsys):
    downloaded, out = archive_run([row("a", version="CPH2653_15.0.0.100(EX01)")], [rel()], "--dry-run")
    assert downloaded == [] and len(out) == 1
    assert V in capsys.readouterr().out


def test_pick_boot_name_prefers_the_plain_boot_image():
    names = ["vendor_kernel_boot.img", "image/boot.img", "init_boot.img", "vendor_boot.img"]
    assert bootimg.pick_boot_name(names) == "image/boot.img"


def test_pick_boot_name_never_returns_the_other_boot_partitions():
    assert bootimg.pick_boot_name(["vendor_kernel_boot.img", "init_boot.img", "vendor_boot.img"]) is None


def test_pick_boot_name_falls_back_to_the_shortest_boot_image_name():
    assert bootimg.pick_boot_name(["x/recovery_boot.img", "boot.img.bak", "xx/yy/slot_boot.img"]) == "x/recovery_boot.img"


def test_asset_with_several_boot_images_is_read_from_boot_img(http_server, tmp_path):
    other = BANNER.replace("6.6.89", "5.4.1")
    http_server.files["/boot.7z"] = boot_7z(tmp_path, {"vendor_kernel_boot.img": boot_image(other), "boot.img": boot_image()})
    res = archive.extract_asset(http_server.url("/boot.7z"))
    assert res.ok, res.error
    assert res.kernel_release == "6.6.89-android15-8-gabc123"


def test_asset_without_boot_image_is_reported(http_server, tmp_path):
    http_server.files["/boot.7z"] = boot_7z(tmp_path, {"vendor_boot.img": boot_image()})
    res = archive.extract_asset(http_server.url("/boot.7z"))
    assert not res.ok and "no boot.img" in res.error


def page(*tags_with_assets):
    return json.dumps([{"tag_name": tag, "assets": [{"name": name, "browser_download_url": f"https://example.invalid/{tag}/{name}"}
                                                    for name in assets]} for tag, assets in tags_with_assets]).encode()


def test_releases_are_listed_across_pages_and_row_becomes_glo(monkeypatch):
    pages = {1: page(("CPH2653_16.0.0.210(EX01)_ROW", ["x-image-boot.7z", "x-other.7z"]),
                     ("CPH2653_15.0.0.100(EX01)_EU", ["x-boot.7z"]),
                     ("CPH2449_13.1.0.500(EX01)_EU", ["x-boot.7z"]),          # Android 13: not wanted
                     ("not-a-firmware-tag", ["x-boot.7z"]),
                     ("CPH2653_16.0.0.300(EX01)_EU", ["only-system.7z"])),    # no boot asset
             2: page(("PLK110_16.0.5.702(CN01)_CN", ["a-boot.7z"])), 3: b"[]"}
    seen = []

    def fake_get(url, token=None):
        seen.append((url, token))
        return pages[int(url.rsplit("page=", 1)[1])]

    monkeypatch.setattr(archive, "_get", fake_get)
    got = archive.releases("spike0en/oneplus_archive", "tok")
    assert [(r["version"], r["region"]) for r in got] == [("CPH2653_16.0.0.210(EX01)", "GLO"), ("CPH2653_15.0.0.100(EX01)", "EU"),
                                                          ("PLK110_16.0.5.702(CN01)", "CN")]
    assert got[0]["asset_url"] == "https://example.invalid/CPH2653_16.0.0.210(EX01)_ROW/x-image-boot.7z"
    assert [t for _, t in seen] == ["tok"] * 3 and seen[0][0].endswith("releases?per_page=100&page=1")


@pytest.mark.parametrize("url", ["file:///etc/hostname", "ftp://example.invalid/boot.7z"])
def test_asset_url_must_be_http(url):
    res = archive.extract_asset(url)
    assert not res.ok and "unsupported URL scheme" in res.error


def test_archive_command_explains_the_missing_optional_dependency(archive_run, monkeypatch):
    monkeypatch.setitem(sys.modules, "py7zr", None)               # as if the `archive` extra was not installed
    with pytest.raises(SystemExit, match=r"opkv\[archive\]"):
        archive_run([row("a", version="CPH2653_15.0.0.100(EX01)")], [rel()])


def test_dry_run_does_not_need_the_optional_dependency(archive_run, monkeypatch):
    monkeypatch.setitem(sys.modules, "py7zr", None)
    assert archive_run([row("a", version="CPH2653_15.0.0.100(EX01)")], [rel()], "--dry-run")[0] == []


def test_failed_archive_row_is_not_downloaded_again_by_default(archive_run):
    failed = row("sp-1", version=V, region="EU", ok=False, origin="spike0en-archive")
    downloaded, out = archive_run([failed], [rel()])
    assert downloaded == [] and [r["id"] for r in out] == ["sp-1"]


def test_retry_failed_downloads_failed_archive_rows_again(archive_run):
    failed = row("sp-1", version=V, region="EU", ok=False, origin="spike0en-archive")
    downloaded, out = archive_run([failed], [rel()], "--retry-failed")
    assert len(downloaded) == 1 and [(r["version"], r["ok"]) for r in out] == [(V, True)]


def test_nothing_tags_name_the_build_and_the_package_is_global():
    repo = "spike0en/nothing_archive"
    assert archive.parse_tag(repo, "Tetris_B4.1-261028-1606") == ("Tetris_B4.1-261028-1606", "GLO")
    assert archive.parse_tag(repo, "SuperContra_B4.1-261111-1740") == ("SuperContra_B4.1-261111-1740", "GLO")
    assert archive.parse_tag(repo, "CPH2653_16.0.0.210(EX01)_ROW") is None
    assert archive.parse_tag("spike0en/oneplus_archive", "Tetris_B4.1-261028-1606") is None


def test_nothing_releases_older_than_android_14_are_left_out(monkeypatch):
    listing = page(("Pong_B4.1-261014-1615", ["x-image-boot.7z"]),            # B = Android 16
                   ("Spacewar_V3.2-260618-1045", ["x-image-boot.7z"]),        # V = Android 15
                   ("Pong_T2.5-240101-1000", ["x-image-boot.7z"]))            # T = Android 13
    monkeypatch.setattr(archive, "_get", lambda url, token=None: listing if url.endswith("page=1") else b"[]")
    assert [r["version"] for r in archive.releases("spike0en/nothing_archive")] == ["Pong_B4.1-261014-1615", "Spacewar_V3.2-260618-1045"]


def test_nothing_firmware_is_added_with_the_device_of_its_codename(tmp_path, monkeypatch):
    monkeypatch.setattr(archive, "releases", lambda repo, token=None: [
        rel("Pacman_C5.0-261112-1938", "GLO"), rel("Unknown_C5.0-261112-1938", "GLO")])
    monkeypatch.setattr(archive, "extract_asset", lambda url: result(source="boot.img"))
    assert cli.main(["archive", "--brand", "nothing", "--data-dir", str(tmp_path), "--workers", "1"]) == 0
    (new,) = read_json(tmp_path / "nothing.json")
    assert (new["brand"], new["device"], new["model"], new["android_version"], new["origin"]) == (
        "Nothing", "Phone (2a)", "Pacman", "17", "spike0en-archive")


def test_brands_without_an_archive_are_said_so(tmp_path, capsys):
    assert cli.main(["archive", "--brand", "xiaomi", "--data-dir", str(tmp_path), "--dry-run"]) == 0
    assert "no Xiaomi firmware" in capsys.readouterr().err


FEED = b"""<?xml version="1.0" encoding="UTF-8"?><feed><entry><link rel="alternate" href="https://github.com/spike0en/nothing_archive/releases/tag/Pacman_C5.0-261112-1938"/></entry>
<entry><link href="/spike0en/nothing_archive/releases/tag/Spacewar_S1.1-230112-1613-GLO"/></entry>
<entry><link href="/spike0en/nothing_archive/releases/tag/0.0.0-dev+pong.240625"/></entry>
<entry><link href="/spike0en/nothing_archive/releases/tag/Pong_T2.5-230901-1200"/></entry>
<entry><link href="/spike0en/nothing_archive/releases/tag/Pacman_C5.0-261112-1938"/></entry></feed>"""


def test_latest_releases_come_from_the_public_feed_without_the_api(monkeypatch):
    asked = []
    monkeypatch.setattr(archive, "_get", lambda url, token=None: asked.append(url) or FEED)
    got = archive.latest_releases("spike0en/nothing_archive")
    assert asked == ["https://github.com/spike0en/nothing_archive/releases.atom"]          # a page, not api.github.com
    assert got == [{"version": "Pacman_C5.0-261112-1938", "region": "GLO", "asset_url":
                    "https://github.com/spike0en/nothing_archive/releases/download/Pacman_C5.0-261112-1938/Pacman_C5.0-261112-1938-image-boot.7z"}]


def test_latest_option_never_calls_the_api(tmp_path, monkeypatch):
    def api(*a, **k):
        raise AssertionError("the GitHub API must not be used")

    monkeypatch.setattr(archive, "releases", api)
    monkeypatch.setattr(archive, "latest_releases", lambda repo: [rel("Pacman_C5.0-261112-1938", "GLO")])
    monkeypatch.setattr(archive, "extract_asset", lambda url: result(source="boot.img"))
    assert cli.main(["archive", "--brand", "nothing", "--data-dir", str(tmp_path), "--workers", "1", "--latest"]) == 0
    (new,) = read_json(tmp_path / "nothing.json")
    assert (new["device"], new["version"]) == ("Phone (2a)", "Pacman_C5.0-261112-1938")


def test_latest_release_whose_asset_is_not_there_yet_is_left_for_the_next_run(tmp_path, monkeypatch):
    from opkv.extract import Result
    monkeypatch.setattr(archive, "latest_releases", lambda repo: [rel("Pacman_C5.0-261112-1938", "GLO")])
    monkeypatch.setattr(archive, "extract_asset", lambda url: Result(error="HTTPError: HTTP Error 404: Not Found"))
    assert cli.main(["archive", "--brand", "nothing", "--data-dir", str(tmp_path), "--workers", "1", "--latest"]) == 0
    assert read_json(tmp_path / "nothing.json") == []                    # no failed row: it is tried again tomorrow
