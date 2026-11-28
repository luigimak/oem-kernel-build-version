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
    pulse: str = ""                         # OTA Pulse model list (OnePlus, OPPO and Realme only; empty = not queried)
    ou_prefix: str = ""                     # Oxygen Updater device names start with it (lower case; empty = not listed there)
    violet: str = ""                        # brand name in the VioletToolBox ROM API (empty = not listed there)
    archive: str = ""                       # spike0en GitHub repo with the boot images of its firmware (OnePlus, Nothing)
    lolinet: str = ""                       # directory of the lolinet mirror that lists its firmware (Motorola, Lenovo)

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
    Brand("oneplus", "OnePlus", "OP ", catalog.is_oneplus, PULSE + "oneplus.json", "oneplus", "OnePlus",
          archive="spike0en/oneplus_archive"),
    Brand("oppo", "OPPO", "OPPO ", catalog.is_oppo, PULSE + "oppo.json", "oppo", "OPPO"),
    Brand("realme", "Realme", "Realme ", catalog.is_realme, PULSE + "realme.json", "realme", "realme"),
    Brand("xiaomi", "Xiaomi", "Xiaomi ", catalog.is_xiaomi),
    Brand("poco", "POCO", "POCO ", catalog.is_poco),
    Brand("redmi", "Redmi", "Redmi ", catalog.is_redmi),
    Brand("nothing", "Nothing", "Nothing ", catalog.is_nothing, archive="spike0en/nothing_archive"),
    Brand("motorola", "Motorola", "Motorola ", catalog.is_motorola, lolinet="/firmware/lenomola/"),
    Brand("lenovo", "Lenovo", "Lenovo ", catalog.is_lenovo, lolinet="/firmware/lenowow/"),
)}


def select(key: str) -> list[Brand]:
    return list(BRANDS.values()) if key == "all" else [BRANDS[key]]


def of_release(rel: dict) -> Brand | None:
    return next((b for b in BRANDS.values() if b.matches(rel)), None)
