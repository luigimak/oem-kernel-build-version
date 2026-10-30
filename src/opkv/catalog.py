"""Load catalog.json (releases list) and keep OnePlus entries only."""
from __future__ import annotations

import json
import urllib.request


import re

OLD_RE = re.compile(r"^OP (\d(?!\d)|NORD( 2| CE| N10| N100| N200)?$)")


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


def oneplus_releases(src: str) -> list[dict]:
    seen, out = set(), []
    for r in load(src):
        if not is_oneplus(r) or not r.get("source_url", "").startswith("http"):
            continue
        key = r["id"]
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out
