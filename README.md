# oneplus-kernel-build-version

Extracts the `Linux version …` string (kernel version + build) from the `boot.img` inside the `payload.bin`
of OnePlus OTA packages, without downloading the firmware: it reads only the needed bytes over HTTP Range
(about 10 MB per OTA, whose full package is several GB). Results: [`data/results.md`](data/results.md) and
[`data/results.json`](data/results.json), updated every day by a GitHub Actions workflow.
A searchable, filterable table of the same data is published with GitHub Pages: <https://luigimak.github.io/oneplus-kernel-build-version/>
(source in [`docs/`](docs/), deployed by `.github/workflows/pages.yml`; set Settings → Pages → Source to "GitHub Actions" once).

## Usage
```bash
python3 -m venv .venv && .venv/bin/pip install .       # '.[archive]' adds what `opkv archive` needs
opkv fetch      # update the local release catalog (roms.danielspringer.at API)
opkv discover   # find firmware missing from the catalog: OTA servers + Oxygen Updater (--no-ou to skip)
opkv run        # extract kernel/build of new firmware -> data/results.json
opkv archive    # add older Android 14+ firmware missing from the results (spike0en archive, boot.7z)
opkv report     # data/results.md
opkv url <URL>  # a single OTA zip
```
OnePlus only (`OP …`), from the 10 series onward, and only firmware from Android 14 onward (older rows are dropped). `run` is resumable.

The workflow `.github/workflows/update.yml` runs `fetch`, `discover`, `run --retry-failed` and `report` every day at 05:17 UTC and commits
the updated results to the default branch (`archive` is a manual command; `archive --retry-failed` downloads again the assets that failed before). Scheduled runs are off until the repository variable
`AUTO_UPDATE` is set to `true` (so a fork does not run them); manual runs always work. The workflow installs the hash-pinned
[`requirements.txt`](requirements.txt), runs `python -m opkv` from the checkout, and gives the commit step alone the token it needs to push.

## Results
`data/results.json` is a list of rows, one per firmware, sorted by device, model and build time:

| Field | Meaning |
|---|---|
| `id`, `origin` | row id and where the firmware was found (`catalog`, `ota-query`, `oxygen-updater`, `spike0en-archive`) |
| `device`, `model`, `region` | device label (`OP 13R`), model code (`CPH2645`), region (`EU`, `GLO`, `IN`, `CN`, `NA`, …) |
| `version`, `ota_version`, `build_timestamp` | firmware version (`CPH2645_15.0.0.840(EX01)`), OTA version string, OTA build time |
| `android_version` | Android release, from the OTA metadata |
| `ok`, `error` | whether the kernel string was extracted, and why not |
| `linux_version`, `kernel_release`, `build`, `compiler` | the `Linux version …` banner and its parts |
| `source` | where the banner was read: `payload.bin` or `boot.img` |
| `md5`, `size` | of the OTA package, when known |

`data/results.md` groups the rows of a device that share kernel and build, oldest kernel build first.

## Notes
- Firmware URLs are never stored or logged (error messages are redacted).
- A firmware is identified by `(version, region)`, whichever source or id it came with; each model code gets one device label (the most common one).
- Full OTAs only; incremental ones return an error. OTAs without `payload.bin` fall back to `boot.img` in the zip.
- The Android version comes from `META-INF/com/android/metadata` in each OTA (a few KB); if it is missing, it is inferred from the OS version (OxygenOS/ColorOS 13+ major = Android release). `run` backfills it for rows that lack it.
- Missing `md5`/`size` are filled from Oxygen Updater, the antirollchecker database or the OTA `Content-Length`; rows whose links expired may stay empty.
- Beta tracks (`taste`) cannot be found by `discover`; they depend on the catalog.

## Development
```bash
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest                # no network: a local server stands in for the OTA CDN, the OTA servers and Oxygen Updater
.venv/bin/ruff check .
.venv/bin/mypy
```
CI (`.github/workflows/ci.yml`) runs the tests on Python 3.10, 3.12 and 3.14, ruff and mypy on 3.12, and lints the workflows with actionlint and zizmor.
`requirements.txt` is generated from `pyproject.toml`: `pip-compile --generate-hashes --strip-extras --annotation-style=line -o requirements.txt pyproject.toml`
(Dependabot proposes the updates, monthly).

## License and attribution
Copyright 2026 luigimak, licensed under the Apache License 2.0 (see [LICENSE](LICENSE) and [NOTICE](NOTICE)).

`src/opkv/ota_query.py` and `src/opkv/resolver.py` are derived from
[OTA Pulse](https://github.com/RemuruSama/OTA-Pulse) (Apache-2.0, Copyright 2026 OTA Pulse), translated to Python
and modified; each file header says so. The model list (OTA Pulse `devices/oneplus.json`) is downloaded at runtime
and not redistributed here.

No code from the other sources below is copied. They are queried at runtime, and `data/results.*` only contains factual
metadata (versions, regions, md5, size) and the `Linux version …` string extracted from `boot.img`. No firmware image or
download URL is stored or redistributed. Several of these sources publish no license (Oxygen Updater, spike0en/oneplus_archive,
OnePlus-antirollchecker); this project is not affiliated with them or with OnePlus/OPPO. Firmware remains the property of
its owners. If you are a source owner and want something changed or removed, open an issue.

## How it talks to the services
`opkv` only reads public metadata and never logs in. To get answers it has to present itself as the clients those services expect:
- the OnePlus/OPPO OTA servers (`discover`) are queried the way the OnePlus updater does, with a placeholder device identity (no real IMEI or account) and the protocol implemented by OTA Pulse; the OTA CDN (`run`) is read with the headers of that client, about 10 MB per new package, never the whole firmware;
- the Oxygen Updater API is called with the User-Agent of the Oxygen Updater app, which is the only one it accepts.

Volume is low (a daily run makes roughly 250 OTA queries and 100 Oxygen Updater requests, plus the packages that are new that day) and read-only. This may not match the terms of use of those services; if you run it, you do so on your own responsibility, and if you maintain one of them and object, open an issue.

## Sources
- [roms.danielspringer.at](https://roms.danielspringer.at) — release catalog (`opkv fetch`).
- [OTA Pulse](https://github.com/RemuruSama/OTA-Pulse) (Apache-2.0) protocol and model list — OTA server queries (`opkv discover`).
- [Oxygen Updater](https://github.com/oxygen-updater/os-updater) API — extra full-OTA releases, md5 and size.
- [spike0en/oneplus_archive](https://github.com/spike0en/oneplus_archive) — historical firmware: the `boot.7z` asset of each release is downloaded temporarily and read (`opkv archive`). Its `ROW` region is recorded as `GLO`.
- [OnePlus-antirollchecker](https://github.com/Bartixxx32/OnePlus-antirollchecker) `database.json` — md5 checksums.
