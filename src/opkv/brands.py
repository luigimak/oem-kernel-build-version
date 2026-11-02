"""The brands whose firmware is tracked: one results file per brand, each with its own sources."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from . import catalog

PULSE = "https://raw.githubusercontent.com/RemuruSama/OTA-Pulse/main/devices/"


@dataclass(frozen=True)
class Brand:
    key: str                                # data/<key>.json, data/<key>.md
    label: str
    matches: Callable[[dict], bool]         # does a release / {"device": ...} belong to the brand (and is it wanted)
    pulse: str                              # OTA Pulse model list
    ou_prefix: str                          # Oxygen Updater device names start with it (lower case)
    archive: bool = False                   # spike0en/oneplus_archive only has OnePlus firmware


BRANDS = {b.key: b for b in (
    Brand("oneplus", "OnePlus", catalog.is_oneplus, PULSE + "oneplus.json", "oneplus", archive=True),
    Brand("oppo", "OPPO", catalog.is_oppo, PULSE + "oppo.json", "oppo"),
    Brand("realme", "Realme", catalog.is_realme, PULSE + "realme.json", "realme"),
)}


def select(key: str) -> list[Brand]:
    return list(BRANDS.values()) if key == "all" else [BRANDS[key]]


def of_release(rel: dict) -> Brand | None:
    return next((b for b in BRANDS.values() if b.matches(rel)), None)
