from helpers import release, row

from opkv import cli, sources
from opkv.extract import Result


def test_new_firmware_is_extracted_and_stored_without_its_url(run):
    extracted, rows = run([release("n1")], [])
    assert extracted == ["https://example.invalid/ota.zip"]
    assert [r["id"] for r in rows] == ["n1"]
    assert rows[0]["ok"] is True and rows[0]["kernel_release"] == "6.6.89-android15-8-gabc123"
    assert "source_url" not in rows[0]


def test_firmware_already_stored_under_another_id_is_not_extracted_again(run):
    extracted, rows = run([release("new-id")], [row("old-id")])
    assert extracted == []
    assert [r["id"] for r in rows] == ["old-id"]


def test_failed_row_is_retried_in_place_under_its_own_id(run):
    extracted, rows = run([release("new-id")], [row("old-id", ok=False)], "--retry-failed")
    assert len(extracted) == 1
    assert [(r["id"], r["ok"]) for r in rows] == [("old-id", True)]


def test_failed_row_is_left_alone_without_the_retry_flag(run):
    extracted, rows = run([release("new-id")], [row("old-id", ok=False)])
    assert extracted == []
    assert [(r["id"], r["ok"]) for r in rows] == [("old-id", False)]


def test_metadata_pass_fills_the_android_version_and_size_of_a_stored_row(run, monkeypatch):
    asked = []

    def fake_android(url):
        asked.append(url)
        return Result(ok=True, android_version="16", size=4242)

    monkeypatch.setattr(cli, "extract_android", fake_android)
    stored = row("old-id", size=0)
    del stored["android_version"]
    _, rows = run([release("new-id")], [stored])
    assert asked == ["https://example.invalid/ota.zip"]            # the release is found by firmware, not by id
    assert (rows[0]["android_version"], rows[0]["size"]) == ("16", 4242)


def test_metadata_pass_takes_the_md5_of_the_catalog_release(run):
    _, rows = run([release("new-id", md5="a" * 32)], [row("old-id", md5="")])
    assert rows[0]["md5"] == "a" * 32


def test_metadata_pass_takes_a_missing_md5_from_the_antirollchecker_index(run, monkeypatch):
    monkeypatch.setattr(sources, "arb_index", lambda: {("CPH2645_15.0.0.840(EX01)", "EU"): "f" * 32})
    _, rows = run([], [row("a", md5="")])
    assert rows[0]["md5"] == "f" * 32


def test_unreachable_antirollchecker_index_is_not_fatal(run, monkeypatch, capsys):
    def down():
        raise OSError("down")

    monkeypatch.setattr(sources, "arb_index", down)
    _, rows = run([], [row("a", md5="")])
    assert rows[0]["md5"] == "" and "antirollchecker index unavailable: OSError" in capsys.readouterr().err


def test_extraction_result_is_stored_with_its_size_and_android_version(run):
    _, rows = run([release("n1", size=0, md5="b" * 32)], [])
    assert (rows[0]["size"], rows[0]["android_version"], rows[0]["md5"]) == (1000, "15", "b" * 32)


def test_limit_caps_the_number_of_extractions(run):
    extracted, rows = run([release("a", version="CPH2645_15.0.0.1(EX01)"), release("b", version="CPH2645_15.0.0.2(EX01)")], [],
                          "--limit", "1")
    assert len(extracted) == 1 and len(rows) == 1


def test_failed_extraction_is_stored_with_its_error(run, monkeypatch):
    monkeypatch.setattr(cli, "extract", lambda url: Result(ok=False, error="HTTPError: HTTP Error 404: Not Found"))
    _, rows = run([release("a")], [])
    assert (rows[0]["ok"], rows[0]["error"]) == (False, "HTTPError: HTTP Error 404: Not Found")


def test_duplicates_in_the_stored_results_are_resolved_before_retrying(run):
    # a results file from an older version holding a good and a failed row of one firmware: nothing to retry
    extracted, rows = run([release("c")], [row("good"), row("bad", ok=False)], "--retry-failed")
    assert extracted == [] and [r["id"] for r in rows] == ["good"]
