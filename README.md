# oneplus-kernel-build-version

Extracts the `Linux version …` string (kernel version + build) from the `boot.img` inside the `payload.bin`
of OnePlus OTA packages, without downloading the firmware: it reads only the needed bytes over HTTP Range
(~130 KB per OTA). Results: [`data/results.md`](data/results.md) and `data/results.json`.

## Usage
```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
opkv fetch      # update the local release catalog (roms.danielspringer.at API)
opkv discover   # query the OTA servers for firmware missing from the catalog
opkv run        # extract kernel/build of new firmware -> data/results.json
opkv report     # data/results.md
opkv url <URL>  # a single OTA zip
```
OnePlus only (`OP …`), from the 10 series onward. `run` is resumable. A weekly GitHub Actions workflow
(`.github/workflows/update.yml`, Mondays) runs the sequence and opens a draft PR. Scheduled runs are off by
default: set the repository variable `AUTO_UPDATE=true` to enable them; manual runs always work.

## Notes
- Firmware URLs are never stored or logged.
- Full OTAs only; incremental ones return an error. OTAs without `payload.bin` fall back to `boot.img` in the zip.
- The Android version comes from `META-INF/com/android/metadata` in each OTA (a few KB); if it is missing, it is inferred from the OS version (OxygenOS/ColorOS 13+ major = Android release). `run` backfills it for rows that lack it.
- Beta tracks (`taste`) cannot be found by `discover`; they depend on the catalog.

## License and attribution
Apache License 2.0 (see [LICENSE](LICENSE) and [NOTICE](NOTICE)).
`src/opkv/ota_query.py` and `src/opkv/resolver.py` are derived from
[OTA Pulse](https://github.com/RemuruSama/OTA-Pulse) (Apache-2.0, Copyright 2026 OTA Pulse), translated to Python
and modified. The model list (OTA Pulse `devices/oneplus.json`) is downloaded at runtime and not redistributed here.
The release catalog comes from roms.danielspringer.at.
