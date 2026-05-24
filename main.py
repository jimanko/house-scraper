#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import logging
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

# Ensure UTF-8 stdout/stderr on Windows (avoids cp1252 encoding errors for Greek text)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import yaml

import notifier
from scrapers.base import Listing
from scrapers.spitogatos import SpitogatosScraper
from scrapers.xe import XeScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")

SEEN_FILE = Path(__file__).parent / "seen.json"
CONFIG_FILE = Path(__file__).parent / "config.yaml"
SEEN_TTL_DAYS = 30

_SCRAPERS = {
    "spitogatos": SpitogatosScraper(),
    "xe": XeScraper(),
}


# ---------------------------------------------------------------------------
# seen.json helpers
# ---------------------------------------------------------------------------

def _load_seen() -> dict[str, str]:
    if SEEN_FILE.exists():
        try:
            return json.loads(SEEN_FILE.read_text("utf-8"))
        except Exception as exc:
            log.warning("Could not parse seen.json, starting fresh: %s", exc)
    return {}


def _save_seen(seen: dict[str, str]) -> None:
    SEEN_FILE.write_text(json.dumps(seen, ensure_ascii=False, indent=2), "utf-8")


def _prune_seen(seen: dict[str, str]) -> dict[str, str]:
    cutoff = datetime.now(timezone.utc).timestamp() - SEEN_TTL_DAYS * 86400
    return {k: v for k, v in seen.items() if _ts(v) >= cutoff}


def _ts(iso: str) -> float:
    try:
        return datetime.fromisoformat(iso).timestamp()
    except Exception:
        return 0.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

def _passes(listing: Listing, filters: dict) -> bool:
    """Return True if the listing passes all configured local filters."""
    include_unknown = filters.get("include_unknown", True)

    # Price
    if filters.get("max_price"):
        if listing.price is None:
            if not include_unknown:
                return False
        elif listing.price > filters["max_price"]:
            return False

    # Size
    if filters.get("min_size"):
        if listing.size_sqm is None:
            if not include_unknown:
                return False
        elif listing.size_sqm < filters["min_size"]:
            return False

    # Bedrooms
    if filters.get("min_bedrooms"):
        if listing.bedrooms is None:
            if not include_unknown:
                return False
        elif listing.bedrooms < filters["min_bedrooms"]:
            return False
    if filters.get("max_bedrooms"):
        if listing.bedrooms is not None and listing.bedrooms > filters["max_bedrooms"]:
            return False

    # Year built
    if filters.get("min_year_built"):
        if listing.year_built is None:
            if not include_unknown:
                return False
        elif listing.year_built < filters["min_year_built"]:
            return False

    # Floor
    if filters.get("min_floor") or filters.get("exclude_ground_floor") or filters.get("exclude_basement"):
        floor = listing.floor
        if floor is not None:
            if filters.get("exclude_basement") and floor < 0:
                return False
            if filters.get("exclude_ground_floor") and floor == 0:
                return False
            if filters.get("min_floor") and floor < filters["min_floor"]:
                return False

    # Location filter: check if listing location contains any of the allowed area names
    location_filter = filters.get("location_filter")
    if location_filter:
        loc = (listing.location or "").lower()
        if not any(area.lower() in loc for area in location_filter):
            return False

    # Exclude keywords: reject if listing title/description contains any of these
    exclude_kw = filters.get("exclude_keywords", [])
    if exclude_kw:
        text = f"{listing.title} {listing.location}".lower()
        if any(kw.lower() in text for kw in exclude_kw):
            return False

    # Required keywords: each entry must match (if entry contains "|", treat as OR within that requirement).
    # This is a safety net for features like parking that can't be filtered via URL params.
    required_kw = filters.get("required_keywords", [])
    if required_kw:
        text = f"{listing.title} {listing.location} {listing.description or ''}".lower()
        for req in required_kw:
            # "|" means OR within one requirement
            alternatives = [alt.strip().lower() for alt in req.split("|")]
            if not any(re.search(alt, text) for alt in alternatives):
                return False

    return True


# ---------------------------------------------------------------------------
# Cookie expiry check
# ---------------------------------------------------------------------------

def _check_cookie_expiry(config: dict, email_to: str, dry_run: bool) -> None:
    expiry_cfg = config.get("cookie_expiry", {})
    today = date.today()
    for site, expiry_str in expiry_cfg.items():
        try:
            expiry = date.fromisoformat(str(expiry_str))
        except ValueError:
            log.warning("cookie_expiry.%s has invalid date '%s'", site, expiry_str)
            continue
        days_left = (expiry - today).days
        if days_left > 1:
            log.info("Cookie expiry — %s: %d days left (%s)", site, days_left, expiry)
            continue
        if days_left == 1:
            msg = f"⚠️ Το cookie για το {site} λήγει αύριο ({expiry})! Ανανέωσέ το από το browser σου και ενημέρωσε το GitHub Secret SPITOGATOS_COOKIE."
        elif days_left == 0:
            msg = f"⚠️ Το cookie για το {site} λήγει ΣΗΜΕΡΑ ({expiry})! Ανανέωσέ το άμεσα."
        else:
            msg = f"⚠️ Το cookie για το {site} έχει ήδη λήξει ({expiry} — πριν {abs(days_left)} μέρες). Το {site} παραλείπεται."
        log.warning(msg)
        if dry_run or not email_to or email_to == "YOUR_EMAIL@gmail.com":
            continue
        subject = f"⚠️ Cookie {site} λήγει {'αύριο' if days_left == 1 else 'σήμερα' if days_left == 0 else 'έχει ληξει'}"
        html = f"""<!DOCTYPE html><html lang="el"><head><meta charset="utf-8"></head>
<body style="background:#fafafa;padding:20px;font-family:Arial,sans-serif">
<div style="max-width:520px;background:#fff3cd;border:1px solid #ffc107;border-radius:8px;padding:20px">
<h2 style="color:#856404;margin-top:0">⚠️ Cookie {site} — ανανέωση απαιτείται</h2>
<p style="color:#333">{msg}</p>
<ol style="color:#333">
  <li>Άνοιξε <a href="https://www.spitogatos.gr/enoikiaseis-katoikies/galatsi">spitogatos.gr</a> στο browser σου</li>
  <li>F12 → Application → Cookies → www.spitogatos.gr → αντέγραψε <strong>reese84</strong></li>
  <li>GitHub repo → Settings → Secrets → ενημέρωσε <strong>SPITOGATOS_COOKIE</strong></li>
  <li>Ενημέρωσε <strong>cookie_expiry.spitogatos</strong> στο <code>config.yaml</code></li>
</ol>
</div></body></html>"""
        plain = msg + "\n\n1. spitogatos.gr → F12 → Cookies → reese84\n2. GitHub Secret SPITOGATOS_COOKIE\n3. config.yaml cookie_expiry.spitogatos"
        try:
            notifier.send_warning(subject, html, plain, email_to)
            log.info("Cookie expiry warning sent for %s", site)
        except Exception as exc:
            log.error("Failed to send cookie expiry warning: %s", exc)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    if not CONFIG_FILE.exists():
        log.error("config.yaml not found at %s", CONFIG_FILE)
        return 1

    config = yaml.safe_load(CONFIG_FILE.read_text("utf-8"))
    searches = config.get("searches", [])
    email_cfg = config.get("email", {})
    email_to = email_cfg.get("to", "")
    subject_prefix = email_cfg.get("subject_prefix", "🏠 Νέες αγγελίες")

    dry_run = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")
    _check_cookie_expiry(config, email_to, dry_run)

    seen = _load_seen()
    seen = _prune_seen(seen)

    # First-run detection: seen.json didn't exist or was empty before this run.
    # Seed all current listings silently without emailing — avoids a flood of
    # notifications for properties that were already listed before the scraper started.
    first_run = len(seen) == 0
    if first_run:
        log.info("First run detected — will seed seen.json without sending email.")

    # Group searches by site so we hit each site in one block (better rate limiting).
    by_site: dict[str, list[dict]] = defaultdict(list)
    for search in searches:
        by_site[search.get("site", "").lower()].append(search)

    all_new: list[Listing] = []
    hard_failure = False

    for site_name, site_searches in by_site.items():
        if site_name not in _SCRAPERS:
            log.error("Unknown site '%s' — skipping all its searches", site_name)
            continue

        for search in site_searches:
            name = search.get("name", search.get("url", "?"))
            url = search.get("url", "")
            filters = search.get("filters", {})

            log.info("── Running search: %s", name)
            try:
                listings = _SCRAPERS[site_name].fetch(url)
            except Exception as exc:
                log.error("Search '%s' failed: %s", name, exc)
                hard_failure = True
                continue

            filtered = [l for l in listings if _passes(l, filters)]
            log.info("  %d total / %d after filters", len(listings), len(filtered))

            new_count = 0
            for listing in filtered:
                key = f"{listing.site}:{listing.id}"
                if key not in seen:
                    if not first_run:
                        log.info("  NEW: %s — %s", key, listing.title)
                        all_new.append(listing)
                    seen[key] = _now_iso()
                    new_count += 1
                else:
                    seen[key] = _now_iso()

            if first_run and new_count:
                log.info("  Seeded %d listings (first run, no email)", new_count)

    _save_seen(seen)
    log.info("seen.json updated (%d entries)", len(seen))

    if first_run:
        log.info("First run complete — seeded %d total listings. Email will start from next run.", len(seen))
        return 0

    if all_new:
        log.info("Sending email for %d new listing(s)…", len(all_new))
        if dry_run:
            log.info("DRY_RUN=1 — skipping real email send")
            for l in all_new:
                print(f"  [{l.site}] {l.title} | {l.price}€ | {l.size_sqm}m² | {l.location}")
                print(f"    {l.url}")
        else:
            if not email_to or email_to == "YOUR_EMAIL@gmail.com":
                log.error("email.to not configured — skipping send")
            else:
                try:
                    notifier.send(all_new, email_to, subject_prefix)
                    log.info("Email sent to %s", email_to)
                except Exception as exc:
                    log.error("Failed to send email: %s", exc)
                    hard_failure = True
    else:
        log.info("No new listings found.")

    return 1 if hard_failure else 0


if __name__ == "__main__":
    sys.exit(main())
