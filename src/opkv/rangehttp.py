"""Seekable file-like backed by HTTP Range requests (stdlib only)."""
from __future__ import annotations

import io
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

HEADERS = {
    "User-Agent": "okhttp/3.12.12",
    "userId": "oplus-ota|16002018",
    "Accept": "*/*",
    "Accept-Encoding": "identity",
}
MIN_FETCH = 64 * 1024


class HttpError(Exception):
    pass


def check_scheme(url: str) -> None:
    """URLs come from third-party catalogs: only http(s) is fetched (urllib would also read file:// and ftp://)."""
    if urllib.parse.urlparse(url).scheme not in ("http", "https"):
        raise HttpError("unsupported URL scheme")


# bytes really received by the current thread: one extraction runs on one worker thread
_traffic = threading.local()


def reset_traffic() -> None:
    _traffic.requests = _traffic.bytes = 0


def traffic() -> tuple[int, int]:
    """(requests, bytes) received by the current thread since reset_traffic()."""
    return getattr(_traffic, "requests", 0), getattr(_traffic, "bytes", 0)


def _count(nbytes: int) -> None:
    _traffic.requests = getattr(_traffic, "requests", 0) + 1
    _traffic.bytes = getattr(_traffic, "bytes", 0) + nbytes


# some hosts (e.g. *-cn.allawnfs.com) answer 403 to the okhttp+userId profile but 206 to neutral UAs
PROFILES = [
    HEADERS,
    {"User-Agent": "curl/8.5.0", "Accept": "*/*"},
    {"User-Agent": "Dalvik/2.1.0 (Linux; U; Android 14; OnePlus)", "Accept": "*/*"},
]
_host_profile: dict[str, int] = {}


def _open(url: str, rng: str | None, timeout: float):
    check_scheme(url)
    host = urllib.parse.urlparse(url).netloc
    start = _host_profile.get(host, 0)
    for k in range(len(PROFILES)):
        idx = (start + k) % len(PROFILES)
        h = dict(PROFILES[idx])
        if rng:
            h["Range"] = rng
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout)
            _host_profile[host] = idx
            return r
        except urllib.error.HTTPError as e:
            e.close()                           # the error keeps its code and headers, the connection goes
            if e.code != 403 or k == len(PROFILES) - 1:
                raise                           # a 403 on every profile is the host's answer
    raise HttpError("no request profile")       # not reachable: the last profile returns or raises


def fetch_range(url: str, start: int, end: int, timeout: float = 60, retries: int = 3) -> bytes:
    """Fetch bytes [start, end] inclusive."""
    check_scheme(url)
    last: Exception | None = None
    for i in range(retries):
        try:
            with _open(url, f"bytes={start}-{end}", timeout) as r:
                if r.status != 206:
                    raise HttpError(f"server ignored Range (HTTP {r.status})")
                data = r.read()
            if len(data) != end - start + 1:
                raise HttpError(f"short read {len(data)} != {end - start + 1}")
            _count(len(data))
            return data
        except HttpError as e:
            last = e
            if "ignored Range" in str(e):
                break
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
        time.sleep(1.5 * (i + 1))
    raise HttpError(f"range [{start}-{end}] su {urllib.parse.urlparse(url).netloc}: {last}")


def remote_size(url: str, timeout: float = 30) -> int:
    with _open(url, "bytes=0-0", timeout) as r:
        cr = r.headers.get("Content-Range", "")
        if r.status == 206 and "/" in cr:
            _count(1)
            return int(cr.rsplit("/", 1)[1])
        raise HttpError(f"no Content-Range (HTTP {r.status})")


class RangeFile(io.RawIOBase):
    def __init__(self, url: str, size: int | None = None):
        self.url = url
        self.size = size if size is not None else remote_size(url)
        self.pos = 0
        self._cache_start = 0
        self._cache = b""

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos

    def seek(self, off, whence=io.SEEK_SET):
        if whence == io.SEEK_SET: self.pos = off
        elif whence == io.SEEK_CUR: self.pos += off
        else: self.pos = self.size + off
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        n = min(n, self.size - self.pos)
        if n <= 0:
            return b""
        lo, hi = self.pos, self.pos + n
        cs, ce = self._cache_start, self._cache_start + len(self._cache)
        if not (cs <= lo and hi <= ce):
            end = min(self.size, lo + max(n, MIN_FETCH))
            self._cache = fetch_range(self.url, lo, end - 1)
            self._cache_start = lo
            cs = lo
        out = self._cache[lo - cs: hi - cs]
        self.pos = hi
        return out

    def readinto(self, b):
        d = self.read(len(b))
        b[: len(d)] = d
        return len(d)
