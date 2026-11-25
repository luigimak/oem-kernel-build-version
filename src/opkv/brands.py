"""The brands whose firmware is tracked: one results file per brand, each with its own sources."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from . import catalog, normalize

PULSE = "https://raw.githubusercontent.com/RemuruSama/OTA-Pulse/main/devices/"


@dataclass(frozen=True)
class Brand:
    key: str                                # data/<key>.json, data/<key>.md
    label: str                              # the `brand` of every results row
    prefix: str                             # catalogs and sources start a device name with it ("OP 13R"), results rows leave it out
    matches: Callable[[dict], bool]         # does a release / {"device": ...} belong to the brand (and is it wanted)
    pulse: str                              # OTA Pulse model list
    ou_prefix: str                          # Oxygen Updater device names start with it (lower case)
    violet: str                             # brand name in the VioletToolBox ROM API
    archive: bool = False                   # spike0en/oneplus_archive only has OnePlus firmware

    def short(self, name: str) -> str:
        """Device name of a catalog or a source ("OP 13R", "realme 16 Pro") -> device of a results row ("13R", "16 PRO")."""
        name = normalize.device(name)
        return name[len(self.prefix):] if name.upper().startswith(self.prefix.upper()) else name

    def full(self, device: str) -> str:
        """Device of a results row -> the name catalogs and sources use, the one `matches` recognizes."""
        return self.prefix + device

    def adopt(self, row: dict) -> dict:
        """A results row in the current layout: `brand` right after the id, `device` without the brand prefix.
        A file written before the brand field existed holds the prefixed device; the current layout passes unchanged."""
        return {"id": row["id"], "brand": self.label, **row, "device": self.short(row["device"])}


BRANDS = {b.key: b for b in (
    Brand("oneplus", "OnePlus", "OP ", catalog.is_oneplus, PULSE + "oneplus.json", "oneplus", "OnePlus", archive=True),
    Brand("oppo", "OPPO", "OPPO ", catalog.is_oppo, PULSE + "oppo.json", "oppo", "OPPO"),
    Brand("realme", "Realme", "Realme ", catalog.is_realme, PULSE + "realme.json", "realme", "realme"),
)}


def select(key: str) -> list[Brand]:
    return list(BRANDS.values()) if key == "all" else [BRANDS[key]]


def of_release(rel: dict) -> Brand | None:
    return next((b for b in BRANDS.values() if b.matches(rel)), None)
