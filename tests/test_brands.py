"""How a device is named in the catalogs and sources ("OP 13R") and in the results rows ("13R", next to its brand)."""
import pytest

from opkv import brands


@pytest.mark.parametrize("key,name,device", [
    ("oneplus", "OP 13R", "13R"), ("oneplus", "OP PAD2 PRO", "PAD 2 PRO"), ("oneplus", "OP OPEN", "OPEN"),
    ("oppo", "OPPO FIND X9", "FIND X9"), ("oppo", "OPPO RENO 16 PRO+", "RENO 16 PRO+"),
    ("realme", "Realme GT7 PRO", "GT7 PRO"), ("realme", "realme 16 Pro", "16 PRO"), ("realme", "REALME NEO 8", "NEO 8"),
    ("xiaomi", "Xiaomi 15T Pro", "15T PRO"), ("xiaomi", "XIAOMI PAD 7", "PAD 7"),
    ("poco", "POCO F7 Pro", "F7 PRO"), ("poco", "POCO M8 Pro 5G", "M8 PRO 5G"),
    ("redmi", "REDMI 17 5G", "17 5G"), ("redmi", "Redmi Note 14 Pro+ 5G", "NOTE 14 PRO+ 5G"),
    ("nothing", "Nothing Phone (2a)", "Phone (2a)"), ("nothing", "Nothing CMF Phone 1", "CMF Phone 1"),
    ("motorola", "Motorola AVR", "AVR"), ("lenovo", "Lenovo Legion Y700 5G", "LEGION Y700 5G")])
def test_short_drops_the_brand_prefix_and_full_puts_it_back(key, name, device):
    brand = brands.BRANDS[key]
    assert brand.short(name) == device
    assert brand.short(device) == device                      # a device that is already short stays as it is
    assert brand.matches({"device": brand.full(device)})      # the prefixed name is what `matches` recognizes


def test_adopt_puts_the_brand_after_the_id_and_shortens_the_device():
    old = {"id": "a", "device": "OP 13R", "region": "EU"}
    new = brands.BRANDS["oneplus"].adopt(old)
    assert new == {"id": "a", "brand": "OnePlus", "device": "13R", "region": "EU"}
    assert list(new) == ["id", "brand", "device", "region"]
    assert old == {"id": "a", "device": "OP 13R", "region": "EU"}      # the row it was given is left alone


@pytest.mark.parametrize("key", list(brands.BRANDS))
def test_adopt_leaves_a_current_row_unchanged(key):
    brand = brands.BRANDS[key]
    row = {"id": "a", "brand": brand.label, "device": "13R", "region": "EU"}
    assert brand.adopt(row) == row and list(brand.adopt(row)) == list(row)


def test_every_brand_lists_which_sources_know_it():
    sources = {key: (bool(b.pulse), bool(b.ou_prefix), bool(b.violet), b.archive) for key, b in brands.BRANDS.items()}
    assert sources["oneplus"] == (True, True, True, "spike0en/oneplus_archive")
    assert sources["oppo"] == sources["realme"] == (True, True, True, "")
    assert sources["nothing"] == (False, False, False, "spike0en/nothing_archive")
    assert all(sources[k] == (False, False, False, "") for k in ("xiaomi", "poco", "redmi", "motorola", "lenovo"))
    assert (brands.BRANDS["motorola"].lolinet, brands.BRANDS["lenovo"].lolinet) == ("/firmware/lenomola/", "/firmware/lenowow/")
    assert not any(b.lolinet for k, b in brands.BRANDS.items() if k not in ("motorola", "lenovo"))
