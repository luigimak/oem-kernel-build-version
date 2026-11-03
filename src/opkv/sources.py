"""Extra release sources: Oxygen Updater API (latest firmware per device/region), the VioletToolBox ROM API
(older Chinese-market firmware) and antirollchecker's database (md5 index). All public, read-only, low volume."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from . import catalog, normalize
from .brands import Brand

OU_BASE = "https://oxygenupdater.com/api/v2.10/"
OU_HEADERS = {"User-Agent": "Oxygen_updater_7.1.0"}
VT_BASE = "https://violettool.top/rom-api"
VT_HEADERS = {"User-Agent": "opkv"}
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


def ou_releases(brand: Brand, workers: int = 6) -> list[dict]:
    """Latest *full* firmware of every device/region of the brand known to Oxygen Updater (Android 14+ only)."""
    devices = _get(OU_BASE + "devices/all", OU_HEADERS)
    todo = []
    for d in devices:
        name = d.get("name", "")
        if not name.lower().startswith(brand.ou_prefix):
            continue
        base = re.sub(r"\s*\(.*\)\s*$", "", name)
        device = normalize.device_from_name(base)
        if not brand.matches({"device": device}):
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


# "ColorOS PHN110_14.0.0.850(CN01) C.22", "RealmeUI RMX5010_15.0.0.500(CN01) A.48", "OPD2601_16.0.10.600(CN01)"
_VT_VERSION = re.compile(r"(?P<version>(?P<model>[A-Za-z0-9]+)_\d+\.\d+\.\d+\.\d+\(CN\d+\))(?:\s+(?P<letter>[A-Z])\.(?P<build>\d+))?")
_VT_TAG = re.compile(r"^\[[^\]]*\]\s*")                  # "[普通]", "[C16动态解析]"
_VT_CODE = re.compile(r"\s*[(\uff08][A-Z0-9]+[)\uff09]\s*$")      # trailing model code, with ASCII or fullwidth parentheses
_CJK = re.compile(r"[\u3000-\u9fff\uff00-\uffef]")


def violet_version(name: str) -> dict | None:
    """Firmware of a VioletToolBox version name: {version, model, ota_version}; None unless it is a Chinese-market
    (CNxx) firmware, the only region the service lists with its real name."""
    m = _VT_VERSION.search(name)
    if not m:
        return None
    ota = f"{m['model']}_11.{m['letter']}.{m['build']}" if m["letter"] else m["version"]
    return {"version": m["version"], "model": m["model"], "ota_version": ota}


def violet_device(raw: str) -> str:
    """Device label from a VioletToolBox device name (a tag, Chinese words, the model code in parentheses): -> "Realme GT7 PRO"."""
    name = _CJK.sub("", _VT_CODE.sub("", _VT_TAG.sub("", raw)))
    return normalize.device_from_name(re.sub(r"\s+", " ", name).strip())


def violet_releases(brand: Brand, pause: float = 0.3) -> list[dict]:
    """Chinese-market firmware (Android 14+) the VioletToolBox community service lists for the brand. A release has
    no link but a `violet` reference: the links last only minutes, so `violet_link` asks for one right before the
    package is read. One request at a time, with a pause: the service asks for moderate use. Unreadable parts are
    reported and skipped."""
    def get(path: str, **query):
        time.sleep(pause)
        return _get(f"{VT_BASE}/{path}?{urllib.parse.urlencode(query)}", VT_HEADERS)

    out: list[dict] = []
    seen: set[str] = set()
    failed: list[str] = []
    try:
        series = get("series", packageType="full", brand=brand.violet)["items"]
    except Exception as e:  # noqa: BLE001 - a source that is down must not stop the run
        _warn("VioletToolBox", f"VioletToolBox: {brand.label} not read ({type(e).__name__})")
        return out
    for ser in series:
        try:
            devices = get("devices", packageType="full", brand=brand.violet, series=ser)["items"]
        except Exception as e:  # noqa: BLE001
            failed.append(f"{ser}: {type(e).__name__}")
            continue
        for raw in devices:
            device = violet_device(raw)
            if not brand.matches({"device": device}):
                continue
            try:
                names = [x["name"] for x in get("versions", packageType="full", brand=brand.violet, series=ser,
                                               device=raw)["items"]]
                for name in names:
                    fw = violet_version(name)
                    if not fw or fw["version"] in seen or not catalog.wanted_version(fw["version"]):
                        continue
                    seen.add(fw["version"])
                    rel = {"id": "vt-" + hashlib.sha1(f"{fw['version']}|CN".encode(), usedforsecurity=False).hexdigest()[:20],
                           "device": device, "region": "CN", "model": fw["model"], "version": fw["version"],
                           "ota_version": fw["ota_version"], "build_timestamp": normalize.ota_timestamp(fw["ota_version"]),
                           "source_url": "", "md5": "", "size": 0, "origin": "violettoolbox",
                           "violet": {"brand": brand.violet, "series": ser, "device": raw, "name": name}}
                    out.append(rel)
            except Exception as e:  # noqa: BLE001
                failed.append(f"{device}: {type(e).__name__}")
    if failed:
        _warn("VioletToolBox", f"VioletToolBox: {len(failed)} parts of {brand.label} could not be read ({'; '.join(failed[:8])})")
    return out


def violet_link(ref: dict) -> str:
    """Download link of the version a `violet` reference names, or "" when the service has none. The link is used
    in memory only and expires within minutes."""
    body = json.dumps({"packageType": "full", "brand": ref["brand"], "series": ref["series"], "device": ref["device"],
                       "version": ref["name"]}).encode()
    req = urllib.request.Request(VT_BASE + "/download-link", data=body,
                                 headers={**VT_HEADERS, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            links = json.load(r).get("links") or []
    except Exception:  # noqa: BLE001 - no link: the firmware is listed but cannot be read
        return ""
    return next((link for link in links if isinstance(link, str) and link.startswith("http")), "")


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
