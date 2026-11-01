from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import catalog, normalize
from .extract import extract, extract_android


def _load_results(path: str) -> dict:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return {r["id"]: r for r in json.load(f)}
    return {}


def _save(path: str, rows: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    for i in [i for i, r in rows.items() if not catalog.wanted_version(r["version"], r.get("android_version"))]:
        del rows[i]                            # only Android 14+ firmware is kept
    for r in rows.values():
        r.pop("source_url", None)              # never persist URLs
        normalize.row(r)                       # fix catalog typos / naming (idempotent)
    dropped = normalize.dedupe(rows)           # one row per firmware, whatever the ids it came with
    if dropped:
        print(f"dropped {len(dropped)} duplicate rows", file=sys.stderr)
    normalize.relabel(rows.values())           # one device label per model code
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(sorted(rows.values(), key=lambda r: (r["device"], r["model"], r.get("build_timestamp", ""))),
                  f, indent=1, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def cmd_url(a):
    r = extract(a.url)
    print(json.dumps(r.dict(), indent=1))
    return 0 if r.ok else 1


def cmd_fetch(a):
    """Download the live catalog and MERGE it into the local one (by id): known releases are
    kept even if the API drops them; new ones are added."""
    import urllib.request
    with urllib.request.urlopen(a.api, timeout=120) as r:
        live = json.load(r)
    live_rel = live["releases"] if isinstance(live, dict) else live
    local = {"api_version": "1", "releases": []}
    existed = os.path.exists(a.out)
    if existed:
        with open(a.out, encoding="utf-8") as f:
            local = json.load(f)
    by_id = {r["id"]: r for r in local["releases"]}
    new = [r for r in live_rel if r["id"] not in by_id]
    for r in live_rel:                      # also refresh known ones (e.g. is_latest, new links)
        by_id[r["id"]] = r
    local["releases"] = list(by_id.values())
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(local, f, ensure_ascii=False)
    new_op = [r for r in new if catalog.is_oneplus(r)]
    if not existed:
        print(f"{a.out}: catalog initialized with {len(local['releases'])} releases ({len(new_op)} OnePlus)")
        return 0
    print(f"{a.out}: {len(local['releases'])} releases in total, {len(new)} new ({len(new_op)} OnePlus)")
    shown = sorted(new_op, key=lambda r: r["build_timestamp"])
    for r in shown[:20]:
        print(f"  + {r['device']:<16} {r['region']:<4} {r['version']}")
    if len(shown) > 20:
        print(f"  ... and {len(shown) - 20} more")
    return 0


def cmd_discover(a):
    """Query the OTA servers (OTA Pulse protocol) for the current firmware of every OnePlus model
    and add the ones not yet known to the local catalog."""
    import hashlib
    import re
    import urllib.request
    from . import ota_query as oq

    with urllib.request.urlopen(a.devices, timeout=60) as r:
        devices = json.load(r)
    cat = {"api_version": "1", "releases": []}
    if os.path.exists(a.catalog):
        with open(a.catalog, encoding="utf-8") as f:
            cat = json.load(f)
    by_id = {r["id"]: r for r in cat["releases"]}
    by_key: dict[tuple[str, str], str] = {}        # firmware -> id of its catalog entry (first wins)
    for r in cat["releases"]:
        by_key.setdefault(normalize.firmware_key(r), r["id"])
    done = {normalize.firmware_key(r) for r in _load_results(a.results).values()}      # already processed: not "new"
    labels = normalize.labels_by_model(r for r in cat["releases"] if catalog.is_oneplus(r))
    letters: dict[str, set[str]] = {}          # model -> track letters seen in the catalog (11.<L>.)
    for r in cat["releases"]:
        m = re.search(r"_11\.([A-Z])\.", r["ota_version"])
        if m:
            letters.setdefault(r["model"], set()).add(m.group(1))

    queries: dict[tuple, tuple] = {}
    for d in devices:
        name = d.get("name", "")
        if not catalog.is_oneplus({"device": normalize.device_from_name(name)}):
            continue                                   # OnePlus 9 and older (same rule as the catalog)
        base = d.get("variants") or []
        for grp, val in (d.get("firmwareGroups") or {}).items():
            rui = oq.rui_from_group(grp)
            variants = val if isinstance(val, list) else [dict(v, versionLetter=val) if isinstance(val, str) else v for v in base]
            for v in variants:
                disp = v.get("displayName")
                if disp not in oq.REGIONS:
                    continue
                model = v.get("productModel") or v.get("model")
                if not model:
                    continue
                q = oq.Query(v.get("productName") or model, model, disp, rui, v.get("versionLetter", "A"), v.get("reqMode", "manual"))
                # the same query is listed under several groups and devices: ask the server once
                queries.setdefault((q.product, q.model, q.region_name, q.rui, q.letter, q.req_mode), (name, disp, model, q))
    jobs = list(queries.values())
    print(f"OTA queries: {len(jobs)}", file=sys.stderr)

    def work(j):
        name, disp, model, q = j
        err = None
        # OTA Pulse letter first, then the ones seen in the catalog for the same model
        tries = [q.letter] + sorted(letters.get(model, set()) - {q.letter})
        for L in tries:
            q.letter = L
            try:
                return j, oq.components(oq.query(q)), None
            except Exception as e:  # noqa: BLE001
                err = str(e)
                if "2004" not in err:           # only "no update" is worth retrying
                    break
        return j, [], err

    added, errs, new_keys, refreshed = 0, {}, set(), set()
    with ThreadPoolExecutor(a.workers) as ex:
        for j, comps, err in ex.map(work, jobs):
            name, disp, model, q = j
            if err:
                errs[err] = errs.get(err, 0) + 1
                kind = ("restricted track (taste/beta): covered by the catalog only" if q.req_mode == "taste"
                        else "no public update for this track")
                print(f"  ! {name} {disp} {model} (rui {q.rui}, {q.req_mode}): {kind}", file=sys.stderr)
            for c in comps:
                if not catalog.wanted_version(c["version"]):
                    continue                             # Android 13 and older
                key = normalize.firmware_key({"version": c["version"], "region": disp})
                if key in new_keys:                      # several queries report the same firmware
                    continue
                if key in by_key:                        # already known: refresh the link (it may have expired)
                    rel = by_id[by_key[key]]
                    rel["source_url"], rel["md5"] = c["source_url"], c["md5"] or rel.get("md5", "")
                    refreshed.add(rel["id"])
                    continue
                new_keys.add(key)
                rid = "q-" + hashlib.sha1("|".join((model, c["ota_version"], disp)).encode(), usedforsecurity=False).hexdigest()[:20]
                by_id[rid] = {"id": rid, "device": labels.get(model) or normalize.device_from_name(name), "region": disp,
                              "model": model, "version": c["version"], "ota_version": c["ota_version"],
                              "build_timestamp": normalize.ota_timestamp(c["ota_version"]),
                              "security_patch": c["security_patch"],
                              "source_url": c["source_url"], "md5": c["md5"], "size": c["size"],
                              "is_latest": True, "origin": "ota-query"}
                by_key[key] = rid
                if key not in done:                      # already processed ones stay in the catalog (retries) but are not "new"
                    added += 1
                    print(f"  + {name} {disp} {c['version']}", file=sys.stderr)
    ou_added = 0
    if not a.no_ou:
        from . import sources
        for rel in sources.ou_releases(a.workers):
            rel["device"] = labels.get(rel["model"], rel["device"])
            key = normalize.firmware_key(rel)
            if key in by_key:                            # same firmware already in the catalog: complete missing metadata
                old = by_id[by_key[key]]
                old["md5"] = old.get("md5") or rel["md5"]
                old["size"] = old.get("size") or rel["size"]
                continue
            by_id[rel["id"]] = rel
            by_key[key] = rel["id"]
            if key not in done:                          # already processed ones stay in the catalog (retries) but are not "new"
                ou_added += 1
                print(f"  + {rel['device']} {rel['region']} {rel['version']}  [oxygen-updater]", file=sys.stderr)
    cat["releases"] = list(by_id.values())
    with open(a.catalog, "w", encoding="utf-8") as f:
        json.dump(cat, f, ensure_ascii=False)
    print(f"new releases from OTA query: {added}  from Oxygen Updater: {ou_added}  links refreshed: {len(refreshed)}  "
          f"(queries without answer: {sum(errs.values())})")
    return 0


def _uniq(items):
    return list(dict.fromkeys(items))


def cmd_report(a):
    """Markdown table; rows of the same device sharing kernel + build are merged."""
    rows = [normalize.row(r) for r in json.load(open(a.results, encoding="utf-8"))
            if r["ok"] and catalog.wanted_version(r["version"], r.get("android_version"))]
    rows.sort(key=lambda r: (r["device"], r["build_timestamp"], r["model"], r["region"]))
    groups: dict[tuple, list] = {}
    for r in rows:                                   # dict keeps first-seen order = oldest build first
        groups.setdefault((r["device"], r["kernel_release"], r["build"]), []).append(r)
    out = ["| Device | Models | Regions | Android version | FW versions | Kernel | Build |",
           "|---|---|---|---|---|---|---|"]
    for (device, kernel, build), g in groups.items():
        models = "<br>".join(sorted(set(r["model"] for r in g)))
        regions = "<br>".join(sorted(set(r["region"] for r in g)))
        pairs = list(dict.fromkeys((r["version"], normalize.android(r)) for r in g))   # one line per FW version
        versions = "<br>".join(v for v, _ in pairs)
        androids = "<br>".join(f"A{an}" if an else "?" for _, an in pairs)                   # same order as FW versions
        out.append(f"| {device} | {models} | {regions} | {androids} | {versions} | `{kernel}` | `{build}` |")
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print(f"{len(rows)} firmware -> {len(groups)} rows -> {a.out}")
    return 0


def cmd_archive(a):
    """Add Android 14+ firmware missing from the results, from the spike0en archive (boot.7z assets)."""
    import hashlib
    from . import archive
    rows = _load_results(a.out)
    have = {(r["version"], r["region"]) for r in rows.values()}
    device_of = {r["version"].split("_")[0]: r["device"] for r in rows.values()}
    todo = []
    for rel in archive.releases(os.environ.get("GITHUB_TOKEN")):
        v = normalize.version(rel["version"])
        if (v, rel["region"]) in have or v.split("_")[0] not in device_of:
            continue
        todo.append({**rel, "version": v})
    if a.limit:
        todo = todo[: a.limit]
    print(f"archive: {len(todo)} missing firmware", file=sys.stderr)
    if a.dry_run:
        for t in todo:
            print(f"  {device_of[t['version'].split('_')[0]]} {t['version']} {t['region']}")
        return 0
    with ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(archive.extract_asset, t["asset_url"]): t for t in todo}
        for n, fu in enumerate(as_completed(futs), 1):
            t, res = futs[fu], fu.result()
            code = t["version"].split("_")[0]
            rid = "sp-" + hashlib.sha1(f"{t['version']}|{t['region']}".encode()).hexdigest()[:10]
            rows[rid] = {
                "id": rid, "device": device_of[code], "region": t["region"], "model": code, "version": t["version"],
                "ota_version": t["version"], "build_timestamp": "", "md5": "", "size": 0, "origin": "spike0en-archive",
                "ok": res.ok, "android_version": str(catalog.os_major(t["version"])),
                "linux_version": res.linux_version, "kernel_release": res.kernel_release, "build": res.build,
                "compiler": res.compiler, "source": res.source, "error": res.error,
            }
            print(f"[{n}/{len(todo)}] {t['version']} {t['region']}: {res.kernel_release or res.error}", file=sys.stderr)
            if n % 10 == 0:
                _save(a.out, rows)
    _save(a.out, rows)
    return 0


def cmd_run(a):
    rels = catalog.oneplus_releases(a.catalog)
    rows = _load_results(a.out)
    row_of = {normalize.firmware_key(r): i for i, r in rows.items()}      # firmware -> id of its stored row
    todo = [r for r in rels
            if (i := row_of.get(normalize.firmware_key(r))) is None or (a.retry_failed and not rows[i]["ok"])]
    if a.limit:
        todo = todo[: a.limit]
    print(f"OnePlus releases: {len(rels)}  already done: {len(rels) - len(todo)}  to do: {len(todo)}", file=sys.stderr)

    def work(rel):
        res = extract(rel["source_url"])
        return rel, res

    with ThreadPoolExecutor(a.workers) as ex:
        futs = [ex.submit(work, r) for r in todo]
        for n, fu in enumerate(as_completed(futs), 1):
            rel, res = fu.result()
            rid = row_of.get(normalize.firmware_key(rel), rel["id"])      # a retry updates the stored row
            rows[rid] = {
                "id": rid, "device": rel["device"], "region": rel["region"], "model": rel["model"],
                "version": rel["version"], "ota_version": rel["ota_version"],
                "build_timestamp": rel.get("build_timestamp", ""), "md5": rel.get("md5", ""),
                "size": rel.get("size") or res.size or 0, "origin": rel.get("origin", "catalog"),
                "ok": res.ok, "android_version": res.android_version or rows.get(rid, {}).get("android_version"),
                "linux_version": res.linux_version, "kernel_release": res.kernel_release,
                "build": res.build, "compiler": res.compiler,
                "source": res.source, "error": res.error,
            }
            print(f"[{n}/{len(todo)}] {rel['device']} {rel['model']} {rel['version']}: "
                  f"{res.kernel_release or res.error}", file=sys.stderr)
            if n % 10 == 0:
                _save(a.out, rows)
    _save(a.out, rows)

    # metadata pass for rows that miss Android version, size or md5 (a few KB per row, no full extraction)
    rel_of = {normalize.firmware_key(r): r for r in rels}
    need = [i for i, r in rows.items() if r.get("ok") and (
        ("android_version" not in r or (r["android_version"] is None and a.retry_failed))
        or not r.get("size") or not r.get("md5"))]
    if need:
        print(f"metadata pass: {len(need)} rows", file=sys.stderr)
        arb = None
        if any(not rows[i].get("md5") for i in need):
            try:
                from . import sources
                arb = sources.arb_index()
            except Exception as e:  # noqa: BLE001 - the md5 index is optional
                print(f"  antirollchecker index unavailable: {type(e).__name__}", file=sys.stderr)

        def work_meta(i):
            r = rows[i]
            rel = rel_of.get(normalize.firmware_key(r))
            res = extract_android(rel["source_url"]) if rel and (
                "android_version" not in r or not r.get("size")) else None
            return i, res

        with ThreadPoolExecutor(a.workers) as ex:
            for n, (i, res) in enumerate(ex.map(work_meta, need), 1):
                r = rows[i]
                rel = rel_of.get(normalize.firmware_key(r))
                if res is not None:
                    if "android_version" not in r or res.android_version:
                        r["android_version"] = res.android_version or r.get("android_version")
                    if not r.get("size") and res.size:
                        r["size"] = res.size
                if not r.get("size") and rel and rel.get("size"):
                    r["size"] = rel["size"]
                if not r.get("md5"):
                    r["md5"] = (rel or {}).get("md5") or (arb or {}).get((r["version"], r["region"]), "")
                if n % 50 == 0:
                    print(f"  [{n}/{len(need)}]", file=sys.stderr)
                    _save(a.out, rows)
        _save(a.out, rows)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="opkv")
    sub = p.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("url", help="extract Linux version from a single OTA zip (URL)")
    u.add_argument("url"); u.set_defaults(fn=cmd_url)
    f = sub.add_parser("fetch", help="update the local release catalog (roms.danielspringer.at API)")
    f.add_argument("--api", default="https://roms.danielspringer.at/api/ota.php")
    f.add_argument("--out", default="data/catalog.json"); f.set_defaults(fn=cmd_fetch)
    dsc = sub.add_parser("discover", help="native OTA query: find firmware missing from the catalog")
    dsc.add_argument("--devices", default="https://raw.githubusercontent.com/RemuruSama/OTA-Pulse/main/devices/oneplus.json")
    dsc.add_argument("--no-ou", action="store_true", help="skip the Oxygen Updater source")
    dsc.add_argument("--catalog", default="data/catalog.json"); dsc.add_argument("--results", default="data/results.json"); dsc.add_argument("--workers", type=int, default=4)
    dsc.set_defaults(fn=cmd_discover)
    ar = sub.add_parser("archive", help="add Android 14+ firmware missing from the results (spike0en archive, boot.7z)")
    ar.add_argument("--out", default="data/results.json"); ar.add_argument("--workers", type=int, default=3)
    ar.add_argument("--limit", type=int, default=0); ar.add_argument("--dry-run", action="store_true")
    ar.set_defaults(fn=cmd_archive)
    g = sub.add_parser("report", help="results.json -> markdown table")
    g.add_argument("--results", default="data/results.json"); g.add_argument("--out", default="data/results.md")
    g.set_defaults(fn=cmd_report)
    r = sub.add_parser("run", help="extract the kernel version of all OnePlus releases not yet processed")
    r.add_argument("--catalog", default="data/catalog.json", help="file or URL")
    r.add_argument("--out", default="data/results.json")
    r.add_argument("--workers", type=int, default=4)
    r.add_argument("--limit", type=int, default=0)
    r.add_argument("--retry-failed", action="store_true")
    r.set_defaults(fn=cmd_run)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
