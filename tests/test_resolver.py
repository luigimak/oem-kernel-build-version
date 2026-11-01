import pytest

from opkv import resolver
from opkv.rangehttp import HttpError


def test_redirects_are_followed_to_the_final_url(http_server):
    http_server.files["/final.zip"] = b"x"
    http_server.redirects = {"/a": "/b", "/b": "/final.zip"}          # a relative Location, twice
    assert resolver.resolve(http_server.url("/a")) == http_server.url("/final.zip")


def test_url_without_redirect_is_returned_as_is(http_server):
    http_server.files["/f.zip"] = b"x"
    assert resolver.resolve(http_server.url("/f.zip")) == http_server.url("/f.zip")


def test_head_refused_falls_back_to_a_ranged_get(http_server):
    http_server.files["/f.zip"] = b"xyz"
    http_server.head_status = 405
    assert resolver.resolve(http_server.url("/f.zip")) == http_server.url("/f.zip")
    assert [(r[0], r[2]) for r in http_server.requests] == [("HEAD", None), ("GET", "bytes=0-0")]


def test_redirect_loop_is_reported(http_server):
    http_server.redirects = {"/a": "/a"}
    with pytest.raises(HttpError, match="too many redirects"):
        resolver.resolve(http_server.url("/a"))


def test_redirect_without_location_is_reported(http_server):
    http_server.redirects = {"/a": None}
    with pytest.raises(HttpError, match="redirect without Location"):
        resolver.resolve(http_server.url("/a"))


def test_json_escaped_ampersands_are_unescaped(http_server):
    http_server.files["/f.zip"] = b"x"
    assert resolver.resolve(http_server.url("/f.zip?a=1\\u0026b=2")) == http_server.url("/f.zip?a=1&b=2")


def test_non_http_links_are_returned_unchanged():
    assert resolver.resolve("file:///tmp/a.zip") == "file:///tmp/a.zip"
