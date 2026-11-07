"""
CLI: python -m agent.run_audit <url>

Glues the pipeline together in one real browser session: capture -> consent
-> (stop early if there was no free way to reject) -> browse -> trackers
-> policy -> compare. Writes one audit JSON to audits/<site_domain>.json,
matching the shape in .claude/docs/audit-format.md. letter.py plugs in
separately (owned by the teammate) — left as null here.
"""
import sys
import json
import time
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

from .capture import base_domain, make_logger, serialize_cookies
from .consent import reject_cookies
from .browse import browse
from . import trackers
from .policy import read_policy
from .compare import compare
from . import llm

def tag_cookie_trackers(cookies, site_domain):
    """Add a tracker_company field to each cookie, per audit-format.md."""
    for c in cookies:
        domain = base_domain(c["domain"].lstrip("."))
        match = trackers.match(domain, site_domain)
        c["tracker_company"] = match["company"] if match["is_tracker"] else None
    return cookies

def run(url):
    site_domain = base_domain(url)
    cost = llm.Cost()
    started_at = datetime.now(timezone.utc).isoformat()
    start = time.monotonic()

    requests_list, on_request, phase_state = make_logger(site_domain)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.on("request", on_request)
        page.goto(url)
        page.wait_for_timeout(3000)

        cookies_before = serialize_cookies(page.context.cookies())
        consent_result = reject_cookies(page, cost=cost)

        policy_result = {"url": None, "found": False, "companies_named": [], "dpo_contact": None}
        visited = []
        if consent_result["rejected"]:
            phase_state["phase"] = "after_reject"
            page.wait_for_timeout(1000)
            visited = browse(page, site_domain, max_pages=3)
            policy_result = read_policy(page, cost=cost)

        cookies_after = serialize_cookies(page.context.cookies())
        browser.close()

    tag_cookie_trackers(cookies_before, site_domain)
    tag_cookie_trackers(cookies_after, site_domain)

    after_reject_tracker_matches = []
    for r in requests_list:
        match = trackers.match(r["domain"], site_domain)
        r["tracker"] = match
        if match["is_tracker"] and r["phase"] == "after_reject":
            after_reject_tracker_matches.append(match)

    findings, summary = compare(after_reject_tracker_matches, policy_result["companies_named"])

    audit = {
        "url": url,
        "started_at": started_at,
        "duration_s": round(time.monotonic() - start, 2),
        "cost": cost.as_dict(),
        "consent": consent_result,
        "requests": requests_list,
        "cookies": {"before_consent": cookies_before, "after_reject": cookies_after},
        "policy": policy_result,
        "visited_pages": visited,
        "findings": findings,
        "summary": summary,
        "letter": None,
    }

    with open(f"audits/{site_domain}.json", "w") as f:
        json.dump(audit, f, indent=2)
    return audit

def main():
    audit = run(sys.argv[1])
    print(json.dumps(audit["summary"], indent=2))

if __name__ == "__main__":
    main()
