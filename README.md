# oem-kernel-build-version

Extracts the `Linux version …` string (kernel version + build) from the `boot.img` inside the `payload.bin`
of OnePlus, OPPO and Realme OTA packages, without downloading the firmware: it reads only the needed bytes over HTTP Range
(about 10 MB per OTA, whose full package is several GB). Results, one pair of files per brand, updated every day by a GitHub Actions workflow:
[`data/oneplus.md`](data/oneplus.md) / [`data/oneplus.json`](data/oneplus.json),
[`data/oppo.md`](data/oppo.md) / [`data/oppo.json`](data/oppo.json),
[`data/realme.md`](data/realme.md) / [`data/realme.json`](data/realme.json).
A searchable, filterable table of all of them is published with GitHub Pages: <https://luigimak.github.io/oem-kernel-build-version/> (source in [`docs/`](docs/)).

## Usage
```bash
python3 -m venv .venv && .venv/bin/pip install .       # '.[archive]' adds what `opkv archive` needs
opkv fetch      # update the local release catalog (roms.danielspringer.at API)
opkv discover   # find firmware missing from the catalog: OTA servers, Oxygen Updater, VioletToolBox; then search the failed ones again
opkv run        # extract kernel/build of new firmware -> data/<brand>.json
opkv archive    # add older Android 14+ OnePlus firmware missing from the results (spike0en archive, boot.7z)
opkv report     # data/<brand>.md
opkv url <URL>  # a single OTA zip
```
`fetch`, `discover`, `run`, `archive` and `report` take `--brand oneplus|oppo|realme|all` (default `all`) and `--data-dir` (default `data`).
`discover` also takes `--no-ou`, `--no-violet` and `--no-scan` to skip a source or the new search of the failed firmware.
OnePlus (`OP …`) from the 10 series onward, every OPPO and Realme model, and only firmware from Android 14 onward (older rows are dropped). `run` is resumable.

A GitHub Actions workflow (`.github/workflows/update.yml`) runs `fetch`, `discover`, `run --retry-failed` and `report` every day and commits
the updated results to the default branch. `archive` is a manual command.

## Results
`data/<brand>.json` is a list of rows, one per firmware, sorted by device, model and build time:

| Field | Meaning |
|---|---|
| `id`, `origin` | row id and where the firmware was found (`catalog`, `ota-query`, `ota-scan`, `oxygen-updater`, `violettoolbox`, `spike0en-archive`) |
| `device`, `model`, `region` | device label (`OP 13R`), model code (`CPH2645`), region (`EU`, `GLO`, `IN`, `CN`, `NA`, …) |
| `version`, `ota_version`, `build_timestamp` | firmware version (`CPH2645_15.0.0.840(EX01)`), OTA version string, OTA build time |
| `android_version` | Android release, from the OTA metadata; for a firmware that could not be read, from its version |
| `ok`, `error` | whether the kernel string was extracted, and why not |
| `linux_version`, `kernel_release`, `build`, `compiler` | the `Linux version …` banner and its parts |
| `source` | where the banner was read: `payload.bin` or `boot.img` |
| `md5`, `size` | of the OTA package, when known |

`data/<brand>.md` groups the rows of a device that share kernel and build, oldest kernel build first.

## Notes
- Firmware URLs are never stored or logged (error messages are redacted).
- A firmware is identified by `(version, region)`, whichever source or id it came with; each model code gets one device label (the most common one).
- Full OTAs only; incremental ones return an error. OTAs without `payload.bin` fall back to `boot.img` in the zip.
- If the OTA has no metadata, the Android release is inferred from the OS version (OxygenOS/ColorOS 13+ major = Android release).
- Missing `md5`/`size` are filled from Oxygen Updater, the antirollchecker database or the OTA `Content-Length`; rows whose links expired may stay empty.
- Failed firmware (expired links, servers that refuse) are searched again through every source that allows it, a few each day; some stay failed for good.
- VioletToolBox lists older Chinese-market (CN) firmware only; it is the one source of that history for OPPO and Realme.
- The spike0en archive and `archive` cover OnePlus only; OPPO and Realme come from the catalog, OTA Pulse and Oxygen Updater.
- Beta tracks (`taste`) cannot be found by `discover`; they depend on the catalog.

## Development
```bash
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest                # no network: a local server stands in for the OTA CDN, the OTA servers and Oxygen Updater
.venv/bin/ruff check .
.venv/bin/mypy
```
CI runs the tests, ruff and mypy on every push.

## License and attribution
Copyright 2026 luigimak, licensed under the Apache License 2.0 (see [LICENSE](LICENSE) and [NOTICE](NOTICE)).

`src/opkv/ota_query.py` and `src/opkv/resolver.py` are derived from
[OTA Pulse](https://github.com/RemuruSama/OTA-Pulse) (Apache-2.0, Copyright 2026 OTA Pulse), translated to Python
and modified; each file header says so. The model list (OTA Pulse `devices/{oneplus,oppo,realme}.json`) is downloaded at runtime
and not redistributed here.

No code from the other sources below is copied. They are queried at runtime, and `data/*.json` and `data/*.md` only contain factual
metadata (versions, regions, md5, size) and the `Linux version …` string extracted from `boot.img`. No firmware image or
download URL is stored or redistributed. Several of these sources publish no license (Oxygen Updater, spike0en/oneplus_archive,
OnePlus-antirollchecker); this project is not affiliated with them or with OnePlus/OPPO/Realme. Firmware remains the property of
its owners. If you are a source owner and want something changed or removed, open an issue.

## How it talks to the services
`opkv` only reads public metadata and never logs in. To get answers it has to present itself as the clients those services expect:
- the OnePlus/OPPO/Realme OTA servers (`discover`) are queried the way the OnePlus updater does, with a placeholder device identity (no real IMEI or account) and the protocol implemented by OTA Pulse; the OTA CDN (`run`) is read with the headers of that client, about 10 MB per new package, never the whole firmware;
- the Oxygen Updater API is called with the User-Agent of the Oxygen Updater app, which is the only one it accepts;
- the VioletToolBox ROM API (`violettool.top/rom-api`, public, no login) is called as `opkv`: version lists once a day, and a download link asked for right before a package is read (it expires within minutes, points to the manufacturer's own CDN and is used in memory only). Its README asks developers to use it moderately, hence the pause between requests.

Volume is moderate and read-only: a daily run makes about a thousand OTA queries, a few thousand Oxygen Updater requests and a few hundred VioletToolBox ones (one at a time, with a pause), plus the packages that are new that day. This may not match the terms of use of those services; if you run it, you do so on your own responsibility, and if you maintain one of them and object, open an issue.

## Sources
- [roms.danielspringer.at](https://roms.danielspringer.at) — release catalog (`opkv fetch`).
- [OTA Pulse](https://github.com/RemuruSama/OTA-Pulse) (Apache-2.0) protocol and model list — OTA server queries (`opkv discover`).
- [Oxygen Updater](https://github.com/oxygen-updater/os-updater) API — extra full-OTA releases, md5 and size.
- [spike0en/oneplus_archive](https://github.com/spike0en/oneplus_archive) — historical firmware: the `boot.7z` asset of each release is downloaded temporarily and read (`opkv archive`). Its `ROW` region is recorded as `GLO`.
- [VioletToolBox](https://github.com/Smart-Paocai/VioletToolBox) ROM API (the project is GPL-3.0; only its public HTTP API is called, none of its code is used) — older Chinese-market firmware of OnePlus, OPPO and Realme.
- [OnePlus-antirollchecker](https://github.com/Bartixxx32/OnePlus-antirollchecker) `database.json` — md5 checksums.
