"""
Compare step: turn what we observed (requests, cookies, consent result)
plus what the policy says (companies_named) into findings + summary.
Plain code, no AI.

Rule for every finding: only claim what the evidence shows, and word it
so it stays true even in the "innocent" explanation. A wrong accusation
in front of judges (or in a real complaint letter) is worse than a
missed one.

Finding types, worst first:
  1. Tracker cookies set BEFORE you answered the banner        (PECR reg. 6)
  2. A tracker company still receiving data AFTER Reject all   (PECR reg. 6)
     - for 1 and 2, severity depends on category: ads/session replay = high,
       analytics = medium (some may be exempt), monitoring = low
  3. Reject only possible by paying/subscribing                (consent not freely given)
  4. Tracker companies not named in the privacy policy         (UK GDPR Art. 13(1)(e))
"""
import re

from .trackers import TRACKER_COMPANIES

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}  # "critical" only comes from the AI review safeguard

# How bad a tracker is, by category (from trackers.py).
CATEGORY_SEVERITY = {
    "Advertising": "high",
    "Session replay": "high",
    "Analytics": "medium",
    "Monitoring": "low",
}

# The same company under different names. Policies often say "Meta" or "YouTube"
# while our tracker list says "Facebook" or "Google". Each group = one company;
# the first name in each group is the key we compare on.
ALIASES = [
    ["facebook", "meta", "meta platforms", "instagram", "whatsapp"],
    ["google", "alphabet", "youtube", "doubleclick", "google analytics", "google ads",
     "google tag manager", "google marketing platform", "admob", "firebase"],
    ["twitter", "x", "x corp"],
    ["tiktok", "bytedance"],
    ["amazon", "amazon ads", "amazon advertising", "amazon alexa", "amazon web services", "aws"],
    ["microsoft", "linkedin", "bing", "xandr", "appnexus", "microsoft clarity", "clarity"],
    ["yahoo", "verizon media", "oath"],
    ["oracle", "bluekai", "addthis", "moat"],
    ["adobe", "adobe analytics"],
    ["comscore", "scorecard research", "scorecardresearch"],
    ["nielsen", "the nielsen company"],
    ["parse.ly", "parsely"],
    ["segment", "twilio segment"],
    ["snap", "snapchat"],
]
_ALIAS_TO_KEY = {alias: group[0] for group in ALIASES for alias in group}  # e.g. "youtube" -> "google"

# Bits of company names that don't help matching ("Google LLC" == "Google").
_SUFFIXES = r"\b(inc|ltd|limited|llc|plc|corp|corporation|co|gmbh|sa|ireland|uk)\b\.?"


def normalize(name):
    """'Meta Platforms Ireland Ltd.' -> 'meta platforms'. Lowercase, drop company suffixes."""
    name = re.sub(_SUFFIXES, "", name.lower())
    return re.sub(r"\s+", " ", name).strip(" .,")


def company_key(name):
    """One key per real company, so aliases compare equal: 'YouTube' and 'Google' -> same key."""
    n = normalize(name)
    if n in _ALIAS_TO_KEY:
        return _ALIAS_TO_KEY[n]
    # Policy names like "Google Analytics 4" or "Amazon Alexa skills": match a known
    # alias as a whole word inside the name. Skip 1-letter aliases ("x") to avoid nonsense.
    for alias, key in _ALIAS_TO_KEY.items():
        if len(alias) > 1 and re.search(rf"\b{re.escape(alias)}\b", n):
            return key
    return n


# "Chartbeat" -> "Analytics", using the shown names from trackers.py (for cookie-only companies).
_CATEGORY_BY_SHOWN_NAME = {shown: category for shown, category in TRACKER_COMPANIES.values()}


def _law(category, base):
    """Legal note for a tracking finding, softened where an exemption might apply."""
    if category == "Analytics":
        return base + ". Some audience-measurement analytics may be exempt under the Data (Use and Access) Act 2025"
    if category == "Monitoring":
        return "Possibly exempt: performance monitoring is usually treated as strictly necessary"
    return base


def _plural(n, word):
    """_plural(1, "request") -> "1 request", _plural(3, "company") -> "3 companies"."""
    if n == 1:
        return f"{n} {word}"
    return f"{n} {word[:-1]}ies" if word.endswith("y") else f"{n} {word}s"


def _group_trackers(requests, phase):
    """{company: {"category", "count", "domains"}} for tracker requests in one phase."""
    groups = {}
    for r in requests:
        t = r.get("tracker") or {}
        if not t.get("is_tracker") or r.get("phase") != phase:
            continue
        g = groups.setdefault(t["company"], {"category": t.get("category"), "count": 0, "domains": set()})
        g["count"] += 1
        g["domains"].add(r.get("domain"))
    return groups


def _tracker_cookies_by_company(cookies):
    """{company: [cookie names]} for cookies tagged as trackers."""
    out = {}
    for c in cookies:
        if c.get("tracker_company"):
            out.setdefault(c["tracker_company"], []).append(c["name"])
    return out


def compare(requests, cookies, policy, consent):
    """requests: run_audit's request list (each with "phase" and "tracker").
    cookies: {"before_consent": [...], "after_reject": [...]}, each tagged with tracker_company.
    policy: policy.py's dict (uses "found" and "companies_named").
    consent: consent.py's dict (uses "rejected" and "method").
    Returns (findings, summary) per .claude/docs/audit-format.md."""
    findings = []
    rejected = bool(consent.get("rejected"))
    named = policy.get("companies_named") or []
    named_keys = {company_key(c) for c in named}

    before = _group_trackers(requests, "before_consent")
    after = _group_trackers(requests, "after_reject") if rejected else {}
    cookies_before = _tracker_cookies_by_company(cookies.get("before_consent", []))
    cookies_after = _tracker_cookies_by_company(cookies.get("after_reject", [])) if rejected else {}
    before_cookie_names = {c["name"] for c in cookies.get("before_consent", [])}

    # Category for each company we saw anywhere: from its requests, or (cookie-only companies) from trackers.py.
    categories = {name: g["category"] for name, g in {**before, **after}.items()}
    for name in set(cookies_before) | set(cookies_after):
        categories.setdefault(name, _CATEGORY_BY_SHOWN_NAME.get(name))

    # 1. Tracker cookies already on your device before you'd answered the banner.
    for company, names in sorted(cookies_before.items()):
        category = categories.get(company)
        findings.append({
            "severity": CATEGORY_SEVERITY.get(category, "medium"),
            "title": f"{company} cookies were set before you could choose",
            "detail": f"{_plural(len(names), 'tracking cookie')} ({', '.join(sorted(names))}) "
                      f"{'was' if len(names) == 1 else 'were'} already set before the cookie banner "
                      f"was answered ({category or 'tracker'}).",
            "law": _law(category, "PECR reg. 6 (consent needed before storing cookies)"),
        })

    # 2. Companies still receiving data after Reject all.
    for company, g in sorted(after.items(), key=lambda kv: -kv[1]["count"]):
        new_cookies = [n for n in cookies_after.get(company, []) if n not in before_cookie_names]
        detail = (f"{_plural(g['count'], 'request')} to {', '.join(sorted(g['domains']))} "
                  f"after you clicked reject ({g['category'] or 'tracker'}).")
        if new_cookies:
            detail += f" New tracking cookies set after reject: {', '.join(sorted(new_cookies))}."
        findings.append({
            "severity": CATEGORY_SEVERITY.get(g["category"], "medium"),
            "title": f"{company} still received data after you rejected cookies",
            "detail": detail,
            "law": _law(g["category"], "PECR reg. 6 (cookies / tracking need consent)"),
        })

    # 3. The only way to say no costs money.
    if consent.get("method") == "pay_or_consent":
        findings.append({
            "severity": "medium",
            "title": "Rejecting cookies requires paying or subscribing",
            "detail": "The only reject option found was tied to a subscription or payment, so we did not click it.",
            "law": "UK GDPR Art. 4(11) and 7(4) (consent must be freely given). ICO allows 'consent or pay' only if it's fair",
        })

    # 4. Companies we saw that the policy never names. Only if we actually read a policy
    #    (found it AND extracted it without an error), otherwise "not named" would just
    #    mean "we couldn't read the policy".
    seen = sorted(set(before) | set(after) | set(cookies_before) | set(cookies_after))
    policy_read = policy.get("found") and not policy.get("error")
    not_disclosed = [c for c in seen if company_key(c) not in named_keys] if policy_read else []
    if not_disclosed:
        findings.append({
            "severity": "medium",
            "title": f"{_plural(len(not_disclosed), 'tracking company')} not named in the privacy policy",
            "detail": f"The policy names {_plural(len(named), 'company')}. We saw these and found no mention: "
                      f"{', '.join(not_disclosed)}. (The policy may describe them only by category, e.g. 'advertising partners'.)",
            "law": "UK GDPR Art. 13(1)(e) (you must be told who receives your data)",
        })

    findings.sort(key=lambda f: SEVERITY_ORDER[f["severity"]])

    summary = {
        "trackers_after_reject": sum(g["count"] for g in after.values()),  # tracker REQUESTS after reject
        "companies_seen": len(seen),
        "companies_in_policy": len(named),
        "companies_not_disclosed": not_disclosed,
        # New fields (added, nothing renamed, so the UI contract still holds):
        "companies_after_reject": sorted(after),
        "companies_with_cookies_before_consent": sorted(cookies_before),
        "categories": {c: categories.get(c) for c in seen},
    }
    return findings, summary
