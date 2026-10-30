"""URL redaction: OTA URLs are temporary and must not end up in logs/results."""
import re
from urllib.parse import urlparse

_URL = re.compile(r"https?://[^\s'\"<>)]+")


def redact(text: str) -> str:
    return _URL.sub(lambda m: f"<url {urlparse(m.group()).netloc}>", text)
