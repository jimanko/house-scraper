"""XE.gr scraper — selectors verified against live HTML (2025-05)."""
from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import BaseScraper, Listing, _get

log = logging.getLogger(__name__)

BASE = "https://www.xe.gr"


def _parse_price(text: str) -> int | None:
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


class XeScraper(BaseScraper):
    def fetch(self, search_url: str) -> list[Listing]:
        log.info("XE: fetching %s", search_url)
        try:
            resp = _get(search_url, referer=BASE)
        except Exception as exc:
            log.error("XE: request failed — %s", exc)
            return []

        if resp.status_code == 403:
            log.warning("XE: got 403 (bot protection) — skipping")
            return []

        if resp.status_code != 200:
            log.error("XE: unexpected HTTP %d for %s", resp.status_code, search_url)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        listings = self._parse(soup, search_url)
        log.info("XE: %d listings parsed", len(listings))
        return listings

    def _parse(self, soup: BeautifulSoup, page_url: str) -> list[Listing]:
        # Verified selector: each card is a div.common-ad with id="common_property_ad_<uuid>"
        cards = soup.select("div.common-ad[id^='common_property_ad_']")
        if not cards:
            log.warning("XE: no cards found — page structure may have changed")
        results = []
        for card in cards:
            try:
                l = self._parse_card(card, page_url)
                if l:
                    results.append(l)
            except Exception as exc:
                log.warning("XE: failed to parse card — %s", exc)
        return results

    def _parse_card(self, card, page_url: str) -> Listing | None:
        # ID: strip "common_property_ad_" prefix from element id
        raw_id = card.get("id", "")
        listing_id = raw_id.replace("common_property_ad_", "").strip()
        if not listing_id:
            return None

        # URL: anchor inside .common-ad-body
        a = card.select_one(".common-ad-body a[href]")
        url = a["href"] if a and a["href"].startswith("http") else urljoin(BASE, a["href"] if a else "")

        # Title: h3 inside .common-property-ad-title
        title_el = card.select_one(".common-property-ad-title h3")
        title = title_el.get_text(strip=True) if title_el else "—"

        # Price: span.property-ad-price  e.g. "1.100 €"
        price_el = card.select_one("span.property-ad-price")
        price = _parse_price(price_el.get_text()) if price_el else None

        # Size: extracted from the title text "Διαμέρισμα 85 τ.μ."
        size_m = re.search(r"(\d+)\s*τ\.μ\.", title)
        size_sqm = int(size_m.group(1)) if size_m else None

        # Bedrooms: icon i.xe-bedroom followed by span "×2"
        bed_icon = card.select_one("i.xe-bedroom")
        bedrooms = None
        if bed_icon:
            span = bed_icon.find_next_sibling("span")
            if span:
                m = re.search(r"\d+", span.get_text())
                bedrooms = int(m.group()) if m else None

        # Location: h3.common-property-ad-address  "Βουλιαγμένη (Καβούρι) | Ενοικίαση κατοικίας"
        loc_el = card.select_one("h3.common-property-ad-address")
        location = loc_el.get_text(strip=True).split("|")[0].strip() if loc_el else "—"

        # Image: img inside .common-property-ad-image
        img_el = card.select_one(".common-property-ad-image img[src]")
        image_url = img_el["src"] if img_el else None

        # Floor: best-effort from feature list (not reliably present in XE list cards)
        floor: int | None = None
        floor_spans = card.select(".common-property-ad-details span")
        for sp in floor_spans:
            text = sp.get_text(strip=True)
            fm = re.search(r"όροφος\s*:?\s*(-?\d+)", text, re.IGNORECASE)
            if fm:
                floor = int(fm.group(1))
                break

        return Listing(
            id=listing_id,
            site="xe",
            title=title,
            price=price,
            size_sqm=size_sqm,
            bedrooms=bedrooms,
            location=location,
            url=url,
            image_url=image_url,
            floor=floor,
        )
