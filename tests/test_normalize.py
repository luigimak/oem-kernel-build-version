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
