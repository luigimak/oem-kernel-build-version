from opkv.safe import redact


def test_url_is_replaced_by_its_host():
    assert redact("failed https://cdn.example.com/a/b.zip?x=1 now") == "failed <url cdn.example.com> now"


def test_url_with_parentheses_in_the_path_is_redacted_whole():
    out = redact("boom https://cdn.example.com/dl/CPH2653_16.0.10.600(EX01).zip?Expires=123&Signature=SECRETSIG tail")
    assert out == "boom <url cdn.example.com> tail"


def test_url_ending_with_a_balanced_parenthesis_is_redacted_whole():
    assert redact("see https://cdn.example.com/dl/CPH2653(EX01)") == "see <url cdn.example.com>"


def test_punctuation_around_the_url_is_kept():
    assert redact("(see https://a.example/x?s=SECRET)") == "(see <url a.example>)"
    assert redact("got 'https://a.example/x?s=SECRET' back") == "got '<url a.example>' back"
    assert redact("at https://a.example/x?s=SECRET.") == "at <url a.example>."
    assert redact("<https://a.example/x?s=SECRET>") == "<<url a.example>>"


def test_every_url_in_the_text_is_redacted():
    assert redact("a http://one.example/x then HTTPS://two.example/y") == "a <url one.example> then <url two.example>"


def test_text_without_a_url_is_unchanged():
    assert redact("HTTPError: HTTP Error 404: Not Found") == "HTTPError: HTTP Error 404: Not Found"
