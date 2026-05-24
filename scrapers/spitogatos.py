"""Spitogatos.gr scraper.

NOTE: spitogatos.gr is protected by DataDome (a JS-challenge bot protection).
Pure requests CANNOT pass this challenge — the protection page sets a cookie
only after executing JavaScript. The scraper will log a clear warning when
blocked and return an empty list so the rest of the pipeline continues.

When/if the IP running this code is not challenged (e.g. trusted cloud IPs,
or after a session cookie is provided via SPITOGATOS_COOKIE env var), the
selectors below will parse the real listing cards.

Selector notes (based on spitogatos.gr HTML inspected via browser DevTools,
2025 layout):
  card:    article[data-id]  or  article.property-box
  id:      article[data-id] attribute
  url:     a.property-box__link
  title:   h2.property-box__title  or  h3
  price:   span.property-box__price
  size:    span.property-box__area  (contains "τ.μ.")
  beds:    span.property-box__bedrooms
  loc:     span.property-box__location
  image:   img inside .property-box__image
"""
from __future__ import annotations

import logging
import os
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import BaseScraper, Listing, _get

log = logging.getLogger(__name__)

BASE = "https://www.spitogatos.gr"
_DATADOME_MARKER = "Pardon Our Interruption"


def _parse_price(text: str) -> int | None:
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def _parse_int(text: str) -> int | None:
    m = re.search(r"\d+", text)
    return int(m.group()) if m else None


class SpitogatosScraper(BaseScraper):
    def fetch(self, search_url: str) -> list[Listing]:
        log.info("Spitogatos: fetching %s", search_url)

        # Optional: inject a real browser session cookie via env var
        extra_headers = {}
        cookie = os.environ.get("SPITOGATOS_COOKIE", "")
        if cookie:
            extra_headers["Cookie"] = cookie
            log.info("Spitogatos: using SPITOGATOS_COOKIE from env")

        try:
            resp = _get(search_url, referer=BASE, extra_headers=extra_headers)
        except Exception as exc:
            log.error("Spitogatos: request failed — %s", exc)
            return []

        if _DATADOME_MARKER in resp.text:
            log.warning(
                "Spitogatos: blocked by DataDome JS challenge — cannot scrape without "
                "a real browser session. Set SPITOGATOS_COOKIE env var with a valid "
                "datadome= cookie extracted from your browser to bypass this. Skipping."
            )
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        listings = self._parse(soup, search_url)
        log.info("Spitogatos: %d listings parsed", len(listings))
        return listings

    def _parse(self, soup: BeautifulSoup, page_url: str) -> list[Listing]:
        cards = soup.select("article[data-id]")
        if not cards:
            cards = soup.select("article.property-box, div.property-box")
        if not cards:
            log.warning("Spitogatos: no listing cards found — page structure may have changed")
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
        # ID
        listing_id = card.get("data-id", "")
        if not listing_id:
            a = card.select_one("a[href*='/property/']")
            if a:
                m = re.search(r"/property/(\d+)", a.get("href", ""))
                listing_id = m.group(1) if m else ""
        if not listing_id:
            return None

        # URL
        a_link = card.select_one("a.property-box__link, a[href*='/property/']")
        if not a_link:
            a_link = card.select_one("a[href]")
        href = a_link.get("href", "") if a_link else ""
        url = urljoin(BASE, href) if href else page_url

        # Title
        title_el = (
            card.select_one("h2.property-box__title")
            or card.select_one("h3.property-box__title")
            or card.select_one("h2")
            or card.select_one("h3")
        )
        title = title_el.get_text(strip=True) if title_el else "—"

        # Price
        price_el = card.select_one("span.property-box__price, [class*='price']")
        price = _parse_price(price_el.get_text()) if price_el else None

        # Size
        size_el = card.select_one("span.property-box__area, [class*='area'], [class*='size']")
        size_sqm = _parse_int(size_el.get_text()) if size_el else None
        if size_sqm is None:
            for node in card.find_all(string=re.compile(r"τ\.μ\.")):
                size_sqm = _parse_int(str(node))
                if size_sqm:
                    break

        # Bedrooms
        bed_el = card.select_one("span.property-box__bedrooms, [class*='bedroom']")
        bedrooms = _parse_int(bed_el.get_text()) if bed_el else None

        # Location
        loc_el = card.select_one(
            "span.property-box__location, [class*='location'], [class*='area-name']"
        )
        location = loc_el.get_text(strip=True) if loc_el else "—"

        # Image
        img_el = card.select_one(".property-box__image img, img[src]")
        image_url = None
        if img_el:
            image_url = img_el.get("src") or img_el.get("data-src")

        return Listing(
            id=str(listing_id),
            site="spitogatos",
            title=title,
            price=price,
            size_sqm=size_sqm,
            bedrooms=bedrooms,
            location=location,
            url=url,
            image_url=image_url,
        )
