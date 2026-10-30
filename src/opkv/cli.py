from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import catalog
from .extract import extract


def _load_results(path: str) -> dict:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return {r["id"]: r for r in json.load(f)}
    return {}


def _save(path: str, rows: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows.values():
            r.pop("source_url", None)          # never persist URLs
        json.dump(sorted(rows.values(), key=lambda r: (r["device"], r["model"], r.get("build_timestamp", ""))),
                  f, indent=1, ensure_ascii=False)
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
    done_ids = set(_load_results(a.results))       # already processed: not "new"
    known = {(r["model"], r["ota_version"], r["region"]): r["id"] for r in cat["releases"]}
    letters: dict[str, set[str]] = {}          # model -> track letters seen in the catalog (11.<L>.)
    for r in cat["releases"]:
        m = re.search(r"_11\.([A-Z])\.", r["ota_version"])
        if m:
            letters.setdefault(r["model"], set()).add(m.group(1))

    jobs = []
    for d in devices:
        name = d.get("name", "")
        if re.match(r"OnePlus (\d|Nord N|Nord \d?$)", name) and not re.match(r"OnePlus (1\d|Nord \d\d)", name):
            continue                                   # OnePlus 9 and older
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
                jobs.append((name, disp, model, oq.Query(v.get("productName") or model, model, disp, rui,
                                                       v.get("versionLetter", "A"), v.get("reqMode", "manual"))))
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

    added, errs, seen, refreshed = 0, {}, set(), set()
    with ThreadPoolExecutor(a.workers) as ex:
        for j, comps, err in ex.map(work, jobs):
            name, disp, model, q = j
            if err:
                errs[err] = errs.get(err, 0) + 1
                kind = ("restricted track (taste/beta): covered by the catalog only" if q.req_mode == "taste"
                        else "no public update for this track")
                print(f"  ! {name} {disp} {model} (rui {q.rui}, {q.req_mode}): {kind}", file=sys.stderr)
            for c in comps:
                key = (model, c["ota_version"], disp)
                if key in known:                         # already known: refresh the link (it may have expired)
                    rel = by_id[known[key]]
                    rel["source_url"], rel["md5"] = c["source_url"], c["md5"] or rel.get("md5", "")
                    refreshed.add(known[key])
                    continue
                if key in seen:
                    continue
                seen.add(key)
                m = re.search(r"_(\d{12})$", c["ota_version"])
                ts = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:8]}T{m.group(1)[8:10]}:{m.group(1)[10:12]}:00" if m else ""
                rid = "q-" + hashlib.sha1("|".join(key).encode()).hexdigest()[:20]
                if rid in done_ids:
                    continue
                by_id[rid] = {"id": rid, "device": name.upper().replace("ONEPLUS", "OP"), "region": disp,
                              "model": model, "version": c["version"], "ota_version": c["ota_version"],
                              "build_timestamp": ts, "security_patch": c["security_patch"],
                              "source_url": c["source_url"], "md5": c["md5"], "size": c["size"],
                              "is_latest": True, "origin": "ota-query"}
                added += 1
                print(f"  + {name} {disp} {c['version']}", file=sys.stderr)
    cat["releases"] = list(by_id.values())
    with open(a.catalog, "w", encoding="utf-8") as f:
        json.dump(cat, f, ensure_ascii=False)
    print(f"new releases from OTA query: {added}  links refreshed: {len(refreshed)}  (queries without answer: {sum(errs.values())})")
    return 0


def cmd_report(a):
    rows = [r for r in json.load(open(a.results, encoding="utf-8")) if r["ok"]]
    rows.sort(key=lambda r: (r["device"], r["model"], r["build_timestamp"]), reverse=False)
    out = ["| Device | Model | Region | FW version | Kernel | Build |", "|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['device']} | {r['model']} | {r['region']} | {r['version']} | `{r['kernel_release']}` | {r['build']} |")
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print(f"{len(rows)} rows -> {a.out}")
    return 0


def cmd_run(a):
    rels = catalog.oneplus_releases(a.catalog)
    rows = _load_results(a.out)
    todo = [r for r in rels if r["id"] not in rows or (a.retry_failed and not rows[r["id"]]["ok"])]
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
            rows[rel["id"]] = {
                "id": rel["id"], "device": rel["device"], "region": rel["region"], "model": rel["model"],
                "version": rel["version"], "ota_version": rel["ota_version"],
                "build_timestamp": rel.get("build_timestamp", ""), "md5": rel.get("md5", ""),
                "size": rel.get("size", 0), "origin": rel.get("origin", "catalog"),
                "ok": res.ok, "linux_version": res.linux_version, "kernel_release": res.kernel_release,
                "build": res.build, "compiler": res.compiler,
                "source": res.source, "error": res.error,
            }
            print(f"[{n}/{len(todo)}] {rel['device']} {rel['model']} {rel['version']}: "
                  f"{res.kernel_release or res.error}", file=sys.stderr)
            if n % 10 == 0:
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
    dsc.add_argument("--catalog", default="data/catalog.json"); dsc.add_argument("--results", default="data/results.json"); dsc.add_argument("--workers", type=int, default=4)
    dsc.set_defaults(fn=cmd_discover)
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
