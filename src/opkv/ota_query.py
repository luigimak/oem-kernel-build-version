# Derived from OTA Pulse (https://github.com/RemuruSama/OTA-Pulse), Copyright 2026 OTA Pulse,
# licensed under the Apache License, Version 2.0 (see LICENSE).
# Modified: translated from Kotlin to Python (Request.kt, Crypto.kt, Data.kt, RegionData.kt; protocol v2 only, standalone client).
"""Native OTA query (port of OTA Pulse Request.kt / Crypto.kt / Data.kt, protocol v2).

Asks the OTA servers for the latest full firmware of a (model, region). The returned URLs are
temporary: they only live in memory / in the git-ignored local catalog.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.serialization import load_der_public_key

# --- Data.kt ----------------------------------------------------------------
DEFAULT_HEADERS = {
    "language": "en-EN", "romVersion": "unknown", "otaVersion": "unknown",
    "androidVersion": "unknown", "colorOSVersion": "unknown", "model": "unknown",
    "infVersion": "1", "operator": "unknown", "nvCarrier": "unknown",
    "uRegion": "unknown", "trackRegion": "unknown", "imei": "000000000000000",
    "imei1": "000000000000000", "deviceId": "0", "mode": "client_auto",
    "channel": "pc", "version": "1", "Accept": "application/json",
    "Content-Type": "application/json", "User-Agent": "NULL",
}
DEFAULT_BODY = {
    "language": "en-EN", "romVersion": "unknown", "otaVersion": "unknown",
    "androidVersion": "unknown", "colorOSVersion": "unknown", "model": "unknown",
    "productName": "unknown", "operator": "unknown", "uRegion": "unknown",
    "trackRegion": "unknown", "imei": "000000000000000", "imei1": "000000000000000",
    "mode": "0", "registrationId": "unknown", "deviceId": "0", "version": "3",
    "type": "1", "otaPrefix": "unknown", "isRealme": "unknown", "time": "0",
    "canCheckSelf": "0", "gray": "0", "reqMode": "manual",
}
# region idx -> (url, pubkey b64, negotiationVersion)
SERVERS = {
    0: ("https://component-otapc-sg.allawnos.com/update/v3", "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAkA980wxi+eTGcFDiw2I6RrUeO4jL/Aj3Yw4dNuW7tYt+O1sRTHgrzxPD9SrOqzz7G0KgoSfdFHe3JVLPN+U1waK+T0HfLusVJshDaMrMiQFDUiKajb+QKr+bXQhVofH74fjat+oRJ8vjXARSpFk4/41x5j1Bt/2bHoqtdGPcUizZ4whMwzap+hzVlZgs7BNfepo24PWPRujsN3uopl+8u4HFpQDlQl7GdqDYDj2zNOHdFQI2UpSf0aIeKCKOpSKF72KDEESpJVQsqO4nxMwEi2jMujQeCHyTCjBZ+W35RzwT9+0pyZv8FB3c7FYY9FdF/+lvfax5mvFEBd9jO+dpMQIDAQAB", "1615895993238"),
    1: ("https://component-otapc-cn.allawntech.com/update/v3", "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEApXYGXQpNL7gmMzzvajHaoZIHQQvBc2cOEhJc7/tsaO4sT0unoQnwQKfNQCuv7qC1Nu32eCLuewe9LSYhDXr9KSBWjOcCFXVXteLO9WCaAh5hwnUoP/5/Wz0jJwBA+yqs3AaGLA9wJ0+B2lB1vLE4FZNE7exUfwUc03fJxHG9nCLKjIZlrnAAHjRCd8mpnADwfkCEIPIGhnwq7pdkbamZcoZfZud1+fPsELviB9u447C6bKnTU4AaMcR9Y2/uI6TJUTcgyCp+ilgU0JxemrSIPFk3jbCbzamQ6Shkw/jDRzYoXpBRg/2QDkbq+j3ljInu0RHDfOeXf3VBfHSnQ66HCwIDAQAB", "1615879139745"),
    2: ("https://component-otapc-in.allawnos.com/update/v3", "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAwYtghkzeStC9YvAwOQmWylbp74Tj8hhi3f9IlK7A/CWrGbLgzz/BeKxNb45zBN8pgaaEOwAJ1qZQV5G4nProWCPOP1ro1PkemFJvw/vzOOT5uN0ADnHDzZkZXCU/knxqUSfLcwQlHXsYhNsAm7uOKjY9YXF4zWzYN0eFPkML3Pj/zg7hl/ov9clB2VeyI1/blMHFfcNA/fvqDTENXcNBIhgJvXiCpLcZqp+aLZPC5AwY/sCb3j5jTWer0Rk0ZjQBZE1AncwYvUx4mA65U59cWpTyl4c47J29MsQ66hqWv6eBHlDNZSEsQpHePUqgsf7lmO5Wd7teB8ugQki2oz1Y5QIDAQAB", "1615896309308"),
    3: ("https://component-otapc-eu.allawnos.com/update/v3", "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAh8/EThsK3f0WyyPgrtXb/D0Xni6UZNppaQHUqHWo976cybl92VxmehE0ISObnxERaOtrlYmTPIxkVC9MMueDvTwZ1l0KxevZVKU0sJRxNR9AFcw6D7k9fPzzpNJmhSlhpNbt3BEepdgibdRZbacF3NWy3ejOYWHgxC+I/Vj1v7QU5gD+1OhgWeRDcwuV4nGY1ln2lvkRj8EiJYXfkSq/wUI5AvPdNXdEqwou4FBcf6mD84G8pKDyNTQwwuk9lvFlcq4mRqgYaFg9DAgpDgqVK4NTJWM7tQS1GZuRA6PhupfDqnQExyBFhzCefHkEhcFywNyxlPe953NWLFWwbGvFKwIDAQAB", "1615897067573"),
}
SERVER_CODE = {"GL": 0, "CN": 1, "IN": 2, "EU": 3}
# RegionData.kt: displayName -> (nvid, serverCode)
REGIONS = {
    "GLO": ("NVA7", "GL"), "CN": ("NV97", "CN"), "VN": ("NV3C", "EU"), "IN": ("NV1B", "IN"),
    "EU": ("NV44", "EU"), "TR": ("NV51", "GL"), "RU": ("NV37", "EU"), "MEA": ("NVA6", "EU"),
    "SA": ("NV83", "EU"), "SG": ("NV2C", "EU"), "TH": ("NV39", "EU"), "LATAM": ("NV9A", "EU"),
    "BR": ("NV9E", "GL"), "TW": ("NV1A", "EU"), "MY": ("NV38", "EU"), "ID": ("NV33", "EU"),
    "KZ": ("NV5A", "EU"), "OCA": ("NVA5", "EU"), "PH": ("NV3D", "EU"), "LK": ("NV60", "EU"),
}


class OtaQueryError(Exception):
    pass


# --- Crypto.kt (v2: AES-256-CTR + RSA-OAEP-SHA1 on the session key) --------------
def _ctr(data: bytes, key: bytes, iv: bytes) -> bytes:
    c = Cipher(algorithms.AES(key), modes.CTR(iv)).encryptor()
    return c.update(data) + c.finalize()


def _protected_key(key_b64: str, pub_b64: str) -> str:
    pub = load_der_public_key(base64.b64decode(pub_b64))
    if not isinstance(pub, RSAPublicKey):
        raise OtaQueryError("server key is not an RSA key")
    ct = pub.encrypt(key_b64.encode(), padding.OAEP(                 # the OTA servers expect OAEP with SHA-1
        mgf=padding.MGF1(hashes.SHA1()), algorithm=hashes.SHA1(), label=None))  # noqa: S303
    return base64.b64encode(ct).decode()


# --- Request.kt --------------------------------------------------------------
def rui_from_group(name: str) -> int:
    import re
    for pat, table in ((r"(?:Realme\s*UI|RUI)\s*(\d+)", None), (r"(?:ColorOS|COS)\s*(\d+)", "cos"),
                       (r"Android\s*(\d+)", "and")):
        m = re.search(pat, name, re.I)
        if not m:
            continue
        n = int(m.group(1))
        if table is None:
            return max(1, min(7, n))
        if table == "cos":
            return 6 if n >= 15 else {14: 5, 13: 4, 12: 3, 11: 2}.get(n, 1 if n <= 7 else 6)
        return 7 if n >= 17 else 6 if n >= 15 else {14: 5, 13: 4, 12: 3, 11: 2}.get(n, 1)
    return 6


def firmware_version(product_model: str, nv: str, letter: str) -> str:
    return f"{product_model}{nv}_11.{letter}.01_0001_100001010000"


@dataclass
class Query:
    product: str          # model sent to the server (variant.productName, e.g. CPH2653EEA)
    model: str            # productModel used in the firmware string (e.g. CPH2653)
    region_name: str      # displayName (EU, IN, GLO, CN ...)
    rui: int              # derived from the group name
    letter: str = "A"
    req_mode: str = "manual"
    gray: int = 0
    beta: bool = False
    language: str | None = None
    ota_version: str | None = None   # full override (e.g. to target a specific build)


def _android_cos(rui: int) -> tuple[str, str]:
    if rui >= 11: a = c = rui
    elif rui >= 6: a = c = 10 + rui
    elif rui == 1: a, c = 10, 7
    else: a, c = 10 + rui - 1, 11 + rui - 2
    return (f"Android {a}" if a >= 17 else f"Android{a}.0"), (f"ColorOS {c}.0" if c >= 17 else f"ColorOS{c}")


# OTA Pulse names the product of some regions model + suffix (CPH2659EEA, RMX5078IN, CPH2865RU)
REGION_SUFFIX = {"IN": "IN", "EU": "EEA", "RU": "RU", "TR": "TR"}


def scan_queries(model: str, region: str, android: int) -> list[Query]:
    """Queries that could return a firmware known only by model, region and Android release (a row of the results,
    not an entry of OTA Pulse): the product with and without its regional suffix, from the Android release and the one
    before it (an OTA offers the update of the version it is asked from). Each one is to be tried with every letter."""
    products = [model, model + REGION_SUFFIX[region]] if region in REGION_SUFFIX else [model]
    ruis = sorted({rui_from_group(f"Android {android}"), rui_from_group(f"Android {android - 1}")})
    return [Query(p, model, region, rui) for p in products for rui in ruis]


def query(q: Query, timeout: float = 30) -> dict:
    """Return the decrypted response JSON (dict) or raise OtaQueryError."""
    nv, scode = REGIONS[q.region_name]
    ridx = SERVER_CODE[scode]
    url, pub, negv = SERVERS[ridx]
    fw = q.ota_version or firmware_version(q.model, nv, q.letter)
    now = str(int(time.time() * 1000))
    android, cos = _android_cos(q.rui)
    reg_str = {1: "CN", 2: "IN", 3: "EU"}.get(ridx, "GL")
    carrier = {1: "10010111", 3: "01000100"}.get(ridx, "00011011") if nv else "0"
    lang = q.language or ("zh-CN" if ridx == 1 else "en-EN")
    props = {
        "model": q.product, "productName": q.product, "otaVersion": fw,
        "otaPrefix": "_".join(fw.split("_")[:2]), "romVersion": "_".join(fw.split("_")[:2]),
        "language": lang, "gray": str(q.gray), "reqMode": q.req_mode,
        "deviceId": hashlib.sha256(DEFAULT_HEADERS["deviceId"].encode()).hexdigest(),
        "trackRegion": reg_str, "uRegion": reg_str, "nvCarrier": carrier,
        "androidVersion": android, "colorOSVersion": cos,
        "isRealme": "0", "time": now,
    }
    body = {k: props.get(k, v) for k, v in DEFAULT_BODY.items()}
    if q.beta:
        body["mode"] = "1"
    headers = {k: props.get(k, v) for k, v in DEFAULT_HEADERS.items()}
    headers["version"] = "2"
    headers["mode"] = q.req_mode

    key = os.urandom(32); iv = os.urandom(16)
    key_b64 = base64.b64encode(key).decode()
    cipher = base64.b64encode(_ctr(json.dumps(body, separators=(",", ":")).encode(), key, iv)).decode()
    payload = {"params": json.dumps({"cipher": cipher, "iv": base64.b64encode(iv).decode()},
                                    separators=(",", ":"))}
    headers["protectedKey"] = json.dumps({"SCENE_1": {
        "protectedKey": _protected_key(key_b64, pub),
        "version": str(int(now) + 86400 * 1000), "negotiationVersion": negv}}, separators=(",", ":"))

    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode()
    except Exception as e:  # noqa: BLE001
        if isinstance(e, urllib.error.HTTPError):
            e.close()                                   # the error holds the connection
        raise OtaQueryError(f"http: {type(e).__name__}") from None
    try:
        outer = json.loads(raw)
        if outer.get("responseCode", 200) != 200:
            raise OtaQueryError(f"server {outer.get('responseCode')}: {outer.get('errMsg', '')}")
        inner = json.loads(outer["body"]) if isinstance(outer.get("body"), str) else outer.get("body")
        plain = _ctr(base64.b64decode(inner["cipher"]), key, base64.b64decode(inner["iv"]))
        content = json.loads(plain)
    except OtaQueryError:
        raise
    except Exception as e:  # noqa: BLE001
        raise OtaQueryError(f"decode: {type(e).__name__}") from None
    root = content.get("body", content) if isinstance(content, dict) else content
    if isinstance(root, dict) and root.get("checkFailReason") not in (None, ""):
        raise OtaQueryError(f"check failed: {root['checkFailReason']}")
    return root


def components(root: dict) -> list[dict]:
    """Normalize the response into release dicts (same fields as the catalog)."""
    out = []
    for c in root.get("components", []) or []:
        pk = c.get("componentPackets", {}) or {}
        url = "".join((pk.get("manualUrl") or pk.get("url") or "").split())
        if not url:
            continue
        out.append({
            "version": root.get("versionName") or c.get("componentVersion", ""),
            "ota_version": root.get("realOtaVersion") or root.get("otaVersion") or c.get("componentVersion", ""),
            "source_url": url, "md5": pk.get("md5", ""),
            "size": int(pk.get("size") or 0),
            "security_patch": root.get("securityPatch", "") or "",
        })
    return out
