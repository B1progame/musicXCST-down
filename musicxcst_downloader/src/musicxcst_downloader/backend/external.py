from __future__ import annotations

import webbrowser
from urllib.parse import urlparse


def is_safe_external_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def open_external_url(url: str) -> dict:
    if not is_safe_external_url(url):
        return {"ok": False, "error": "Only http and https links can be opened."}
    try:
        webbrowser.open(url, new=2, autoraise=True)
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

