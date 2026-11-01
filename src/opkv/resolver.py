# Derived from OTA Pulse (https://github.com/RemuruSama/OTA-Pulse), Copyright 2026 OTA Pulse,
# licensed under the Apache License, Version 2.0 (see LICENSE).
# Modified: translated from Kotlin to Python (OtaResolver.kt; redirect resolution only).
"""OTA resolver (port of OtaResolver.kt): catalog/OTA link -> final CDN URL, in memory ONLY.

The result must never be saved, logged or committed.
"""
from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request

from .rangehttp import HEADERS, HttpError

MAX_REDIRECTS = 10


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def _probe(url: str, headers: dict, method: str, timeout: float):
    opener = urllib.request.build_opener(_NoRedirect)
    h = dict(headers)
    if method == "GET":
        h["Range"] = "bytes=0-0"
    try:
        return opener.open(urllib.request.Request(url, headers=h, method=method), timeout=timeout)
    except urllib.error.HTTPError as e:  # with NoRedirect, 3xx/4xx land here
        return e


def resolve(url: str, timeout: float = 20) -> str:
    """Follow redirects (HEAD, GET Range fallback) and return the final URL."""
    url = url.replace("\\u0026", "&")
    if not url.startswith("http"):
        return url
    for _ in range(MAX_REDIRECTS):
        r = _probe(url, HEADERS, "HEAD", timeout)
        if r.code in (403, 405, 501):
            r.close()
            r = _probe(url, HEADERS, "GET", timeout)
        try:
            if r.code in (301, 302, 303, 307, 308):
                loc = r.headers.get("Location")
                if not loc:
                    raise HttpError("redirect without Location")
                url = urllib.parse.urljoin(url, loc)
                continue
            return url
        finally:
            r.close()
    raise HttpError("too many redirects")
