from __future__ import annotations

import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

# Prefer curl_cffi for better TLS fingerprinting (bypasses some bot checks);
# fall back to requests if not installed.
try:
    from curl_cffi import requests as _requests_lib
    _IMPERSONATE = "chrome124"
    _USE_CURL = True
except ImportError:
    import requests as _requests_lib  # type: ignore[no-redef]
    _IMPERSONATE = None
    _USE_CURL = False

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "el-GR,el;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def _build_session():
    if _USE_CURL:
        session = _requests_lib.Session(impersonate=_IMPERSONATE)
    else:
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        session = _requests_lib.Session()
        retry = Retry(
            total=3,
            backoff_factor=1.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
    session.headers.update(HEADERS)
    return session


_SESSION = _build_session()


def _get(url: str, referer: str | None = None, extra_headers: dict | None = None):
    delay = random.uniform(2.0, 5.0)
    time.sleep(delay)
    headers = {}
    if referer:
        headers["Referer"] = referer
    if extra_headers:
        headers.update(extra_headers)
    response = _SESSION.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    return response


@dataclass
class Listing:
    id: str
    site: str
    title: str
    price: Optional[int]
    size_sqm: Optional[int]
    bedrooms: Optional[int]
    location: str
    url: str
    image_url: Optional[str]
    year_built: Optional[int] = None
    floor: Optional[int] = None
    description: Optional[str] = None


class BaseScraper(ABC):
    @abstractmethod
    def fetch(self, search_url: str) -> list[Listing]:
        """Fetch listings from a search results page."""
        ...
