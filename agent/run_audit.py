"""
CLI: python -m agent.run_audit <url>

Glues the pipeline together in one real browser session: capture -> consent
-> browse (only if reject worked) -> policy + cookie policy -> trackers
-> compare -> AI legal review -> letter (auto for critical/high). Writes one audit JSON to audits/<site_domain>.json,
matching the shape in .claude/docs/audit-format.md. Other audits get a letter
later, only when the user asks for it — left as null here.
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
from .compare import compare, SEVERITY_ORDER
from . import legal_review
from . import letter
from . import llm

def tag_cookie_trackers(cookies, site_domain):
    """Add a tracker_company field to each cookie, per audit-format.md."""
    for c in cookies:
        domain = base_domain(c["domain"].lstrip("."))
        match = trackers.match_cookie(c["name"], domain, site_domain)  # name check catches first-party _ga, _fbp...
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

        visited = []
        if consent_result["rejected"]:
            phase_state["phase"] = "after_reject"
            page.wait_for_timeout(1000)
            visited = browse(page, site_domain, max_pages=3)
        # Read the policies even if reject failed: a "pay or consent" site (Guardian) still
        # has a policy worth checking. policy_texts are for the AI review, not saved in the JSON.
        policy_result, policy_texts = read_policy(page, cost=cost)

        # No successful reject = there is no "after reject", so don't label cookies that way.
        cookies_after = serialize_cookies(page.context.cookies()) if consent_result["rejected"] else []
        browser.close()

    tag_cookie_trackers(cookies_before, site_domain)
    tag_cookie_trackers(cookies_after, site_domain)

    for r in requests_list:
        r["tracker"] = trackers.match(r["domain"], site_domain, url=r["url"])  # url: lets trackers.py check the exact host

    cookies = {"before_consent": cookies_before, "after_reject": cookies_after}
    findings, summary = compare(requests_list, cookies, policy_result, consent_result)
    for f in findings:
        f["source"] = "observed"  # plain-code findings, straight from the evidence

    audit = {
        "url": url,
        "started_at": started_at,
        "duration_s": round(time.monotonic() - start, 2),
        "cost": cost.as_dict(),
        "consent": consent_result,
        "requests": requests_list,
        "cookies": cookies,
        "policy": policy_result,
        "visited_pages": visited,
        "findings": findings,
        "summary": summary,
        "letter": None,
    }

    # AI legal review (LLM job 4): reads the evidence + both policies, adds "source": "ai"
    # findings. Merged into the same list so the UI and the letter use them, worst first.
    ai_findings, audit["ai_review"] = legal_review.review(audit, policy_texts, cost=cost)
    audit["findings"] = sorted(findings + ai_findings, key=lambda f: SEVERITY_ORDER[f["severity"]])

    # Letter: critical audit -> draft + send (per SEND_MODE in .env), high -> draft only,
    # anything else -> None (the UI's "Create draft letter" button can still ask for one).
    audit["letter"] = letter.auto_letter(audit, cost=cost)
    audit["cost"] = cost.as_dict()          # again, so it includes the review + letter calls
    audit["duration_s"] = round(time.monotonic() - start, 2)

    with open(f"audits/{site_domain}.json", "w") as f:
        json.dump(audit, f, indent=2)
    return audit

def main():
    audit = run(sys.argv[1])
    print(json.dumps(audit["summary"], indent=2))

if __name__ == "__main__":
    main()
