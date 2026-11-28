"""Firmware from the spike0en archives (oneplus_archive, nothing_archive) releases: boot.7z -> boot.img -> Linux version.

An archive publishes one GitHub release per firmware with an `image-boot.7z` asset (about 50 MB).
Only releases whose (version, region) is missing from the results are processed.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import urllib.request

from . import bootimg, catalog
from .extract import Result, fill_banner
from .rangehttp import check_scheme
from .safe import redact

# OnePlus: CPH2653_16.0.10.600(EX01)_ROW
_TAG = re.compile(r"^(?P<version>[A-Za-z0-9]+_[\d.]+\([A-Z0-9]+\))_(?P<region>[A-Z]+)$")
# the archive labels the global package "ROW"; results use GLO
_REGION = {"ROW": "GLO"}
# Nothing: Tetris_B4.1-261028-1606 (codename, Nothing OS build, date and time); one global package per tag
_NOTHING_TAG = re.compile(r"^(?P<version>[A-Za-z]+_[A-Z]\d\.\d-\d{6}-\d{4})$")

# codename of a Nothing phone -> device label of the results (the codenames the archive uses)
NOTHING_DEVICES = {
    "Spacewar": "Phone (1)", "Pong": "Phone (2)", "Pacman": "Phone (2a)", "PacmanPro": "Phone (2a) Plus",
    "Asteroids": "Phone (3a)", "AsteroidsPro": "Phone (3a) Pro", "Metroid": "Phone (3)", "Galaxian": "Phone (3a) Lite",
    "Frogger": "Phone (4a)", "FroggerPro": "Phone (4a) Pro", "SuperContra": "Phone (4b)",
    "Tetris": "CMF Phone 1", "Galaga": "CMF Phone 2 Pro",
}


def devices(repo: str) -> dict[str, str]:
    """Model code (or codename) -> device label, for the archives whose release names say nothing but the codename."""
    return NOTHING_DEVICES if repo.endswith("nothing_archive") else {}


def parse_tag(repo: str, tag: str) -> tuple[str, str] | None:
    """(version, region) of a release tag of the archive, or None for a tag that names no firmware."""
    if repo.endswith("nothing_archive"):
        m = _NOTHING_TAG.match(tag)
        return (m["version"], "GLO") if m else None
    m = _TAG.match(tag)
    return (m["version"], _REGION.get(m["region"], m["region"])) if m else None


def _get(url: str, token: str | None = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "opkv", **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def releases(repo: str, token: str | None = None) -> list[dict]:
    """[{version, region, asset_url}] for every release of the archive `repo` that has a boot asset and is Android 14+."""
    out: list[dict] = []
    page = 1
    while True:
        batch = json.loads(_get(f"https://api.github.com/repos/{repo}/releases?per_page=100&page={page}", token))
        if not batch:
            return out
        for rel in batch:
            tag = parse_tag(repo, rel["tag_name"])
            boot = next((a for a in rel["assets"] if re.search(r"-(image-)?boot\.7z$", a["name"])), None)
            if tag and boot and catalog.wanted_version(tag[0]):
                out.append({"version": tag[0], "region": tag[1], "asset_url": boot["browser_download_url"]})
        page += 1


def extract_asset(url: str) -> Result:
    """Download a boot.7z asset to a temp dir, read boot.img, delete everything."""
    import py7zr
    res = Result(source="boot.img")
    try:
        check_scheme(url)
        with tempfile.TemporaryDirectory() as tmp:
            arc = os.path.join(tmp, "boot.7z")
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "opkv"}), timeout=120) as r, \
                    open(arc, "wb") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
                    res.bytes_fetched += len(chunk)
            with py7zr.SevenZipFile(arc) as z:
                name = bootimg.pick_boot_name(z.getnames())
                if not name:
                    raise ValueError("no boot.img in archive")
                z.extract(path=tmp, targets=[name])
            with open(os.path.join(tmp, name), "rb") as f:
                fill_banner(res, f.read())
        res.ok = True
    except Exception as e:  # noqa: BLE001 - per-asset error, keep batch going
        res.error = redact(f"{type(e).__name__}: {e}")
    return res
