#!/usr/bin/env python3
"""
Solve the DataDome challenge for spitogatos.gr using a headless browser,
then write the reese84 cookie to GITHUB_ENV so the scraper can use it
in the same Actions run (same IP = cookie is valid).

Falls back to the SPITOGATOS_COOKIE_SECRET env var (the stored GitHub Secret)
if the browser approach fails, so the job never hard-fails.
"""
from __future__ import annotations

import os
import sys

SPITO_URL = "https://www.spitogatos.gr/enoikiaseis-katoikies/galatsi"
CHALLENGE_WAIT_MS = 10_000  # DataDome needs a few seconds to issue the cookie


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
        from playwright_stealth import stealth_sync
    except ImportError as exc:
        print(f"[cookie] import error — {exc}", file=sys.stderr)
        return _fallback()

    cookie_val: str | None = None

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="el-GR",
            timezone_id="Europe/Athens",
        )
        page = ctx.new_page()
        stealth_sync(page)

        try:
            print(f"[cookie] navigating to {SPITO_URL}")
            page.goto(SPITO_URL, wait_until="domcontentloaded", timeout=30_000)
            # Give DataDome time to run its JS challenge and issue the cookie
            page.wait_for_timeout(CHALLENGE_WAIT_MS)
            print(f"[cookie] page title: {page.title()!r}")
        except Exception as exc:
            print(f"[cookie] navigation error — {exc}", file=sys.stderr)

        all_cookies = ctx.cookies()
        browser.close()

    reese84 = next((c for c in all_cookies if c["name"] == "reese84"), None)
    if reese84:
        cookie_val = f"reese84={reese84['value']}"
        print(f"[cookie] reese84 obtained ({len(reese84['value'])} chars) — writing to GITHUB_ENV")
        _write_env("SPITOGATOS_COOKIE", cookie_val)
        return 0

    print("[cookie] reese84 not found in browser cookies — DataDome challenge may have failed", file=sys.stderr)
    return _fallback()


def _fallback() -> int:
    """Use the stored GitHub Secret as a fallback (may be expired)."""
    secret = os.environ.get("SPITOGATOS_COOKIE_SECRET", "")
    if secret:
        print("[cookie] falling back to stored SPITOGATOS_COOKIE_SECRET")
        _write_env("SPITOGATOS_COOKIE", secret)
    else:
        print("[cookie] no fallback available — spitogatos searches will return 0 results")
        _write_env("SPITOGATOS_COOKIE", "")
    return 0  # non-fatal: XE still runs fine


def _write_env(key: str, value: str) -> None:
    """Write key=value to GITHUB_ENV (makes it available to subsequent steps)."""
    github_env = os.environ.get("GITHUB_ENV")
    if github_env:
        with open(github_env, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")
    else:
        # Local run — just print
        preview = value[:60] + ("…" if len(value) > 60 else "")
        print(f"[cookie] {key}={preview}")


if __name__ == "__main__":
    sys.exit(main())
