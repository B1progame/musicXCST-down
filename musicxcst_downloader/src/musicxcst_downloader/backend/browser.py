from __future__ import annotations

from urllib.parse import quote_plus, urlparse


BROWSER_HOME = "https://www.google.com/"


def normalize_browser_url(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return BROWSER_HOME
    parsed = urlparse(text if "://" in text else f"https://{text}")
    if parsed.scheme in {"http", "https"} and parsed.netloc and ("." in parsed.netloc or parsed.netloc == "localhost"):
        return parsed.geturl()
    return f"https://www.google.com/search?q={quote_plus(text)}"
