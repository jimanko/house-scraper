#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test candidate spitogatos URL slugs.

Usage:
    set SPITOGATOS_COOKIE=reese84=<value>
    python tools/check_slugs.py
"""
from __future__ import annotations

import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from curl_cffi import requests as cf_requests

BASE = "https://www.spitogatos.gr"
_BLOCKED_MARKER = "Pardon Our Interruption"
COOKIE_STR = os.environ.get("SPITOGATOS_COOKIE", "")

if not COOKIE_STR:
    print("WARNING: SPITOGATOS_COOKIE not set — all responses will be DataDome challenge pages.")
    print("Set it to `reese84=<value>` from your browser cookies.\n")

cookies: dict[str, str] = {}
for part in COOKIE_STR.split(";"):
    if "=" in part:
        k, v = part.strip().split("=", 1)
        cookies[k.strip()] = v.strip()

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "el-GR,el;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": BASE,
}

CANDIDATES = {
    "Νέα Φιλαδέλφεια": [
        "nea-filadelfia",
        "nea-filadelfeia",
        "nea-filadelfeia-nea-chalkidona",
    ],
    "Νέο Ηράκλειο": [
        "neo-irakleio",
        "neo-iraklio",
    ],
    "Αγία Παρασκευή": [
        "agia-paraskevi",
        "ag-paraskevi",
    ],
    "Ψυχικό": [
        "psychiko",
        "neo-psychiko",
        "paleo-psychiko",
        "psychiko-neo-psychiko",
    ],
}


def check(slug: str) -> tuple[int, str]:
    url = f"{BASE}/enoikiaseis-katoikies/{slug}"
    try:
        r = cf_requests.get(url, impersonate="chrome", cookies=cookies,
                            headers=HEADERS, timeout=15, allow_redirects=True)
        if r.status_code == 200 and _BLOCKED_MARKER in r.text:
            return 200, "BLOCKED (DataDome)"
        return r.status_code, "OK" if r.status_code == 200 else f"HTTP {r.status_code}"
    except Exception as e:
        return -1, f"ERROR: {e}"


for area, slugs in CANDIDATES.items():
    print(f"\n{area}:")
    for slug in slugs:
        time.sleep(1.5)
        code, label = check(slug)
        print(f"  {label:<30}  /enoikiaseis-katoikies/{slug}")
