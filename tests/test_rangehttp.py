import io
import urllib.error

import pytest

from opkv import extract, rangehttp
from opkv.rangehttp import HttpError, RangeFile

DATA = bytes(range(256)) * 1000        # 256 000 bytes, every offset distinguishable


@pytest.fixture
def served(http_server):
    http_server.files["/f.bin"] = DATA
    return http_server


def test_fetch_range_returns_the_requested_bytes(served):
    assert rangehttp.fetch_range(served.url("/f.bin"), 10, 19) == DATA[10:20]


def test_remote_size_comes_from_content_range(served):
    assert rangehttp.remote_size(served.url("/f.bin")) == len(DATA)


def test_range_file_reads_seeks_and_caches(served):
    rf = RangeFile(served.url("/f.bin"))
    assert rf.size == len(DATA)
    rf.seek(100)
    assert rf.read(10) == DATA[100:110]
    gets = len([r for r in served.requests if r[0] == "GET"])
    assert rf.read(10) == DATA[110:120]                 # inside the block already fetched
    assert len([r for r in served.requests if r[0] == "GET"]) == gets
    rf.seek(-5, 2)
    assert rf.read() == DATA[-5:]
    rf.seek(3)
    rf.seek(4, 1)
    assert (rf.tell(), rf.read(2)) == (7, DATA[7:9])
    rf.seek(len(DATA))
    assert rf.read(10) == b""


def test_range_file_serves_a_zip_reader(served):
    rf = RangeFile(served.url("/f.bin"))
    buf = bytearray(8)
    assert rf.readinto(buf) == 8 and bytes(buf) == DATA[:8]


def test_server_that_ignores_range_fails_at_once(served):
    served.ignore_range = True
    with pytest.raises(HttpError, match="ignored Range"):
        rangehttp.fetch_range(served.url("/f.bin"), 0, 9)
    assert len(served.requests) == 1                    # not retried


def test_remote_size_needs_a_content_range(served):
    served.ignore_range = True
    with pytest.raises(HttpError, match="no Content-Range"):
        rangehttp.remote_size(served.url("/f.bin"))


def test_missing_file_is_a_404(served):
    with pytest.raises(urllib.error.HTTPError) as err:
        rangehttp.remote_size(served.url("/nope"))
    assert err.value.code == 404


def test_host_that_refuses_the_okhttp_profile_gets_another_user_agent(served):
    served.forbid_ua = "okhttp"
    assert rangehttp.fetch_range(served.url("/f.bin"), 0, 3) == DATA[:4]
    assert served.requests[0][3].startswith("okhttp") and served.requests[1][3].startswith("curl")
    rangehttp.fetch_range(served.url("/f.bin"), 4, 7)
    assert served.requests[2][3].startswith("curl")      # the working profile is remembered per host


def test_host_that_refuses_every_profile_raises_the_403(served):
    served.forbid_ua = ""                                # every user agent starts with ""
    with pytest.raises(urllib.error.HTTPError) as err:
        rangehttp.remote_size(served.url("/f.bin"))
    assert err.value.code == 403


@pytest.mark.parametrize("url", ["file:///etc/hostname", "ftp://example.invalid/x.zip", "/etc/hostname"])
def test_only_http_urls_are_fetched(url):
    with pytest.raises(HttpError, match="unsupported URL scheme"):
        rangehttp.fetch_range(url, 0, 9)
    with pytest.raises(HttpError, match="unsupported URL scheme"):
        rangehttp.remote_size(url)


def test_extraction_refuses_a_non_http_url():
    res = extract.extract("file:///etc/hostname")
    assert not res.ok and "unsupported URL scheme" in res.error


def _busy(code=503):
    # Python 3.14 warns about an HTTPError nobody closed (the code closes the ones it gets from a real server)
    err = urllib.error.HTTPError("http://example.invalid/f", code, "Service Temporarily Unavailable", {}, io.BytesIO())
    err.close()
    return err


def test_busy_server_is_given_time_and_more_attempts(served, monkeypatch):
    waits, real_open, answers = [], rangehttp._open, [_busy(), _busy(429), _busy(), _busy()]

    def flaky(url, rng, timeout):
        if answers:
            raise answers.pop(0)
        return real_open(url, rng, timeout)

    monkeypatch.setattr(rangehttp, "_open", flaky)
    monkeypatch.setattr(rangehttp.time, "sleep", waits.append)
    assert rangehttp.fetch_range(served.url("/f.bin"), 0, 9) == DATA[:10]      # the fifth attempt, past the usual three
    assert waits == [4.0, 8.0, 12.0, 16.0]


def test_busy_server_that_never_answers_ends_in_an_error_naming_the_host(monkeypatch):
    monkeypatch.setattr(rangehttp, "_open", lambda *a: (_ for _ in ()).throw(_busy()))
    monkeypatch.setattr(rangehttp.time, "sleep", lambda s: None)
    with pytest.raises(HttpError, match=r"example\.invalid: HTTP Error 503"):
        rangehttp.fetch_range("http://example.invalid/f", 0, 9)


def test_other_failures_keep_the_three_attempts(monkeypatch):
    calls = []

    def refuse(*a):
        calls.append(1)
        raise ConnectionResetError("reset")

    monkeypatch.setattr(rangehttp, "_open", refuse)
    monkeypatch.setattr(rangehttp.time, "sleep", lambda s: None)
    with pytest.raises(HttpError):
        rangehttp.fetch_range("http://example.invalid/f", 0, 9)
    assert len(calls) == 3


def test_size_probe_waits_for_a_busy_server(served, monkeypatch):
    waits, real_open, answers = [], rangehttp._open, [_busy(), _busy(429)]

    def flaky(url, rng, timeout):
        if answers:
            raise answers.pop(0)
        return real_open(url, rng, timeout)

    monkeypatch.setattr(rangehttp, "_open", flaky)
    monkeypatch.setattr(rangehttp.time, "sleep", waits.append)
    assert rangehttp.remote_size(served.url("/f.bin")) == len(DATA)
    assert waits == [4.0, 8.0]


def test_size_probe_gives_up_on_a_server_that_stays_busy(monkeypatch):
    monkeypatch.setattr(rangehttp, "_open", lambda *a: (_ for _ in ()).throw(_busy()))
    monkeypatch.setattr(rangehttp.time, "sleep", lambda s: None)
    with pytest.raises(urllib.error.HTTPError, match="503"):
        rangehttp.remote_size("http://example.invalid/f")
