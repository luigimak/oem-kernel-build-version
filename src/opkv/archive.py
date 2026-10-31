"""Historical firmware from the spike0en/oneplus_archive releases: boot.7z -> boot.img -> Linux version.

The archive publishes one GitHub release per firmware with an `image-boot.7z` asset (about 50 MB).
Only releases whose (model, version) is missing from the results are processed.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import urllib.request

from . import catalog
from .extract import Result, fill_banner
from .safe import redact

REPO = "spike0en/oneplus_archive"
_TAG = re.compile(r"^(?P<version>[A-Za-z0-9]+_[\d.]+\([A-Z0-9]+\))_(?P<region>[A-Z]+)$")
# the archive labels the global package "ROW"; results use GLO
_REGION = {"ROW": "GLO"}


def _get(url: str, token: str | None = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "opkv", **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def releases(token: str | None = None) -> list[dict]:
    """[{version, region, asset_url}] for every archive release that has a boot asset and is Android 14+."""
    out, page = [], 1
    while True:
        batch = json.loads(_get(f"https://api.github.com/repos/{REPO}/releases?per_page=100&page={page}", token))
        if not batch:
            return out
        for rel in batch:
            m = _TAG.match(rel["tag_name"])
            boot = next((a for a in rel["assets"] if re.search(r"-(image-)?boot\.7z$", a["name"])), None)
            if m and boot and catalog.wanted_version(m["version"]):
                out.append({"version": m["version"], "region": _REGION.get(m["region"], m["region"]),
                            "asset_url": boot["browser_download_url"]})
        page += 1


def extract_asset(url: str) -> Result:
    """Download a boot.7z asset to a temp dir, read boot.img, delete everything."""
    import py7zr
    res = Result(source="boot.img")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            arc = os.path.join(tmp, "boot.7z")
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "opkv"}), timeout=120) as r, \
                    open(arc, "wb") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
                    res.bytes_fetched += len(chunk)
            with py7zr.SevenZipFile(arc) as z:
                names = [n for n in z.getnames() if n.endswith("boot.img") and "vendor_boot" not in n and "init_boot" not in n]
                if not names:
                    raise ValueError("no boot.img in archive")
                z.extract(path=tmp, targets=names[:1])
            with open(os.path.join(tmp, names[0]), "rb") as f:
                fill_banner(res, f.read())
        res.ok = True
    except Exception as e:  # noqa: BLE001 - per-asset error, keep batch going
        res.error = redact(f"{type(e).__name__}: {e}")
    return res
