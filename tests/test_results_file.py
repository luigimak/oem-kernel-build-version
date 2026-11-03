"""What lands in data/<brand>.json, whatever the command that saved it (checked through `opkv run`)."""
from helpers import row


def saved(run, rows):
    return run([], rows)[1]


def test_results_file_ends_with_a_newline(run):
    saved(run, [row("a")])
    assert run.path.read_text(encoding="utf-8").endswith("]\n")


def test_firmware_older_than_android_14_is_dropped(run):
    old = row("old", version="CPH2449_13.1.0.500(EX01)", android_version="13")
    assert [r["id"] for r in saved(run, [old, row("new")])] == ["new"]


def test_source_url_is_never_persisted(run):
    assert "source_url" not in saved(run, [row("a", source_url="https://example.invalid/ota.zip")])[0]


def test_catalog_typos_are_fixed(run):
    typo = row("a", version="CCPH2645_15.0.0.840(EX01)", device="OP PAD2 PRO")
    r = saved(run, [typo])[0]
    assert (r["model"], r["version"], r["device"]) == ("CPH2645", "CPH2645_15.0.0.840(EX01)", "OP PAD 2 PRO")


def test_model_follows_the_firmware_version(run):
    # a catalog entry for the Indian OnePlus 13 carrying the global model code
    r = saved(run, [row("a", version="CPH2649_15.0.0.860(EX01)", region="IN", model="CPH2653")])[0]
    assert r["model"] == "CPH2649"


def test_duplicates_of_one_firmware_keep_a_successful_row(run):
    rows = saved(run, [row("failed", ok=False), row("good")])
    assert [(r["id"], r["ok"]) for r in rows] == [("good", True)]


def test_duplicates_of_one_firmware_keep_the_most_complete_row(run):
    rows = saved(run, [row("bare", md5="", size=0), row("full")])
    assert [r["id"] for r in rows] == ["full"]


def test_duplicates_with_the_same_content_keep_the_first_row(run):
    assert [r["id"] for r in saved(run, [row("first"), row("second")])] == ["first"]


def test_same_version_in_two_regions_is_not_a_duplicate(run):
    rows = saved(run, [row("eu", region="EU"), row("glo", region="GLO")])
    assert sorted(r["id"] for r in rows) == ["eu", "glo"]


def test_device_label_follows_the_majority_of_its_model(run):
    rows = [row(f"a{i}", version=f"CPH2653_15.0.0.{i}00(EX01)", device="OP 13") for i in range(3)]
    rows.append(row("odd", version="CPH2653_16.0.0.210(EX01)", device="OP 13S"))
    assert {r["device"] for r in saved(run, rows)} == {"OP 13"}


def test_models_with_a_single_label_are_left_alone(run):
    rows = [row("a", version="CPH2653_15.0.0.100(EX01)", device="OP 13"),
            row("b", version="CPH2723_15.0.0.100(EX01)", device="OP 13S", region="IN")]
    assert {r["device"] for r in saved(run, rows)} == {"OP 13", "OP 13S"}


def test_failed_row_without_android_gets_it_from_the_firmware_version(run):
    r = saved(run, [row("a", version="CPH2841_16.0.10.600(EX01)", ok=False, android_version=None)])[0]
    assert r["android_version"] == "16"


def test_android_read_from_the_ota_is_not_overwritten_by_the_version(run):
    r = saved(run, [row("a", version="CPH2841_16.0.10.600(EX01)", ok=False, android_version="15")])[0]
    assert r["android_version"] == "15"


def test_ok_row_without_android_is_left_for_the_metadata_pass(run):
    # the real value is read from the OTA by `run`; a guess would hide that the row still needs it
    row_ = row("a", version="CPH2841_16.0.10.600(EX01)", android_version=None)
    assert "android_version" in row_ and run([], [row_])[1][0]["android_version"] is None
