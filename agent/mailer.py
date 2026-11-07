"""
Mailer: sends a drafted letter through any SMTP server (we use Brevo's free
tier; Gmail app passwords weren't available on a brand-new Google account).
Only letter.auto_letter() calls this, and only for audits whose worst
finding is "critical".

SEND_MODE in .env decides what happens:
  off    -> nothing (drafts only)
  outbox -> nothing is sent; the email is saved as a .eml file in data/outbox/
            (opens in any mail app). Works offline, safe demo fallback.
  test   -> DEFAULT. Sends to FROM_ADDRESS (your own inbox), with the real DPO
            address in the subject line. Full flow without emailing real companies.
  live   -> sends to the site's real DPO address.
In every mode Reply-To = REPLY_TO (defaults to FROM_ADDRESS), so replies land
in the Gmail inbox even though Brevo does the sending.

Safety limits in live mode (a sent email can't be taken back):
  - at most one email per website, ever (tracked in data/sent_log.json)
  - at most MAX_LIVE_PER_DAY live emails per day
  - never sends if there's no DPO address
Every attempt, sent or not, is logged in data/sent_log.json.

.env settings (Brevo values shown):
  SMTP_HOST=smtp-relay.brevo.com   SMTP_PORT=587   (587 = STARTTLS, 465 = SSL)
  SMTP_USER=<Brevo SMTP login>     SMTP_PASSWORD=<Brevo SMTP key>
  FROM_ADDRESS=<verified sender, e.g. MrGDPR5000@gmail.com>   REPLY_TO=<optional>
"""
import json
import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path

from .capture import base_domain

MAX_LIVE_PER_DAY = 5
DATA = Path(__file__).resolve().parent.parent / "data"
LOG_PATH = DATA / "sent_log.json"
OUTBOX = DATA / "outbox"


def _settings():
    """Read settings at send time (not import time), so editing .env + restarting works."""
    sender = os.getenv("FROM_ADDRESS", "").strip()
    return {
        "mode": os.getenv("SEND_MODE", "test").strip().lower(),
        "host": os.getenv("SMTP_HOST", "smtp-relay.brevo.com").strip(),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": os.getenv("SMTP_USER", "").strip(),
        "password": os.getenv("SMTP_PASSWORD", "").strip(),
        "from": sender,
        "reply_to": os.getenv("REPLY_TO", "").strip() or sender,
        "sender_name": os.getenv("SENDER_NAME", "Clype privacy audit"),
    }


def _load_log():
    try:
        return json.loads(LOG_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _append_log(entry):
    log = _load_log()
    log.append(entry)
    LOG_PATH.parent.mkdir(exist_ok=True)
    LOG_PATH.write_text(json.dumps(log, indent=2))


def _blocked_reason(site, dpo, log):
    """Why we must NOT send in live mode, or None if it's allowed."""
    if not dpo:
        return "No DPO email address for this site."
    if any(e.get("mode") == "live" and e.get("sent") and e.get("site") == site for e in log):
        return "Already emailed this site's DPO once (live mode sends one email per site)."
    today = datetime.now(timezone.utc).date().isoformat()
    sent_today = sum(1 for e in log if e.get("mode") == "live" and e.get("sent") and e.get("at", "").startswith(today))
    if sent_today >= MAX_LIVE_PER_DAY:
        return f"Daily limit reached ({MAX_LIVE_PER_DAY} live emails per day)."
    return None


def _build_message(s, to, subject, body):
    msg = EmailMessage()
    msg["From"] = formataddr((s["sender_name"], s["from"] or "clype@localhost"))
    msg["To"] = to
    msg["Reply-To"] = s["reply_to"] or s["from"]  # replies come back to the Gmail inbox
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain="clype.local")
    msg.set_content(body)
    return msg


def _smtp_send(s, msg):
    """Port 465 = SSL from the start; anything else (587) = plain then STARTTLS."""
    if s["port"] == 465:
        with smtplib.SMTP_SSL(s["host"], s["port"], timeout=20) as smtp:
            smtp.login(s["user"], s["password"])
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(s["host"], s["port"], timeout=20) as smtp:
            smtp.starttls()
            smtp.login(s["user"], s["password"])
            smtp.send_message(msg)


def send_letter(letter, audit):
    """Send (or save) the letter according to SEND_MODE. Returns a 'delivery' dict for the
    audit JSON. Never raises: a mail problem shouldn't lose the audit."""
    s = _settings()
    site = base_domain(audit.get("url", ""))
    dpo = (letter.get("to") or "").strip()
    delivery = {"mode": s["mode"], "sent": False, "to": None, "at": datetime.now(timezone.utc).isoformat(),
                "reason": None, "message_id": None, "site": site, "intended_to": dpo or None, "saved_to": None}
    subject = letter.get("subject") or f"Cookie and tracking concerns: {site}"
    body = letter.get("body") or ""

    if s["mode"] == "outbox":
        msg = _build_message(s, dpo or "no-dpo-address@unknown", subject, body)
        OUTBOX.mkdir(parents=True, exist_ok=True)
        path = OUTBOX / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}_{site}.eml"
        path.write_bytes(bytes(msg))
        delivery.update(saved_to=str(path.relative_to(DATA.parent)), message_id=msg["Message-ID"],
                        reason="Outbox mode: saved as a file, not sent.")
    elif s["mode"] not in ("test", "live"):
        delivery["reason"] = "SEND_MODE is off: drafted only."
    elif not (s["user"] and s["password"] and s["from"]):
        delivery["reason"] = "Email not set up: add SMTP_USER, SMTP_PASSWORD and FROM_ADDRESS to .env."
    elif s["mode"] == "live" and (why := _blocked_reason(site, dpo, _load_log())):
        delivery["reason"] = why
    else:
        to = dpo if s["mode"] == "live" else s["from"]
        if s["mode"] == "test":
            subject = f"[TEST, would go to {dpo or 'NO DPO ADDRESS'}] {subject}"
            body = ("TEST MODE: this email was sent to you, not the company. Set SEND_MODE=live in .env "
                    "to send critical letters to the real DPO.\n\n" + body)
        msg = _build_message(s, to, subject, body)
        try:
            _smtp_send(s, msg)
            delivery.update(sent=True, to=to, message_id=msg["Message-ID"])
        except Exception as e:
            delivery["reason"] = f"{type(e).__name__}: {e}"[:300]

    _append_log({k: delivery[k] for k in ("at", "site", "mode", "sent", "to", "intended_to", "reason",
                                          "message_id", "saved_to")} | {"subject": letter.get("subject")})
    return delivery
