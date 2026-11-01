import urllib.parse
import urllib.request

import pytest
from helpers import read_json, result, write_json

from opkv import cli, sources


@pytest.fixture(autouse=True)
def _no_external_network(monkeypatch):
    """The suite must never reach a real host: only the loopback test servers are allowed."""
    real = urllib.request.urlopen

    def guarded(req, *args, **kwargs):
        url = req if isinstance(req, str) else req.full_url
        if urllib.parse.urlparse(url).hostname not in ("127.0.0.1", "localhost"):
            raise AssertionError(f"test tried to reach {url}")
        return real(req, *args, **kwargs)

    monkeypatch.setattr(urllib.request, "urlopen", guarded)


@pytest.fixture
def run(tmp_path, monkeypatch):
    """`opkv run` on a catalog/results pair, extraction stubbed.

    go(releases, rows, *flags) -> (extracted URLs, results rows after the run)
    """
    extracted = []

    def fake_extract(url):
        extracted.append(url)
        return result()

    def offline(*args, **kwargs):
        raise AssertionError("the metadata pass must not be needed")

    monkeypatch.setattr(cli, "extract", fake_extract)
    monkeypatch.setattr(cli, "extract_android", offline)
    monkeypatch.setattr(sources, "arb_index", offline)

    def go(releases, rows, *flags):
        cat = write_json(tmp_path / "catalog.json", {"api_version": "1", "releases": releases})
        out = tmp_path / "results.json"
        write_json(out, rows)
        assert cli.main(["run", "--catalog", cat, "--out", str(out), *flags]) == 0
        go.path = out
        return extracted, read_json(out)

    return go
