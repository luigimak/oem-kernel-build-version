from opkv import normalize as n


def test_model_typos():
    assert n.model("CCPH2645") == "CPH2645"
    assert n.model("PPKX110") == "PKX110"
    assert n.model("CPH2645") == "CPH2645"
    assert n.model("PGKM10") == "PGKM10"        # legit double letters are not touched
    assert n.model("OPD2403") == "OPD2403"


def test_version_prefix():
    assert n.version("PPKX110_15.0.2.603(CN01)") == "PKX110_15.0.2.603(CN01)"
    assert n.version("NE2210_11_A.19") == "NE2210_11_A.19"


def test_device_spacing():
    assert n.device("OP PAD2 PRO") == "OP PAD 2 PRO"
    assert n.device("OP PAD GO 2") == "OP PAD GO 2"
    assert n.device("OP NORD CE4 LITE") == "OP NORD CE 4 LITE"
    assert n.device("OP NORD CE 3") == "OP NORD CE 3"
    assert n.device("OP 13S") == "OP 13S"


def test_build_date_of_a_kernel_build_string():
    assert n.build_date("#1 SMP PREEMPT Mon Dec 25 12:31:09 UTC 2023") == "2023-12-25T12:31:09"
    assert n.build_date("#1 SMP PREEMPT Thu Jan  4 08:05:00 UTC 2024") == "2024-01-04T08:05:00"
    assert n.build_date("#1 SMP PREEMPT") == ""
    assert n.build_date("") == ""
    assert n.build_date(None) == ""


def test_ota_timestamp():
    assert n.ota_timestamp("CPH2745_11.A.75_1750_202610181120") == "2026-10-18T11:20:00"
    assert n.ota_timestamp("NE2210_11_A.19") == ""
    assert n.ota_timestamp("") == ""


def test_device_from_name():
    assert n.device_from_name("OnePlus Pad2 Pro") == "OP PAD 2 PRO"
    assert n.device_from_name("OnePlus 13R/Ace 5") == "OP 13R/ACE 5"


def test_model_follows_the_version_prefix():
    assert n.model_of({"model": "CPH2653", "version": "CPH2649_15.0.0.860(EX01)"}) == "CPH2649"
    assert n.model_of({"model": "CCPH2645", "version": "junk"}) == "CPH2645"
    assert n.model_of({"version": "PPKX110_15.0.2.603(CN01)"}) == "PKX110"


def test_labels_by_model_take_the_majority_and_tidy_the_spelling():
    rows = [{"model": "CPH2653", "version": "CPH2653_1_1", "device": "OP 13"}] * 2 + [
        {"model": "CPH2653", "version": "CPH2653_1_2", "device": "OP 13S"},
        {"model": "OPD2511", "version": "OPD2511_1_1", "device": "OP PAD2 PRO"},
        {"model": "CPH2000", "version": "CPH2000_1_1", "device": ""}]
    assert n.labels_by_model(rows) == {"CPH2653": "OP 13", "OPD2511": "OP PAD 2 PRO"}


def test_android_fallback():
    assert n.android({"android_version": "16", "version": "X_16.0.1.1"}) == "16"
    assert n.android({"android_version": None, "version": "CPH2465_14.0.0.1320(EX01)"}) == "14"
    assert n.android({"android_version": None, "version": "NE2213_11_A.17"}) is None
