import pytest

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


def test_realme_labels_are_spelled_one_way():
    assert {n.device(x) for x in ("realme 16 Pro", "Realme 16 PRO", "REALME 16 Pro")} == {"Realme 16 PRO"}
    assert n.device_from_name("realme GT7 Pro") == "Realme GT7 PRO"
    assert n.device_from_name("OPPO Find X10") == "OPPO FIND X10"


def test_xiaomi_family_names_are_spelled_one_way():
    assert n.device("REDMI Note 15 Pro") == "Redmi NOTE 15 PRO"
    assert n.device("Redmi Note 14 Pro+ 5G") == "Redmi NOTE 14 PRO+ 5G"
    assert n.device("Xiaomi 15T Pro") == "Xiaomi 15T PRO"
    assert n.device("poco f7 pro") == "POCO F7 PRO"
    assert n.device("Nothing Phone (2a)") == "Nothing Phone (2a)"
    assert n.device("motorola Avr") == "Motorola AVR" and n.device("Lenovo Legion Y700 5G") == "Lenovo LEGION Y700 5G"


@pytest.mark.parametrize("version,android", [
    ("OS3.0.336.0.XOSRUXM", 17), ("OS3.0.311.0.WPSMIXM", 16), ("OS2.0.205.0.VNPINXM", 15), ("OS1.0.5.0.UNQINXM", 14),
    ("V14.0.5.0.TMCMIXM", 13), ("Tetris_B4.1-261028-1606", 16), ("Spacewar_V3.2-260618-1045", 15), ("Pacman_C5.0-261112-1938", 17),
    ("XT2611-3_16_W3WW36.65-64-4", 16), ("XT2415-1_14_U1UDS34.16-92-4", 14),
    ("TB390FU_ROW_OPEN_USER_Q00012.1_A16_ZUI_18.0.10.335_ST_260618", 16),
    ("TB330FU_ROW_OPEN_USER_V15.155_U_ZUI_16.0.198_ST_241220_SVC", 14),
    ("TB710FU_CN_OPEN_USER_QSM8650_V_ZUI_17.0.04.279_ST_250808", 15),
    ("CPH2653_16.0.10.600(EX01)", None), ("OS3.0", None), ("", None)])
def test_android_release_of_a_xiaomi_or_nothing_version(version, android):
    assert n.other_android(version) == android


def test_android_of_a_row_falls_back_to_the_xiaomi_and_nothing_versions():
    assert n.android({"version": "OS3.0.311.0.WPSMIXM"}) == "16"
    assert n.android({"version": "Pong_B4.1-261014-1615"}) == "16"
    assert n.android({"version": "OS3.0.311.0.WPSMIXM", "android_version": "17"}) == "17"
    assert n.android({"version": "junk"}) is None
