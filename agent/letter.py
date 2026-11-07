"""
Letter step (LLM job 3): draft a complaint letter to the site's data
protection officer from the audit's findings (observed AND AI-review ones).

When it runs (see auto_letter below, called by run_audit.py):
  - audit's worst finding is "critical" -> draft, then mailer.py sends it (per SEND_MODE)
  - worst finding is "high"             -> draft only, never sent automatically
  - anything else                       -> nothing; the UI's "Create draft letter" button
                                           can still ask for one (POST /api/audits/{id}/letter)

Kind of letter: a complaint / notice of concerns asking for an explanation,
NOT a Subject Access Request. A SAR asks for *your* personal data, and the
audit used a fresh automated browser, not you, so a SAR doesn't fit.

Trust rules: the model only gets our findings + basic audit facts, must not
add facts, and AI-review findings are described as concerns, not proven breaches.
"""
import os
from datetime import datetime, timezone

from . import llm
from .compare import SEVERITY_ORDER

SENDER_NAME = os.getenv("SENDER_NAME", "Clype privacy audit")  # sign-off name, from .env
AUTO_DRAFT_TIERS = {"critical", "high"}
AUTO_SEND_TIERS = {"critical"}
LETTER_SEVERITIES = {"critical", "high", "medium"}  # low findings are left out of letters

SYSTEM_PROMPT = """You write formal complaint letters in UK English to a company's Data Protection \
Officer about cookie and tracking practices found by an automated privacy audit.

Rules:
- Use ONLY the facts provided. Do not add companies, numbers, dates, laws or claims that are not \
in the input. Do not guess what data was in the requests.
- Findings marked [observed] were measured directly: state them as facts.
- Findings marked [ai review] are an automated legal assessment: present them as concerns \
("our review suggests", "this appears to"), never as proven breaches.
- Explain the method once, briefly: an automated, passive audit with a fresh browser that \
clicked the cookie banner's reject option and recorded what was still sent.
- Ask the company to: (1) explain each point, (2) confirm which cookies/trackers they consider \
strictly necessary or exempt and why, (3) stop any non-essential tracking without consent, and \
(4) reply within one month.
- Mention that the matter may be raised with the Information Commissioner's Office (ICO) if not \
resolved. Do not threaten anything else.
- Polite, factual, under 450 words. No markdown, no bullet symbols other than numbered points.
- Sign off with exactly this name: %s

Respond with JSON only: {"subject": "...", "body": "..."}"""


def audit_tier(audit):
    """The audit's worst finding severity ('critical' / 'high' / 'medium' / 'low'), or None."""
    severities = [f.get("severity") for f in audit.get("findings", []) if f.get("severity") in SEVERITY_ORDER]
    return min(severities, key=SEVERITY_ORDER.get) if severities else None


def _facts(audit):
    """Plain-text input for the model: site, date, consent result, and the findings to raise."""
    c = audit.get("consent") or {}
    p = audit.get("policy") or {}
    lines = [
        f"Website: {audit.get('url')}",
        f"Audit date (UTC): {(audit.get('started_at') or '')[:16].replace('T', ' ')}",
        f"Cookie banner: found={c.get('banner_found')}, reject clicked={c.get('rejected')}, "
        f"buttons clicked: {', '.join(c.get('clicks') or []) or 'none'}",
        f"Pages browsed after reject: {', '.join(audit.get('visited_pages') or []) or 'none'}",
        f"Privacy policy reviewed: {p.get('url') or 'not found'}",
        "",
        "Findings to raise (worst first):",
    ]
    used = []
    for f in audit.get("findings", []):
        if f.get("severity") not in LETTER_SEVERITIES:
            continue
        tag = "ai review" if f.get("source") == "ai" else "observed"
        line = f"- [{tag}] [{f['severity']}] {f.get('title')}. {f.get('detail') or ''} Law: {f.get('law') or 'n/a'}."
        if f.get("policy_quote"):
            line += f' Policy says: "{f["policy_quote"]}"'
        lines.append(line)
        used.append(f.get("title"))
    return "\n".join(lines), used


def draft_letter(audit, cost=None):
    """Draft the letter. Returns the audit-format 'letter' dict. Never raises."""
    p = audit.get("policy") or {}
    to = p.get("dpo_contact")
    letter = {"kind": "complaint", "to": to or "", "subject": "", "body": "",
              "drafted_at": datetime.now(timezone.utc).isoformat(), "model": llm.STRONG_MODEL,
              "findings_used": [], "delivery": None}
    if not to:
        letter["note"] = "No DPO email found in the policy. Add one before sending."
    facts, used = _facts(audit)
    letter["findings_used"] = used
    if not used:
        letter["error"] = "No medium-or-worse findings to raise."
        return letter
    try:
        out = llm.ask_strong_json(facts, system=SYSTEM_PROMPT % SENDER_NAME, cost=cost) or {}
        letter["subject"] = str(out.get("subject") or "").strip()[:200] or f"Cookie and tracking concerns: {audit.get('url')}"
        letter["body"] = str(out.get("body") or "").strip()
        if not letter["body"]:
            letter["error"] = "Model returned an empty letter."
    except Exception as e:
        letter["error"] = f"{type(e).__name__}: {e}"[:300]
    return letter


def auto_letter(audit, cost=None):
    """What run_audit.py calls. Drafts for critical/high audits and sends for critical ones.
    Returns the letter dict, or None if this audit doesn't qualify (user can still request one)."""
    tier = audit_tier(audit)
    if tier not in AUTO_DRAFT_TIERS:
        return None
    letter = draft_letter(audit, cost=cost)
    letter["auto"] = {"tier": tier, "reason": f"Audit's worst finding is {tier}."}
    if tier in AUTO_SEND_TIERS and letter["body"] and not letter.get("error"):
        from . import mailer  # imported here so drafting works even with no email set up
        letter["delivery"] = mailer.send_letter(letter, audit)
    return letter
