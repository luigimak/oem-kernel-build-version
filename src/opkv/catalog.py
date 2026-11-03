"""Load catalog.json (releases list) and keep the entries of one brand (OnePlus, OPPO, Realme)."""
from __future__ import annotations

import json
import re
import urllib.request

from . import normalize

OLD_RE = re.compile(r"^OP (\d(?!\d)|ONE$|X$|NORD( 2| CE| N10| N100| N200)?$)")

MIN_ANDROID = 14                                  # only firmware from Android 14 onward
_VER = re.compile(r"^[A-Za-z0-9]+_(\d+)\.\d")     # CPH2653_16.0.10.600(EX01) -> 16


def os_major(version: str) -> int | None:
    """OS major of a firmware version string (OxygenOS/ColorOS 14+ = Android 14+); None for old formats."""
    m = _VER.match(version or "")
    return int(m.group(1)) if m else None


def wanted_version(version: str, android: str | None = None) -> bool:
    """True if the firmware is Android 14 or newer (Android from OTA metadata if known)."""
    if android:
        try:
            return int(android) >= MIN_ANDROID
        except ValueError:
            pass
    major = os_major(version)
    return major is not None and major >= MIN_ANDROID


def load(src: str) -> list[dict]:
    if src.startswith(("http://", "https://")):
        with urllib.request.urlopen(src, timeout=60) as r:
            data = json.load(r)
    else:
        with open(src, encoding="utf-8") as f:
            data = json.load(f)
    return data["releases"] if isinstance(data, dict) else data


def is_oneplus(rel: dict) -> bool:
    # catalog device names: "OP 13", "OP PAD3", "OP NORD 4", "OP OPEN" vs "OPPO ...", "Realme ..."
    d = rel.get("device", "").upper()
    if not d.startswith("OP ") or d.startswith("OPPO"):
        return False
    # old models excluded: OnePlus 9 and older (OP 9/8/7/..., Nord 1/2/N10/N100/CE 1)
    return not OLD_RE.match(d)


def is_oppo(rel: dict) -> bool:
    return rel.get("device", "").upper().startswith("OPPO ")


def is_realme(rel: dict) -> bool:
    return rel.get("device", "").upper().startswith("REALME ")


def brand_releases(src: str, matches) -> list[dict]:
    """Android 14+ releases with a download link whose device `matches`, one per firmware."""
    seen, out = set(), []
    for r in load(src):
        if not matches(r) or not r.get("source_url", "").startswith("http"):
            continue
        if not wanted_version(r.get("version", "")):
            continue
        key = normalize.firmware_key(r)         # the catalog can list one firmware under several ids
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out
