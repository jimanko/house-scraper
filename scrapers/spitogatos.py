"""Spitogatos.gr scraper — selectors verified against live HTML (2025-05).

Bot protection note: spitogatos.gr uses DataDome/Reese. The challenge cookie
is called `reese84` (not `datadome`). Provide it via the SPITOGATOS_COOKIE
env var (value: `reese84=<value from browser DevTools>`). Without it every
request returns the 2752-char "Pardon Our Interruption" challenge page.

The reese84 cookie expires roughly every month. When it does, the scraper
logs a "blocked" warning and returns no results. Refresh it by visiting
spitogatos.gr in your browser, copying the updated reese84 cookie value
from DevTools → Application → Cookies, and updating the GitHub Secret.

Card structure (Nuxt.js SSR, verified):
  cards:    div.tile.tile--horizontal
  id/url:   a.tile__link[href]  →  /aggelia/<numeric-id>
  title:    h3.tile__title       e.g. "Διαμέρισμα, 100τ.μ."
  location: h3.tile__location    e.g. "Κρητικά (Γαλάτσι)"
  price:    p.price__text        e.g. "€750 / μήνα"
  size:     parsed from title text (digits before "τ.μ.")
  bedrooms: li[title='Υπνοδωμάτια'] span span
  image:    figure.tile__img img[src|data-src]
"""
from __future__ import annotations

import logging
import os
import random
import re
import time
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from curl_cffi import requests as cf_requests

from .base import BaseScraper, Listing

log = logging.getLogger(__name__)

BASE = "https://www.spitogatos.gr"
_BLOCKED_MARKER = "Pardon Our Interruption"
_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "el-GR,el;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": BASE,
}


def _parse_cookie_str(cookie_str: str) -> dict[str, str]:
    """Convert 'reese84=<val>; other=x' → {'reese84': '<val>', 'other': 'x'}."""
    cookies: dict[str, str] = {}
    for part in cookie_str.split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            cookies[k.strip()] = v.strip()
    return cookies


class SpitogatosScraper(BaseScraper):
    def fetch(self, search_url: str) -> list[Listing]:
        log.info("Spitogatos: fetching %s", search_url)

        cookie_str = os.environ.get("SPITOGATOS_COOKIE", "")
        if not cookie_str:
            log.warning(
                "Spitogatos: SPITOGATOS_COOKIE not set — requests will likely be blocked "
                "by DataDome. Set it to `reese84=<value>` from your browser cookies."
            )
        cookies = _parse_cookie_str(cookie_str) if cookie_str else {}

        time.sleep(random.uniform(2.0, 5.0))
        try:
            resp = cf_requests.get(
                search_url,
                impersonate="chrome",
                cookies=cookies,
                headers=_HEADERS,
                timeout=20,
            )
        except Exception as exc:
            log.error("Spitogatos: request failed — %s", exc)
            return []

        if resp.status_code == 403:
            log.warning(
                "Spitogatos: HTTP 403 — DataDome is blocking this IP or the reese84 "
                "token was invalidated server-side. Refresh SPITOGATOS_COOKIE from "
                "your browser and update the GitHub Secret."
            )
            return []

        if resp.status_code != 200:
            log.error("Spitogatos: unexpected HTTP %d for %s", resp.status_code, search_url)
            return []

        if _BLOCKED_MARKER in resp.text:
            log.warning(
                "Spitogatos: blocked by DataDome challenge — the reese84 cookie is "
                "missing or expired. Refresh it from your browser and update the "
                "SPITOGATOS_COOKIE secret."
            )
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        listings = self._parse(soup, search_url)
        log.info("Spitogatos: %d listings parsed", len(listings))
        return listings

    def _parse(self, soup: BeautifulSoup, page_url: str) -> list[Listing]:
        cards = soup.select("div.tile.tile--horizontal")
        if not cards:
            log.warning("Spitogatos: no cards found — page structure may have changed")
        results = []
        for card in cards:
            try:
                l = self._parse_card(card, page_url)
                if l:
                    results.append(l)
            except Exception as exc:
                log.warning("Spitogatos: failed to parse card — %s", exc)
        return results

    def _parse_card(self, card, page_url: str) -> Listing | None:
        # ID + URL from a.tile__link
        a_link = card.select_one("a.tile__link[href]")
        if not a_link:
            return None
        href = a_link["href"]
        m = re.search(r"/aggelia/(\d+)", href)
        if not m:
            return None
        listing_id = m.group(1)
        url = urljoin(BASE, href)

        # Title: "Διαμέρισμα, 100τ.μ."
        title_el = card.select_one("h3.tile__title")
        title = title_el.get_text(strip=True) if title_el else "—"

        # Location: "Κρητικά (Γαλάτσι)"
        loc_el = card.select_one("h3.tile__location")
        location = loc_el.get_text(strip=True) if loc_el else "—"

        # Price: "€750 / μήνα"
        price_el = card.select_one("p.price__text")
        price = None
        if price_el:
            digits = re.sub(r"[^\d]", "", price_el.get_text())
            price = int(digits) if digits else None

        # Size: from title text e.g. "100τ.μ."
        size_m = re.search(r"(\d+)\s*τ\.μ\.", title)
        size_sqm = int(size_m.group(1)) if size_m else None

        # Bedrooms: li[title='Υπνοδωμάτια'] > span > span (the numeric part)
        bed_li = card.select_one("li[title='Υπνοδωμάτια'] span span")
        bedrooms = None
        if bed_li:
            m2 = re.search(r"\d+", bed_li.get_text())
            bedrooms = int(m2.group()) if m2 else None

        # Image: first img that has src or data-src
        img_el = card.select_one("figure.tile__img img")
        image_url = None
        if img_el:
            image_url = img_el.get("src") or img_el.get("data-src")

        # Floor: best-effort from tile feature list (not always present in list view)
        floor: int | None = None
        floor_li = card.select_one("li[title='Επίπεδο'] span span, li[title='Όροφος'] span span")
        if floor_li:
            fm = re.search(r"-?\d+", floor_li.get_text())
            if fm:
                floor = int(fm.group())

        return Listing(
            id=listing_id,
            site="spitogatos",
            title=title,
            price=price,
            size_sqm=size_sqm,
            bedrooms=bedrooms,
            location=location,
            url=url,
            image_url=image_url,
            floor=floor,
        )
