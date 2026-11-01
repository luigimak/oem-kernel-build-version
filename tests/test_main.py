import runpy
import sys

import pytest


def test_python_dash_m_opkv_runs_the_command_line(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["opkv", "--help"])
    with pytest.raises(SystemExit) as stop:
        runpy.run_module("opkv", run_name="__main__")
    assert stop.value.code == 0 and "usage: opkv" in capsys.readouterr().out
