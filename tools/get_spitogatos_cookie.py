#!/usr/bin/env python3
"""
Solve the DataDome challenge for spitogatos.gr using a headless browser,
then write the reese84 cookie to GITHUB_ENV so the scraper can use it
in the same Actions run (same IP = cookie is valid).

Falls back to SPITOGATOS_COOKIE_SECRET env var if the browser fails.
"""
from __future__ import annotations

import os
import sys

SPITO_URL = "https://www.spitogatos.gr/enoikiaseis-katoikies/galatsi"
CHALLENGE_WAIT_MS = 10_000  # time for DataDome JS challenge to issue the cookie

# Inline stealth patches — avoids playwright-stealth version compatibility issues.
# Patches the properties DataDome probes most heavily.
_STEALTH_JS = """
// Remove the main headless signal
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// chrome object is absent in headless — add a minimal stub
if (!window.chrome) {
    window.chrome = { runtime: {} };
}

// Plugins array is empty in headless; real Chrome has at least PDF viewer
Object.defineProperty(navigator, 'plugins', {
    get: () => Object.assign([{ name: 'PDF Viewer', filename: 'internal-pdf-viewer' }],
                             { item: i => null, namedItem: n => null }),
});

// Language list matches the context locale we set
Object.defineProperty(navigator, 'languages', {
    get: () => ['el-GR', 'el', 'en-US', 'en'],
});

// Permissions probe used by DataDome to fingerprint headless
const _origQuery = window.navigator.permissions.query;
window.navigator.permissions.query = p =>
    p.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : _origQuery(p);
"""


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        print(f"[cookie] playwright not installed — {exc}", file=sys.stderr)
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
        ctx.add_init_script(_STEALTH_JS)
        page = ctx.new_page()

        try:
            print(f"[cookie] navigating to {SPITO_URL}")
            page.goto(SPITO_URL, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(CHALLENGE_WAIT_MS)
            print(f"[cookie] page title: {page.title()!r}")
        except Exception as exc:
            print(f"[cookie] navigation error — {exc}", file=sys.stderr)

        all_cookies = ctx.cookies()
        browser.close()

    reese84 = next((c for c in all_cookies if c["name"] == "reese84"), None)
    if reese84:
        cookie_val = f"reese84={reese84['value']}"
        print(f"[cookie] reese84 obtained ({len(reese84['value'])} chars)")
        _write_env("SPITOGATOS_COOKIE", cookie_val)
        return 0

    print("[cookie] reese84 not in browser cookies — DataDome challenge not solved", file=sys.stderr)
    return _fallback()


def _fallback() -> int:
    secret = os.environ.get("SPITOGATOS_COOKIE_SECRET", "")
    if secret:
        print("[cookie] falling back to stored SPITOGATOS_COOKIE_SECRET")
        _write_env("SPITOGATOS_COOKIE", secret)
    else:
        print("[cookie] no cookie available — spitogatos will return 0 results")
        _write_env("SPITOGATOS_COOKIE", "")
    return 0  # non-fatal: XE still runs


def _write_env(key: str, value: str) -> None:
    github_env = os.environ.get("GITHUB_ENV")
    if github_env:
        with open(github_env, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")
    else:
        preview = value[:60] + ("…" if len(value) > 60 else "")
        print(f"[cookie] {key}={preview}")


if __name__ == "__main__":
    sys.exit(main())
