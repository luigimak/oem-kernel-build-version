from helpers import row, write_json

from opkv import cli

KERNEL = "6.6.89-android15-8-gabc123"
BUILD = "#1 SMP PREEMPT Mon Jun 2 10:00:00 UTC 2025"


def report(tmp_path, rows):
    res = write_json(tmp_path / "results.json", rows)
    out = tmp_path / "results.md"
    assert cli.main(["report", "--results", res, "--out", str(out)]) == 0
    return out.read_text(encoding="utf-8").splitlines()


def fw(rid, version, ts, kernel, build, **kw):
    return row(rid, version=version, build_timestamp=ts, kernel_release=kernel, build=build, **kw)


def test_table_has_the_expected_columns(tmp_path):
    lines = report(tmp_path, [row("a")])
    assert lines[0] == "| Device | Models | Regions | Android version | FW versions | Kernel | Build |"
    assert lines[1] == "|---|---|---|---|---|---|---|"
    assert lines[2] == f"| OP 13R | CPH2645 | EU | A15 | CPH2645_15.0.0.840(EX01) | `{KERNEL}` | `{BUILD}` |"


def test_rows_sharing_device_kernel_and_build_are_merged(tmp_path):
    rows = [row("a", version="CPH2653_15.0.0.100(EX01)", region="EU", device="OP 13", build_timestamp="2025-01-01T00:00:00"),
            row("b", version="CPH2653_15.0.0.100(EX01)", region="GLO", device="OP 13", build_timestamp="2025-01-01T00:00:00"),
            row("c", version="CPH2649_15.0.0.110(EX01)", region="IN", device="OP 13", build_timestamp="2025-02-01T00:00:00",
                android_version="16")]
    assert report(tmp_path, rows)[2:] == [
        f"| OP 13 | CPH2649<br>CPH2653 | EU<br>GLO<br>IN | A15<br>A16 | CPH2653_15.0.0.100(EX01)<br>CPH2649_15.0.0.110(EX01)"
        f" | `{KERNEL}` | `{BUILD}` |"]


def test_failed_and_pre_android_14_rows_are_left_out(tmp_path):
    rows = [row("a"), row("b", version="CPH2645_15.0.0.841(EX01)", ok=False),
            row("c", version="CPH2449_13.1.0.500(EX01)", android_version="13")]
    assert len(report(tmp_path, rows)) == 3


def test_unknown_android_version_is_marked(tmp_path):
    # OS 20+ is not covered by the version -> Android fallback, and this row has no OTA metadata
    line = report(tmp_path, [row("a", version="CPH2999_20.0.0.100(EX01)", android_version=None)])[2]
    assert "| ? |" in line


def test_devices_are_listed_alphabetically(tmp_path):
    rows = [row("a", version="CPH2653_15.0.0.100(EX01)", device="OP 13"),
            row("b", version="CPH2581_15.0.0.100(EX01)", device="OP 12")]
    assert [line.split(" | ")[0] for line in report(tmp_path, rows)[2:]] == ["| OP 12", "| OP 13"]


def test_older_builds_come_first(tmp_path):
    rows = [fw("new", "CPH2653_16.0.0.100(EX01)", "2025-09-01T00:00:00", "6.6.2", "#1 SMP Mon Sep 1 00:00:00 UTC 2025", device="OP 13"),
            fw("old", "CPH2653_15.0.0.100(EX01)", "2025-03-01T00:00:00", "6.6.1", "#1 SMP Mon Mar 3 00:00:00 UTC 2025", device="OP 13")]
    assert [line.split(" | ")[5] for line in report(tmp_path, rows)[2:]] == ["`6.6.1`", "`6.6.2`"]


def test_rows_without_an_ota_stamp_are_placed_by_their_kernel_build_date(tmp_path):
    rows = [fw("late", "CPH2653_16.0.0.100(EX01)", "2025-09-01T00:00:00", "6.6.3", "#1 SMP Mon Sep 1 00:00:00 UTC 2025", device="OP 13"),
            fw("archive", "CPH2653_15.0.0.500(EX01)", "", "6.6.2", "#1 SMP Tue Jun 10 08:00:00 UTC 2025", device="OP 13"),
            fw("early", "CPH2653_15.0.0.100(EX01)", "2025-03-01T00:00:00", "6.6.1", "#1 SMP Mon Mar 3 00:00:00 UTC 2025", device="OP 13")]
    assert [line.split(" | ")[5] for line in report(tmp_path, rows)[2:]] == ["`6.6.1`", "`6.6.2`", "`6.6.3`"]


def test_report_uses_one_device_label_per_model(tmp_path):
    rows = [row(f"a{i}", version=f"CPH2653_15.0.0.{i}00(EX01)", device="OP 13", kernel_release=f"6.6.{i}") for i in range(3)]
    rows.append(row("odd", version="CPH2653_16.0.0.210(EX01)", device="OP 13S", kernel_release="6.6.9"))
    assert {line.split(" | ")[0] for line in report(tmp_path, rows)[2:]} == {"| OP 13"}


def test_rows_follow_the_kernel_build_date_even_when_the_ota_stamps_disagree(tmp_path):
    # built first, packaged later (staged rollout): the table lists kernel builds
    rows = [fw("b", "CPH2653_15.0.0.200(EX01)", "2025-04-01T00:00:00", "6.6.2", "#1 SMP Mon Mar 10 00:00:00 UTC 2025", device="OP 13"),
            fw("a", "CPH2653_15.0.0.100(EX01)", "2025-05-01T00:00:00", "6.6.1", "#1 SMP Mon Feb 3 00:00:00 UTC 2025", device="OP 13")]
    assert [line.split(" | ")[5] for line in report(tmp_path, rows)[2:]] == ["`6.6.1`", "`6.6.2`"]
