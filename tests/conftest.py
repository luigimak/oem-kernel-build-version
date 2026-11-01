import collections
import re
import threading
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from helpers import read_json, result, write_json

from opkv import cli, sources


class _Handler(BaseHTTPRequestHandler):
    """Static files with HTTP Range support, like an OTA CDN. Behaviours are switched on the server object."""

    def log_message(self, *args):
        pass

    def _serve(self, head):
        srv = self.server
        path = self.path.split("?")[0]
        srv.requests.append((self.command, path, self.headers.get("Range"), self.headers.get("User-Agent", "")))
        data = srv.files.get(path)
        if data is None:
            return self._reply(404, b"")
        if srv.forbid_ua is not None and self.headers.get("User-Agent", "").startswith(srv.forbid_ua):
            return self._reply(403, b"")
        m = re.fullmatch(r"bytes=(\d+)-(\d*)", self.headers.get("Range") or "")
        if not m or srv.ignore_range:
            return self._reply(200, data, head=head)
        start = int(m[1])
        end = min(int(m[2]) if m[2] else len(data) - 1, len(data) - 1)
        return self._reply(206, data[start:end + 1], head=head, content_range=f"bytes {start}-{end}/{len(data)}")

    def _reply(self, code, body, head=False, content_range=None):
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        if content_range:
            self.send_header("Content-Range", content_range)
        self.end_headers()
        if not head:
            self.server.sent[self.path.split("?")[0]] += len(body)
            self.wfile.write(body)

    do_GET = lambda self: self._serve(False)  # noqa: E731
    do_HEAD = lambda self: self._serve(True)  # noqa: E731


@pytest.fixture
def http_server():
    """Loopback file server: .files {"/path": bytes}, .url(path), .requests [(method, path, range, user agent)],
    .sent {path: body bytes sent}, and switches .forbid_ua (403 for user agents starting with it) and
    .ignore_range (always 200 with the whole body)."""
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    srv.files, srv.requests, srv.sent = {}, [], collections.defaultdict(int)
    srv.forbid_ua, srv.ignore_range = None, False
    srv.url = lambda path: f"http://127.0.0.1:{srv.server_port}{path}"
    thread = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    yield srv
    srv.shutdown()
    srv.server_close()
    thread.join()


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
