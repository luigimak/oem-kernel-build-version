"""Motorola and Lenovo firmware listed by the lolinet community mirror (mirrors.lolinet.com, an h5ai directory index).

The mirror says its files are collected from the Internet, not that they come from the manufacturers' servers. Its
packages are plain zips with a `boot.img` in them, so the kernel is read with HTTP Range like everywhere else.

Layout (a name carries what the release needs):
    Motorola  /firmware/lenomola/<year>/<codename>/official/<channel>/XT2611-3_AVR_RETEU_16_W3WW36.65-64-4_subsidy-....xml.zip
    Lenovo    /firmware/lenowow/<year>/<name>/<model>/TB390FU_ROW_OPEN_USER_Q00012.1_A16_ZUI_18.0.10.335_ST_260618.zip
Only the retail channels of Motorola (`RET*`: carrier builds are hundreds of near copies) and the Lenovo tablet zips are
listed. Every request is a small page, one at a time with a pause.
"""
from __future__ import annotations

import datetime
import hashlib
import html
import re
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass

from . import catalog, normalize
from .brands import Brand
from .rangehttp import check_scheme
from .safe import redact
from .sources import _warn

BASE = "https://mirrors.lolinet.com"
HEADERS = {"User-Agent": "opkv"}
FIRST_YEAR = 2022            # devices launched before can not run Android 14 firmware worth listing
_ROW = re.compile(r'<td class="fb-n"><a href="([^"]+)">([^<]*)</a></td><td class="fb-d">([^<]*)</td>')
# XT2611-3_AVR_RETEU_16_W3WW36.65-64-4_subsidy-DEFAULT_regulatory-DEFAULT_cid50_CFC.xml.zip
_MOTOROLA = re.compile(
    r"^(?P<model>XT[0-9A-Z-]+)_(?P<code>[A-Z0-9_]+?)_(?P<channel>RET[A-Z]*)_(?P<android>\d{1,2})_(?P<build>[A-Z0-9][\w.-]*?)_(?:subsidy|regulatory)-")
# TB390FU_ROW_OPEN_USER_Q00012.1_A16_ZUI_18.0.10.335_ST_260618.zip (the Android release is `A16` or a dessert letter: U = 14)
_LENOVO = re.compile(
    r"^(?P<model>TB[0-9A-Z]+)_(?P<region>ROW|CN|PRC)_OPEN_USER_.+?_(?:[TUVWX]|A\d{2})_(?:ZUI|ZUXOS)_[\d.]+_ST_\d{6}")


@dataclass(frozen=True)
class Entry:
    href: str
    name: str
    modified: datetime.date | None

    @property
    def is_dir(self) -> bool:
        return self.href.endswith("/")


def listing(path: str, pause: float = 0.4) -> list[Entry]:
    """The entries of a directory of the mirror (parent link left out); empty for a directory that does not exist."""
    time.sleep(pause)
    url = BASE + path
    check_scheme(url)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=40) as r:
            page = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        e.close()                                   # the error keeps its code; the connection goes
        if e.code == 404:
            return []
        raise
    out = []
    for m in _ROW.finditer(page):
        if m[1] == "..":
            continue
        try:
            modified = datetime.date.fromisoformat(m[3].strip()[:10])
        except ValueError:
            modified = None
        out.append(Entry(html.unescape(m[1]), html.unescape(m[2]), modified))
    return out


def _fresh(entry: Entry, since: datetime.date | None) -> bool:
    """Is the entry new enough to be looked at? (No cut-off, or no date to judge by: yes.)"""
    return since is None or entry.modified is None or entry.modified >= since


def _release(brand: Brand, device: str, model: str, region: str, version: str, name: str, href: str) -> dict:
    key = f"{version}|{region}"
    return {"id": "lol-" + hashlib.sha1(key.encode(), usedforsecurity=False).hexdigest()[:20], "device": brand.full(device),
            "region": region, "model": model, "version": version, "ota_version": name, "build_timestamp": "",
            "source_url": BASE + href, "md5": "", "size": 0, "is_latest": False, "origin": "lolinet"}


def motorola_release(brand: Brand, entry: Entry) -> dict | None:
    """Release of a Motorola package name: Android 14+ retail firmware only (None for anything else)."""
    m = _MOTOROLA.match(entry.name)
    if not m or not entry.name.endswith(".zip"):
        return None
    version = f"{m['model']}_{m['android']}_{m['build']}"
    if not catalog.wanted_version(version):
        return None
    return _release(brand, m["code"], m["model"], m["channel"], version, entry.name, entry.href)


def lenovo_release(brand: Brand, entry: Entry, device: str) -> dict | None:
    """Release of a Lenovo tablet package (a `.zip`: the `.7z` ones can not be read in part)."""
    m = _LENOVO.match(entry.name)
    if not m or not entry.name.endswith(".zip"):
        return None
    version = entry.name[:-4]
    if not catalog.wanted_version(version):
        return None
    return _release(brand, device.replace("_", " "), m["model"], m["region"], version, entry.name, entry.href)


def _walk(path: str, since: datetime.date | None, failed: list[str]) -> Iterator[Entry]:
    """The entries of a directory that are new enough; a listing that fails is reported at the end and skipped."""
    try:
        yield from (e for e in listing(path) if _fresh(e, since))
    except Exception as e:  # noqa: BLE001 - one directory failing must not stop the others
        failed.append(f"{path}: {type(e).__name__}")


def releases(brand: Brand, since: datetime.date | None = None) -> list[dict]:
    """Android 14+ releases of the brand on the mirror, one per firmware. With `since`, only what changed from that day
    on is looked at (directories and files carry their date), so a daily run asks for a handful of pages."""
    failed: list[str] = []
    out: dict[tuple[str, str], dict] = {}
    this_year = datetime.date.today().year
    for year in _walk(brand.lolinet, since, failed):
        if not (year.is_dir and year.name.strip("/").isdigit() and FIRST_YEAR <= int(year.name.strip("/")) <= this_year + 1):
            continue
        for device in _walk(year.href, since, failed):
            if not device.is_dir:
                continue
            places: list[tuple[Entry, str | None]]
            if brand.key == "motorola":
                places = [(c, None) for c in _walk(device.href + "official/", since, failed)
                          if c.is_dir and c.name.strip("/").startswith("RET")]          # carrier folders are not opened
            else:                                   # <name>/<model>/<files>
                places = [(m, device.name.strip("/")) for m in _walk(device.href, since, failed) if m.is_dir]
            for place, name in places:
                for f in _walk(place.href, since, failed):
                    rel = motorola_release(brand, f) if name is None else lenovo_release(brand, f, name)
                    if rel:
                        out.setdefault(normalize.firmware_key(rel), rel)
    if failed:
        _warn("lolinet", redact(f"lolinet: {len(failed)} directories not read ({'; '.join(failed[:3])}...)"))
    return list(out.values())
