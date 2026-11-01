from helpers import release, row


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
