import json

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

    monkeypatch.setattr(archive, "releases", lambda token=None: listing)
    monkeypatch.setattr(archive, "extract_asset", fake_extract)

    def go(rows, releases, *flags):
        listing[:] = releases
        out = tmp_path / "results.json"
        write_json(out, rows)
        assert cli.main(["archive", "--out", str(out), "--workers", "1", *flags]) == 0
        return downloaded, read_json(out)

    return go


def test_missing_firmware_is_added_with_the_device_label_of_its_model(archive_run):
    rows = [row(f"a{i}", version=f"CPH2653_15.0.0.{i}00(EX01)", region="GLO", device="OP 13") for i in range(3)]
    rows.append(row("odd", version="CPH2653_15.0.0.900(EX01)", region="EU", device="OP 13S"))
    downloaded, out = archive_run(rows, [rel()])
    new = [r for r in out if r["version"] == V]
    assert len(downloaded) == 1 and len(new) == 1
    assert (new[0]["device"], new[0]["origin"], new[0]["android_version"]) == ("OP 13", "spike0en-archive", "16")
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
    got = archive.releases("tok")
    assert [(r["version"], r["region"]) for r in got] == [("CPH2653_16.0.0.210(EX01)", "GLO"), ("CPH2653_15.0.0.100(EX01)", "EU"),
                                                          ("PLK110_16.0.5.702(CN01)", "CN")]
    assert got[0]["asset_url"] == "https://example.invalid/CPH2653_16.0.0.210(EX01)_ROW/x-image-boot.7z"
    assert [t for _, t in seen] == ["tok"] * 3 and seen[0][0].endswith("releases?per_page=100&page=1")
