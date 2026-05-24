from __future__ import annotations

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from scrapers.base import Listing

_CARD_CSS = """
  font-family:Arial,sans-serif;max-width:520px;border:1px solid #e0e0e0;
  border-radius:8px;overflow:hidden;margin:16px 0;box-shadow:0 2px 6px rgba(0,0,0,.08)
"""
_IMG_CSS = "width:100%;height:180px;object-fit:cover;display:block"
_BODY_CSS = "padding:12px 16px"
_TITLE_CSS = "margin:0 0 6px;font-size:16px;color:#212121"
_META_CSS = "margin:0 0 10px;font-size:13px;color:#555"
_BTN_CSS = (
    "display:inline-block;padding:8px 18px;background:#1a73e8;color:#fff;"
    "text-decoration:none;border-radius:5px;font-size:13px"
)


def _card(l: Listing) -> str:
    img = (
        f'<img src="{l.image_url}" alt="" style="{_IMG_CSS}">'
        if l.image_url
        else '<div style="height:180px;background:#f5f5f5"></div>'
    )
    price = f"{l.price:,} €/μήνα".replace(",", ".") if l.price else "—"
    size = f"{l.size_sqm} τ.μ." if l.size_sqm else "—"
    bed = f"{l.bedrooms} υπνοδ." if l.bedrooms else "—"
    meta = f"{price} · {size} · {bed} · {l.location}"
    return (
        f'<div style="{_CARD_CSS}">'
        f"{img}"
        f'<div style="{_BODY_CSS}">'
        f'<h3 style="{_TITLE_CSS}">{l.title}</h3>'
        f'<p style="{_META_CSS}">{meta}</p>'
        f'<a href="{l.url}" style="{_BTN_CSS}">Δες αγγελία →</a>'
        "</div></div>"
    )


def _build_html(listings: list[Listing]) -> str:
    cards = "\n".join(_card(l) for l in listings)
    return f"""<!DOCTYPE html>
<html lang="el"><head><meta charset="utf-8"></head>
<body style="background:#fafafa;padding:20px">
<h2 style="font-family:Arial,sans-serif;color:#333">
  🏠 {len(listings)} νέε{'ς' if len(listings) != 1 else ''} αγγελί{'ες' if len(listings) != 1 else 'α'}
</h2>
{cards}
<p style="font-family:Arial,sans-serif;font-size:11px;color:#999;margin-top:24px">
  Αυτόματη ειδοποίηση από house-scraper · GitHub Actions
</p>
</body></html>"""


def send_warning(subject: str, body_html: str, body_plain: str, to: str) -> None:
    """Send a plain warning email (cookie expiry, errors, etc.)."""
    gmail_user = os.environ["GMAIL_USER"]
    gmail_pass = os.environ["GMAIL_APP_PASSWORD"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = to
    msg.attach(MIMEText(body_plain, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as srv:
        srv.login(gmail_user, gmail_pass)
        srv.sendmail(gmail_user, [to], msg.as_bytes())


def send(listings: list[Listing], to: str, subject_prefix: str = "🏠 Νέες αγγελίες") -> None:
    """Send one consolidated HTML email for all new listings."""
    gmail_user = os.environ["GMAIL_USER"]
    gmail_pass = os.environ["GMAIL_APP_PASSWORD"]

    subject = f"{subject_prefix}: {len(listings)} νέε{'ς' if len(listings) != 1 else ''}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = to

    plain = "\n\n".join(
        f"{l.title}\n{l.url}\nΤιμή: {l.price} € | {l.size_sqm} τ.μ. | {l.location}"
        for l in listings
    )
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(_build_html(listings), "html", "utf-8"))

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as srv:
        srv.login(gmail_user, gmail_pass)
        srv.sendmail(gmail_user, [to], msg.as_bytes())
