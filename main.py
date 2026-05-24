#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone
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
    """Return {composite_id: iso_timestamp} dict."""
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
    return {
        k: v
        for k, v in seen.items()
        if _ts(v) >= cutoff
    }


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
    if filters.get("max_price") and listing.price and listing.price > filters["max_price"]:
        return False
    if filters.get("min_size") and listing.size_sqm and listing.size_sqm < filters["min_size"]:
        return False
    if filters.get("min_bedrooms") and listing.bedrooms and listing.bedrooms < filters["min_bedrooms"]:
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
            log.warning("cookie_expiry.%s has invalid date format '%s' — skipping", site, expiry_str)
            continue
        days_left = (expiry - today).days
        if days_left > 1:
            log.info("Cookie expiry check — %s: %d days remaining (%s)", site, days_left, expiry)
            continue
        if days_left == 1:
            msg = f"⚠️ Το cookie για το {site} λήγει αύριο ({expiry})! Ανανέωσέ το από το browser σου και ενημέρωσε το GitHub Secret SPITOGATOS_COOKIE."
        elif days_left == 0:
            msg = f"⚠️ Το cookie για το {site} λήγει ΣΗΜΕΡΑ ({expiry})! Ανανέωσέ το άμεσα."
        else:
            msg = f"⚠️ Το cookie για το {site} έχει ήδη λήξει ({expiry} — πριν {abs(days_left)} μέρες). Το {site} παραλείπεται μέχρι να το ανανεώσεις."
        log.warning(msg)
        if dry_run:
            log.info("DRY_RUN — skipping cookie expiry warning email")
            continue
        if not email_to or email_to == "YOUR_EMAIL@gmail.com":
            continue
        subject = f"⚠️ Cookie {site} λήγει {'αύριο' if days_left == 1 else 'σήμερα' if days_left == 0 else 'έχει ληξει'}"
        html = f"""<!DOCTYPE html>
<html lang="el"><head><meta charset="utf-8"></head>
<body style="background:#fafafa;padding:20px;font-family:Arial,sans-serif">
<div style="max-width:520px;background:#fff3cd;border:1px solid #ffc107;border-radius:8px;padding:20px">
<h2 style="color:#856404;margin-top:0">⚠️ Cookie {site} — ανανέωση απαιτείται</h2>
<p style="color:#333">{msg}</p>
<h3 style="color:#333">Βήματα:</h3>
<ol style="color:#333">
  <li>Άνοιξε <a href="https://www.spitogatos.gr/enoikiaseis-katoikies/galatsi">spitogatos.gr</a> στο browser σου</li>
  <li>F12 → Application → Cookies → www.spitogatos.gr</li>
  <li>Αντέγραψε την τιμή του <strong>reese84</strong></li>
  <li>Πήγαινε στο GitHub repo → Settings → Secrets → ενημέρωσε το <strong>SPITOGATOS_COOKIE</strong></li>
  <li>Ενημέρωσε και το <strong>cookie_expiry.spitogatos</strong> στο <code>config.yaml</code></li>
</ol>
</div>
<p style="font-size:11px;color:#999;margin-top:16px">house-scraper · GitHub Actions</p>
</body></html>"""
        plain = msg + "\n\nΒήματα:\n1. spitogatos.gr → F12 → Application → Cookies → αντέγραψε το reese84\n2. GitHub Secret SPITOGATOS_COOKIE → ενημέρωσε\n3. config.yaml cookie_expiry.spitogatos → ενημέρωσε"
        try:
            notifier.send_warning(subject, html, plain, email_to)
            log.info("Cookie expiry warning email sent for %s", site)
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

    all_new: list[Listing] = []
    hard_failure = False

    for search in searches:
        name = search.get("name", search.get("url", "?"))
        site = search.get("site", "").lower()
        url = search.get("url", "")
        filters = search.get("filters", {})

        if site not in _SCRAPERS:
            log.error("Unknown site '%s' in search '%s' — skipping", site, name)
            continue

        log.info("── Running search: %s", name)
        try:
            listings = _SCRAPERS[site].fetch(url)
        except Exception as exc:
            log.error("Search '%s' failed with unexpected error: %s", name, exc)
            hard_failure = True
            continue

        filtered = [l for l in listings if _passes(l, filters)]
        log.info("  %d total / %d after filters", len(listings), len(filtered))

        for listing in filtered:
            key = f"{listing.site}:{listing.id}"
            if key not in seen:
                log.info("  NEW: %s — %s", key, listing.title)
                all_new.append(listing)
                seen[key] = _now_iso()
            else:
                seen[key] = _now_iso()  # refresh timestamp to avoid premature pruning

    _save_seen(seen)
    log.info("seen.json updated (%d entries)", len(seen))

    if all_new:
        log.info("Sending email for %d new listing(s)…", len(all_new))
        if dry_run:
            log.info("DRY_RUN=1 — skipping real email send")
            for l in all_new:
                print(f"  [{l.site}] {l.title} | {l.price}€ | {l.size_sqm}m² | {l.location}")
                print(f"    {l.url}")
        else:
            if not email_to or email_to == "YOUR_EMAIL@gmail.com":
                log.error("email.to not configured in config.yaml — skipping send")
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
