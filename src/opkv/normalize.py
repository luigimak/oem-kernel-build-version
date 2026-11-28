"""Normalization of device/model names coming from third-party catalogs (typos, spacing)."""
import re
from collections import Counter

# model codes seen in the wild: CPH2645, PLK110, PJZ110, PGKM10, OPD2403, NE2210
_MODEL = re.compile(r"^(CPH\d{4}|P[A-Z]{2}\d{3}|P[A-Z]{3}\d{2}|OPD\d{4}|NE\d{4})$")


def model(code: str) -> str:
    """CCPH2645 -> CPH2645, PPKX110 -> PKX110 (duplicated first letter)."""
    if len(code) > 1 and code[0] == code[1] and not _MODEL.match(code) and _MODEL.match(code[1:]):
        return code[1:]
    return code


def version(v: str) -> str:
    """Fix the model prefix of a firmware version (PPKX110_15.0.2.603(CN01))."""
    head, sep, tail = v.partition("_")
    return model(head) + sep + tail


# brands whose catalogs spell the name and the rest of the device any way: the brand gets its own spelling, the rest upper case
_SPELLING = {"REALME ": "Realme ", "XIAOMI ": "Xiaomi ", "REDMI ": "Redmi ", "POCO ": "POCO ",
             "MOTOROLA ": "Motorola ", "LENOVO ": "Lenovo "}


def device(name: str) -> str:
    """OP PAD2 PRO -> OP PAD 2 PRO, OP NORD CE4 LITE -> OP NORD CE 4 LITE, realme 16 Pro -> Realme 16 PRO,
    REDMI Note 15 Pro -> Redmi NOTE 15 PRO."""
    name = name.strip()
    for prefix, spelling in _SPELLING.items():
        if name.upper().startswith(prefix):
            name = spelling + name[len(prefix):].upper()
            break
    return re.sub(r"\b(PAD|CE)(\d)", r"\1 \2", name)


def device_from_name(name: str) -> str:
    """Name of a device in another source ("OnePlus Pad2 Pro") -> the catalog's naming ("OP PAD 2 PRO")."""
    return device(name.upper().replace("ONEPLUS", "OP"))


def model_of(r: dict) -> str:
    """Model code of a release/row: the prefix of its firmware version, else its model field."""
    head, sep, _ = version(r.get("version", "")).partition("_")
    return head if sep else model(r.get("model", ""))


def labels_by_model(rows) -> dict[str, str]:
    """Most common device label per model code: sources name the same hardware differently
    (OTA Pulse lists the OnePlus 13 model under "OnePlus 13s"), the majority is the catalog's naming."""
    votes: dict[str, Counter] = {}
    for r in rows:
        if r.get("device"):
            votes.setdefault(model_of(r), Counter())[device(r["device"])] += 1
    return {m: c.most_common(1)[0][0] for m, c in votes.items()}


def ota_timestamp(ota_version: str) -> str:
    """CPH2745_11.A.75_1750_202610181120 -> 2026-10-18T11:20:00 (empty when the version has no build stamp)."""
    m = re.search(r"_(\d{12})$", ota_version or "")
    if not m:
        return ""
    t = m.group(1)
    return f"{t[:4]}-{t[4:6]}-{t[6:8]}T{t[8:10]}:{t[10:12]}:00"


_MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
_BUILD_DATE = re.compile(r"([A-Z][a-z]{2}) +(\d{1,2}) (\d\d:\d\d:\d\d) \w+ (\d{4})\s*$")


def build_date(build: str) -> str:
    """Date of a kernel build string ("#1 SMP PREEMPT Mon Dec 25 12:31:09 UTC 2023") as 2023-12-25T12:31:09;
    empty when there is none. Locale independent."""
    m = _BUILD_DATE.search(build or "")
    if not m or m[1] not in _MONTHS:
        return ""
    return f"{m[4]}-{_MONTHS[m[1]]:02d}-{int(m[2]):02d}T{m[3]}"


def firmware_key(r: dict) -> tuple[str, str]:
    """Identity of a firmware across sources and ids: (version, region).

    The version string already starts with the model code, and the same package shows up under
    different ids and OTA version letters depending on the source (catalog, OTA query, Oxygen Updater).
    """
    return version(r.get("version", "")), r.get("region", "")


def row(r: dict) -> dict:
    r["version"], r["device"] = version(r["version"]), device(r["device"])
    r["model"] = model_of(r)                 # the firmware version names its model; catalogs sometimes disagree
    return r


def _quality(r: dict) -> tuple:
    """Sort key: the higher, the better row to keep among duplicates of one firmware."""
    return (bool(r.get("ok")), bool(r.get("md5")), bool(r.get("size")), bool(r.get("android_version")),
            bool(r.get("build_timestamp")), r.get("origin") in (None, "catalog"))


def dedupe(rows: dict[str, dict]) -> list[str]:
    """Keep one row per firmware: the best one, the first on a tie. Returns the ids dropped."""
    best: dict[tuple[str, str], str] = {}
    for i, r in rows.items():
        k = firmware_key(r)
        if k not in best or _quality(r) > _quality(rows[best[k]]):
            best[k] = i
    keep = set(best.values())
    dropped = [i for i in rows if i not in keep]
    for i in dropped:
        del rows[i]
    return dropped


def relabel(rows) -> None:
    """Give every row of a model code the most common device label of that model."""
    rows = list(rows)
    labels = labels_by_model(rows)
    for r in rows:
        if r.get("device"):
            r["device"] = labels[model_of(r)]


# the letter that opens the last field of a Xiaomi version (OS3.0.336.0.XOSRUXM) and of a Nothing or Pixel build (B4.1-...)
# is the Android dessert initial: T = 13, U = 14, V = 15, W = 16, X = 17 (Xiaomi); T, U, V, B = 16, C = 17 (Nothing)
_XIAOMI = re.compile(r"^(?:OS|V)\d+(?:\.\d+){3}\.([A-Z])[A-Z]{2,}")
_NOTHING = re.compile(r"^[A-Za-z]+_([TUVBC])\d\.\d-\d{6}-\d{4}$")
_NOTHING_ANDROID = {"T": 13, "U": 14, "V": 15, "B": 16, "C": 17}
# Motorola: XT2611-3_16_W3WW36.65-64-4 (model, Android release, build); Lenovo: TB390FU_ROW_OPEN_USER_Q00012.1_A16_ZUI_18.0.10.335_ST_260618
# (the release is `A16` or a dessert letter: T = 13, U = 14, V = 15, W = 16)
_MOTOROLA = re.compile(r"^XT[0-9A-Z-]+_(\d{1,2})_")
_LENOVO = re.compile(r"^TB[0-9A-Z]+_(?:ROW|CN|PRC)_OPEN_USER_.+?_(?:([TUVWX])|A(\d{2}))_(?:ZUI|ZUXOS)_")


def other_android(version: str) -> int | None:
    """Android release of a firmware version that does not follow the OxygenOS/ColorOS scheme (Xiaomi HyperOS, Nothing OS,
    Motorola, Lenovo)."""
    m = _XIAOMI.match(version or "")
    if m:
        return ord(m[1]) - ord("A") - 6
    m = _NOTHING.match(version or "")
    if m:
        return _NOTHING_ANDROID[m[1]]
    m = _MOTOROLA.match(version or "")
    if m:
        return int(m[1])
    m = _LENOVO.match(version or "")
    if m:
        return int(m[2]) if m[2] else ord(m[1]) - ord("A") - 6
    return None


def android(r: dict) -> str | None:
    """Android release of a firmware row: from the OTA metadata, else inferred from the OS version.

    Fallback: for OxygenOS/ColorOS 13+ the major number of the version string (CPH2465_14.0.0.1320)
    equals the Android release; this held for every firmware that has OTA metadata.
    """
    if r.get("android_version"):
        return r["android_version"]
    m = re.match(r"^[A-Z0-9]+_(1[3-9])\.\d", r.get("version", ""))
    if m:
        return m.group(1)
    other = other_android(r.get("version", ""))
    return str(other) if other else None
