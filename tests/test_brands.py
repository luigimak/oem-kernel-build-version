"""How a device is named in the catalogs and sources ("OP 13R") and in the results rows ("13R", next to its brand)."""
import pytest

from opkv import brands


@pytest.mark.parametrize("key,name,device", [
    ("oneplus", "OP 13R", "13R"), ("oneplus", "OP PAD2 PRO", "PAD 2 PRO"), ("oneplus", "OP OPEN", "OPEN"),
    ("oppo", "OPPO FIND X9", "FIND X9"), ("oppo", "OPPO RENO 16 PRO+", "RENO 16 PRO+"),
    ("realme", "Realme GT7 PRO", "GT7 PRO"), ("realme", "realme 16 Pro", "16 PRO"), ("realme", "REALME NEO 8", "NEO 8")])
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
