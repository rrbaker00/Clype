"""
CLI: python -m agent.run_audit <url>

Glues the pipeline together in one real browser session: capture -> consent
-> browse (only if reject worked) -> policy + cookie policy -> trackers
-> compare -> AI legal review -> letter (auto for critical/high).
Writes one audit JSON per run to audits/<timestamp>_<site_domain>.json,
matching the shape in .claude/docs/audit-format.md.

Reliability: every step is wrapped so one failure (slow site, weird banner,
LLM error) is recorded in audit["errors"] and the rest still runs. If the
site can't be loaded at all, a short audit with the error is still saved,
and no LLM calls are made.
"""
import re
import sys
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

from .capture import base_domain, make_logger, serialize_cookies
from .consent import reject_cookies
from .browse import browse
from . import trackers
from .policy import read_policy
from .compare import compare, SEVERITY_ORDER
from . import legal_review
from . import eu_law
from . import fingerprint
from . import letter
from . import llm

AUDITS_DIR = Path(__file__).resolve().parent.parent / "audits"   # project root, not the current folder
PAGE_TIMEOUT_MS = 30000   # max wait for the first page to load


def tag_cookie_trackers(cookies, site_domain):
    """Add tracker_company and value_kind (empty / placeholder / id / value) to each cookie."""
    for c in cookies:
        domain = base_domain(c["domain"].lstrip("."))
        match = trackers.match_cookie(c["name"], domain, site_domain)  # name check catches first-party _ga, _fbp...
        c["tracker_company"] = match["company"] if match["is_tracker"] else None
        c["value_kind"] = trackers.cookie_value_kind(c.get("value"))  # empty ones aren't tracking evidence
    return cookies


# Bot-protection pages (Akamai, Cloudflare, Incapsula...). Auditing one of these would
# "find nothing" and look like a clean site, so we treat them as "couldn't load".
BLOCK_TITLE = re.compile(r"access denied|just a moment|attention required|request unsuccessful|"
                         r"pardon our interruption|verifying device|challenge validation|are you a robot", re.I)


def blocked_reason(page, resp):
    """Why this page is a block/error page instead of the real site, or None if it looks fine."""
    status = resp.status if resp else None
    try:
        title = page.title() or ""
    except Exception:
        title = ""
    if status and status >= 400:
        return f"Site refused the automated browser (HTTP {status}{', ' + title[:60] if title else ''})."
    if BLOCK_TITLE.search(title):
        return f"Site showed a bot-protection page instead of the website ('{title[:60]}')."
    return None


def save(audit, site_domain, started):
    """audits/20261107T224100_bbc.co.uk.json: one file per run, so re-runs never overwrite."""
    AUDITS_DIR.mkdir(exist_ok=True)
    path = AUDITS_DIR / f"{started:%Y%m%dT%H%M%S}_{site_domain}.json"
    path.write_text(json.dumps(audit, indent=2))
    audit["id"] = path.stem
    return path


def run(url, progress=None):
    """Run a full audit. progress(step_text) is called as it goes (the dashboard shows it).
    Always returns an audit dict and always saves it, even if steps failed."""
    say = progress or (lambda text: None)
    site_domain = base_domain(url)
    cost = llm.Cost()
    started = datetime.now(timezone.utc)
    start = time.monotonic()
    errors = []

    def step(name, fn, default):
        """Run one pipeline step; on failure record the error and carry on with `default`."""
        say(name)
        try:
            return fn()
        except Exception as e:
            errors.append({"step": name, "error": f"{type(e).__name__}: {e}"[:300]})
            return default

    requests_list, on_request, phase_state = make_logger(site_domain)
    consent_result = {"banner_found": False, "rejected": False, "method": "failed", "clicks": []}
    policy_result = {"url": None, "found": False, "companies_named": [], "dpo_contact": None, "cookie_policy_url": None}
    policy_texts = {"privacy": "", "cookie": ""}
    cookies_before, cookies_after, visited = [], [], []
    loaded = False
    fp_events = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context()
            # Fingerprinting hooks: must be installed before the site's first script runs.
            fp_events = step("Watching for fingerprinting", lambda: fingerprint.install(context, phase_state), [])
            page = context.new_page()
            page.set_default_timeout(15000)          # no single click/wait can hang forever
            page.on("request", on_request)

            say("Opening the site")
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
                page.wait_for_timeout(3000)          # let trackers fire, like a real visitor would
                blocked = blocked_reason(page, resp)
                if blocked:
                    errors.append({"step": "Opening the site", "error": blocked})
                else:
                    loaded = True
            except Exception as e:
                errors.append({"step": "Opening the site", "error": f"{type(e).__name__}: {e}"[:300]})

            if loaded:
                cookies_before = step("Recording cookies before consent",
                                      lambda: serialize_cookies(page.context.cookies()), [])
                consent_result = step("Clicking reject on the cookie banner",
                                      lambda: reject_cookies(page, cost=cost), consent_result)
                if consent_result["rejected"]:
                    phase_state["phase"] = "after_reject"
                    page.wait_for_timeout(1000)
                    visited = step("Browsing pages after reject",
                                   lambda: browse(page, site_domain, max_pages=3), [])
                # Read the policies even if reject failed: a "pay or consent" site still has a
                # policy worth checking. policy_texts go to the AI review, not into the JSON.
                policy_result, policy_texts = step("Reading the privacy and cookie policies",
                                                   lambda: read_policy(page, cost=cost),
                                                   (policy_result, policy_texts))
                # No successful reject = there is no "after reject", so don't label cookies that way.
                if consent_result["rejected"]:
                    cookies_after = step("Recording cookies after reject",
                                         lambda: serialize_cookies(page.context.cookies()), [])
        finally:
            browser.close()                          # even if something above blew up

    tag_cookie_trackers(cookies_before, site_domain)
    tag_cookie_trackers(cookies_after, site_domain)
    for r in requests_list:
        r["tracker"] = trackers.match(r["domain"], site_domain, url=r["url"])  # url: lets trackers.py check the exact host

    cookies = {"before_consent": cookies_before, "after_reject": cookies_after}
    findings, summary = step("Comparing what we saw with the policy",
                             lambda: compare(requests_list, cookies, policy_result, consent_result), ([], {}))
    fp_findings = step("Checking for fingerprinting", lambda: fingerprint.findings(fp_events, site_domain), [])
    findings = sorted(findings + fp_findings, key=lambda f: SEVERITY_ORDER[f["severity"]])
    if summary:
        summary["fingerprinting_domains"] = sorted({base_domain(e["script"]) for e in fp_events})
    for f in findings:
        f["source"] = "observed"  # plain-code findings, straight from the evidence

    audit = {
        "url": url,
        "started_at": started.isoformat(),
        "duration_s": None,
        "cost": cost.as_dict(),
        "consent": consent_result,
        "requests": requests_list,
        "cookies": cookies,
        "policy": policy_result,
        "visited_pages": visited,
        "fingerprinting": fp_events,
        "findings": findings,
        "summary": summary,
        "letter": None,
        "loaded": loaded,
        "errors": errors,
    }

    if loaded:  # nothing to review or complain about if the site never loaded (saves API credit)
        # AI legal review (LLM job 4): adds "source": "ai" findings, merged in, worst first.
        ai_findings, audit["ai_review"] = step("AI legal review",
                                               lambda: legal_review.review(audit, policy_texts, cost=cost),
                                               ([], {"error": "review step failed"}))
        audit["findings"] = sorted(findings + ai_findings, key=lambda f: SEVERITY_ORDER[f["severity"]])
        # Letter: critical -> draft + send (per SEND_MODE), high -> draft only, else None.
        audit["letter"] = step("Drafting the letter", lambda: letter.auto_letter(audit, cost=cost), None)

    eu_law.add_eu_law(audit["findings"])    # "law_eu": EU GDPR / ePrivacy equivalents (plain code)
    audit["cost"] = cost.as_dict()          # final totals, including review + letter calls
    audit["duration_s"] = round(time.monotonic() - start, 2)
    audit["errors"] = errors
    say("Saving")
    save(audit, site_domain, started)
    return audit


def main():
    audit = run(sys.argv[1], progress=lambda text: print("...", text, flush=True))
    print(json.dumps(audit["summary"], indent=2))
    if audit["errors"]:
        print("errors:", json.dumps(audit["errors"], indent=2))


if __name__ == "__main__":
    main()
