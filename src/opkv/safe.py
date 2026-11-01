"""URL redaction: OTA URLs are temporary and must not end up in logs/results."""
import re
from urllib.parse import urlparse

# up to the first space or quote: a signed URL can hold parentheses, e.g. ".../CPH2653_16.0(EX01).zip?Signature=..."
_URL = re.compile(r"https?://[^\s'\"<>]+", re.I)
_TRAILING = ".,;:!?)]}"


def _replace(m: re.Match) -> str:
    url, tail = m.group(), ""
    # punctuation of the surrounding text is not part of the URL; a closing parenthesis is, when it is balanced
    while url[-1] in _TRAILING and not (url[-1] == ")" and url.count("(") >= url.count(")")):
        url, tail = url[:-1], url[-1] + tail
    return f"<url {urlparse(url).netloc}>{tail}"


def redact(text: str) -> str:
    return _URL.sub(_replace, text)
