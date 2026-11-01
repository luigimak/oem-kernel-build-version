import io
import json
import urllib.request

import pytest
from helpers import read_json, release, write_json

from opkv import cli


@pytest.fixture
def fetch(tmp_path, monkeypatch):
    """`opkv fetch` against a stubbed API: fetch(api_payload, stored_catalog=None) -> (catalog releases, stdout)."""
    def go(payload, stored=None, capsys=None):
        monkeypatch.setattr(urllib.request, "urlopen", lambda req, *a, **k: io.BytesIO(json.dumps(payload).encode()))
        out = tmp_path / "data" / "catalog.json"
        if stored is not None:
            out.parent.mkdir(exist_ok=True)
            write_json(out, {"api_version": "1", "releases": stored})
        assert cli.main(["fetch", "--api", "http://localhost/api", "--out", str(out)]) == 0
        return read_json(out)["releases"]

    return go


def test_first_fetch_creates_the_catalog(fetch, capsys):
    releases = fetch({"api_version": "1", "releases": [release("a"), release("x", device="Xiaomi 15", version="OS3.0.1")]})
    assert [r["id"] for r in releases] == ["a", "x"]
    assert "catalog initialized with 2 releases (1 OnePlus)" in capsys.readouterr().out


def test_api_answering_with_a_bare_list_is_accepted(fetch):
    assert [r["id"] for r in fetch([release("a")])] == ["a"]


def test_releases_the_api_dropped_are_kept_and_new_ones_added(fetch, capsys):
    releases = fetch({"releases": [release("new", version="CPH2645_16.0.0.100(EX01)")]}, stored=[release("old")])
    assert sorted(r["id"] for r in releases) == ["new", "old"]
    out = capsys.readouterr().out
    assert "2 releases in total, 1 new (1 OnePlus)" in out and "+ OP 13R" in out and "CPH2645_16.0.0.100(EX01)" in out


def test_known_release_is_refreshed_from_the_api(fetch):
    stored = release("a", source_url="https://example.invalid/old.zip", is_latest=True)
    live = release("a", source_url="https://example.invalid/new.zip", is_latest=False)
    releases = fetch({"releases": [live]}, stored=[stored])
    assert (releases[0]["source_url"], releases[0]["is_latest"]) == ("https://example.invalid/new.zip", False)


def test_known_release_keeps_the_metadata_the_api_leaves_empty(fetch):
    stored = release("a", md5="a" * 32, size=1000, source_url="https://example.invalid/old.zip")
    live = release("a", md5="", size=0, source_url="https://example.invalid/new.zip")
    releases = fetch({"releases": [live]}, stored=[stored])
    assert (releases[0]["md5"], releases[0]["size"], releases[0]["source_url"]) == ("a" * 32, 1000, "https://example.invalid/new.zip")


def test_long_list_of_new_releases_is_cut_after_twenty(fetch, capsys):
    live = [release(f"n{i:02d}", version=f"CPH2645_16.0.0.{i}(EX01)", build_timestamp=f"2026-01-{i + 1:02d}T00:00:00")
            for i in range(22)]
    fetch({"releases": live}, stored=[release("old")])
    out = capsys.readouterr().out
    assert out.count("  + ") == 20 and "... and 2 more" in out


def test_url_command_prints_the_result_as_json(http_server, capsys):
    from builders import ota_zip
    http_server.files["/ota.zip"] = ota_zip()
    assert cli.main(["url", http_server.url("/ota.zip")]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is True and data["kernel_release"] == "6.6.89-android15-8-gabc123"


def test_url_command_fails_on_an_unreachable_package(http_server, capsys):
    assert cli.main(["url", http_server.url("/gone.zip")]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False
