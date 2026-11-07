"""
Compare step: match what trackers.py observed against what policy.py says
is disclosed, and produce the findings + summary the audit-format expects.
Plain code — no AI, just a set comparison between two lists of company
names.
"""

def normalize(name):
    """Lowercase + strip, for loose company-name matching."""
    return name.strip().lower()

def compare(tracker_matches, companies_named):
    """tracker_matches: list of trackers.py match dicts (the is_tracker=True
    ones, already filtered by the caller to whatever phase matters, e.g.
    after_reject). companies_named: policy.py's companies_named list.
    Returns (findings, summary) per the audit-format contract."""
    companies_seen = sorted({m["company"] for m in tracker_matches if m.get("company")})
    disclosed = {normalize(c) for c in companies_named}
    not_disclosed = [c for c in companies_seen if normalize(c) not in disclosed]

    findings = []
    for company in not_disclosed:
        count = sum(1 for m in tracker_matches if m.get("company") == company)
        findings.append({
            "severity": "high",
            "title": f"{company} tracked you after you rejected cookies",
            "detail": f"{count} request{'s' if count != 1 else ''} to {company} after rejecting.",
            "law": "PECR reg. 6",
        })

    summary = {
        "trackers_after_reject": len(tracker_matches),
        "companies_seen": len(companies_seen),
        "companies_in_policy": len(companies_named),
        "companies_not_disclosed": not_disclosed,
    }
    return findings, summary
