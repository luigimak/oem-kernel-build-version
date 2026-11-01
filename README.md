# oneplus-kernel-build-version

Extracts the `Linux version …` string (kernel version + build) from the `boot.img` inside the `payload.bin`
of OnePlus OTA packages, without downloading the firmware: it reads only the needed bytes over HTTP Range
(~130 KB per OTA). Results: [`data/results.md`](data/results.md) and `data/results.json`.

## Usage
```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
opkv fetch      # update the local release catalog (roms.danielspringer.at API)
opkv discover   # find firmware missing from the catalog: OTA servers + Oxygen Updater (--no-ou to skip)
opkv run        # extract kernel/build of new firmware -> data/results.json
opkv archive   # add older Android 14+ firmware missing from the results (spike0en archive, boot.7z)
opkv report     # data/results.md
opkv url <URL>  # a single OTA zip
```
OnePlus only (`OP …`), from the 10 series onward, and only firmware from Android 14 onward (older rows are dropped). `run` is resumable. A weekly GitHub Actions workflow
(`.github/workflows/update.yml`, Mondays) runs the sequence and commits the updated results to the default branch. Scheduled runs are off by
default: set the repository variable `AUTO_UPDATE=true` to enable them; manual runs always work.

## Notes
- Firmware URLs are never stored or logged.
- Full OTAs only; incremental ones return an error. OTAs without `payload.bin` fall back to `boot.img` in the zip.
- The Android version comes from `META-INF/com/android/metadata` in each OTA (a few KB); if it is missing, it is inferred from the OS version (OxygenOS/ColorOS 13+ major = Android release). `run` backfills it for rows that lack it.
- Missing `md5`/`size` are filled from Oxygen Updater, the antirollchecker database or the OTA `Content-Length`; rows whose links expired may stay empty.
- Beta tracks (`taste`) cannot be found by `discover`; they depend on the catalog.

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

## Sources
- [roms.danielspringer.at](https://roms.danielspringer.at) — release catalog (`opkv fetch`).
- [OTA Pulse](https://github.com/RemuruSama/OTA-Pulse) (Apache-2.0) protocol and model list — OTA server queries (`opkv discover`).
- [Oxygen Updater](https://github.com/oxygen-updater/os-updater) API — extra full-OTA releases, md5 and size.
- [spike0en/oneplus_archive](https://github.com/spike0en/oneplus_archive) — historical firmware: the `boot.7z` asset of each release is downloaded temporarily and read (`opkv archive`). Its `ROW` region is recorded as `GLO`.
- [OnePlus-antirollchecker](https://github.com/Bartixxx32/OnePlus-antirollchecker) `database.json` — md5 checksums.
