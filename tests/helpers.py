"""Builders shared by the tests."""
import json

from opkv.extract import Result

BANNER = ("Linux version 6.6.89-android15-8-gabc123 (kleaf@build-host) "
          "(Android clang version 18.0.0, LLD 18.0.0) #1 SMP PREEMPT Mon Jun 2 10:00:00 UTC 2025")


def release(rid, version="CPH2645_15.0.0.840(EX01)", region="EU", device="OP 13R", **kw):
    """A catalog entry (what `opkv fetch` stores)."""
    model = version.split("_")[0]
    return {"id": rid, "device": device, "region": region, "model": model, "version": version,
            "ota_version": f"{model}_11.C.60_1600_202507081931", "build_timestamp": "2025-07-08T19:31:00",
            "source_url": "https://example.invalid/ota.zip", "md5": "0" * 32, "size": 1000, **kw}


def row(rid, version="CPH2645_15.0.0.840(EX01)", region="EU", device="OP 13R", ok=True, **kw):
    """A complete data/results.json row."""
    model = version.split("_")[0]
    base = {"id": rid, "device": device, "region": region, "model": model, "version": version,
            "ota_version": f"{model}_11.C.60_1600_202507081931", "build_timestamp": "2025-07-08T19:31:00",
            "ok": ok, "android_version": "15", "md5": "0" * 32, "size": 1000, "source": "payload.bin",
            "linux_version": BANNER if ok else None, "error": None if ok else "HTTPError: HTTP Error 404: Not Found",
            "kernel_release": "6.6.89-android15-8-gabc123" if ok else None,
            "build": "#1 SMP PREEMPT Mon Jun 2 10:00:00 UTC 2025" if ok else None,
            "compiler": "Android clang version 18.0.0, LLD 18.0.0" if ok else None}
    base.update(kw)
    return base


def result(**kw):
    """What a successful `extract()` returns."""
    base = {"ok": True, "linux_version": BANNER, "kernel_release": "6.6.89-android15-8-gabc123",
            "build": "#1 SMP PREEMPT Mon Jun 2 10:00:00 UTC 2025", "compiler": "Android clang version 18.0.0, LLD 18.0.0",
            "source": "payload.bin", "android_version": "15", "size": 1000}
    base.update(kw)
    return Result(**base)


def write_json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))
