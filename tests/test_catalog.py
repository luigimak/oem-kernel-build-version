from opkv.catalog import os_major, wanted_version


def test_os_major():
    assert os_major("CPH2653_16.0.10.600(EX01)") == 16
    assert os_major("junk") is None


def test_wanted_version():
    assert wanted_version("CPH2449_13.1.0.500(EX01)") is False
    assert wanted_version("CPH2449_14.0.0.100(EX01)") is True
    assert wanted_version("CPH2449_13.1.0.500(EX01)", "14") is True
    assert wanted_version("junk") is False
