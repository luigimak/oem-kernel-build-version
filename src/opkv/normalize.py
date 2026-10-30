"""Normalization of device/model names coming from third-party catalogs (typos, spacing)."""
import re

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


def device(name: str) -> str:
    """OP PAD2 PRO -> OP PAD 2 PRO, OP NORD CE4 LITE -> OP NORD CE 4 LITE."""
    return re.sub(r"\b(PAD|CE)(\d)", r"\1 \2", name.strip())


def row(r: dict) -> dict:
    r["model"], r["version"], r["device"] = model(r["model"]), version(r["version"]), device(r["device"])
    return r
