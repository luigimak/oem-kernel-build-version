"""Extra release sources: Oxygen Updater API (latest firmware per device/region) and
antirollchecker's database (md5 index + gap check). All public, read-only, low volume."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from . import catalog, normalize

OU_BASE = "https://oxygenupdater.com/api/v2.10/"
OU_HEADERS = {"User-Agent": "Oxygen_updater_7.1.0"}
ARB_DB = "https://raw.githubusercontent.com/Bartixxx32/OnePlus-antirollchecker/main/data/database.json"


def _get(url: str, headers: dict, timeout: float = 40):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
        return json.load(r)


def _warn(title: str, msg: str) -> None:
    """Visible without failing the run: a workflow annotation on GitHub Actions, else a line on stderr."""
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::warning title={title}::{msg}")
    else:
        print(f"warning: {msg}", file=sys.stderr)


def ou_releases(workers: int = 6) -> list[dict]:
    """Latest *full* firmware of every OnePlus device/region known to Oxygen Updater (Android 14+ only)."""
    devices = _get(OU_BASE + "devices/all", OU_HEADERS)
    todo = []
    for d in devices:
        name = d.get("name", "")
        if not name.lower().startswith("oneplus"):
            continue
        base = re.sub(r"\s*\(.*\)\s*$", "", name)
        device = normalize.device_from_name(base)
        if not catalog.is_oneplus({"device": device}):
            continue
        m = re.search(r"\((.*)\)\s*$", name)
        todo.append((d["id"], device, m.group(1) if m else "GLO"))

    failed: list[str] = []

    def work(t):
        did, device, region = t
        out = []
        try:
            for meth in _get(f"{OU_BASE}updateMethods/{did}", OU_HEADERS):
                if "full" not in meth["name"].lower():
                    continue
                u = _get(f"{OU_BASE}mostRecentUpdateData/{did}/{meth['id']}", OU_HEADERS)
                ver, url = u.get("version_number"), u.get("download_url")
                if not ver or not url or not catalog.wanted_version(ver):
                    continue
                ota = u.get("ota_version_number") or ver
                model = ver.split("_")[0]
                key = "|".join((model, ota, region))
                out.append({
                    "id": "ou-" + hashlib.sha1(key.encode(), usedforsecurity=False).hexdigest()[:20], "device": device,
                    "region": region, "model": model, "version": ver, "ota_version": ota,
                    "build_timestamp": normalize.ota_timestamp(ota), "source_url": url, "md5": u.get("md5sum") or "",
                    "size": int(u.get("download_size") or 0), "is_latest": True, "origin": "oxygen-updater"})
        except Exception as e:  # noqa: BLE001 - one device failing must not stop the others
            failed.append(f"{device} {region}: {type(e).__name__}")
        return out

    with ThreadPoolExecutor(workers) as ex:
        found = [r for part in ex.map(work, todo) for r in part]
    if failed:
        _warn("Oxygen Updater", f"Oxygen Updater: {len(failed)} of {len(todo)} devices could not be read "
                                f"({'; '.join(sorted(failed))})")
    return found


def arb_index() -> dict:
    """{(version, region): md5} from antirollchecker's database.json."""
    db = _get(ARB_DB, {"User-Agent": "Mozilla/5.0"}, timeout=90)
    idx = {}
    for entry in db.values():
        for ver, v in (entry.get("versions") or {}).items():
            if not v.get("md5"):
                continue
            for region in v.get("regions") or []:
                idx[(ver, region)] = v["md5"]
    return idx
