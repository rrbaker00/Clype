"""
Policy step (job 2 of the 3 LLM jobs): find the privacy policy page and
ask the fast model to extract which companies it says data is shared
with, plus a contact email for data requests. Plain code finds the link
and grabs the page text; the LLM only reads and extracts, it never
navigates or clicks anything itself.
"""
from .consent import find_by_phrases
from . import llm

POLICY_PHRASES = [
    "privacy policy",
    "privacy notice",
    "data protection",
    "privacy",
]

FULL_POLICY_PHRASES = [
    "full version",
    "full policy",
    "full privacy policy",
    "read the full",
    "complete policy",
]

def find_policy_link(page):
    """Return the first visible privacy-policy link found in any frame, or None."""
    return find_by_phrases(page, POLICY_PHRASES)

def extract_page_text(page, max_chars=15000):
    """Grab the visible text of the current page, trimmed to a reasonable size."""
    return page.inner_text("body")[:max_chars]

def ask_ai_for_policy_info(text, cost=None):
    """Ask the fast model which companies are named and what the contact email is."""
    prompt = (
        "This is the text of a website's privacy policy. Identify: "
        "1) every named third-party company or service the site says it "
        "shares personal data with (not generic terms like \"advertising "
        "partners\" — only companies named by name), and 2) the single "
        "best contact email for a data request or complaint (DPO, "
        "privacy, or data protection contact), or null if none is given.\n\n"
        "Respond with JSON only, exactly two keys: \"companies_named\" "
        "(a list of strings) and \"dpo_contact\" (a string or null).\n\n"
        + text
    )
    return llm.ask_fast(prompt, json_schema=True, max_tokens=800, cost=cost)

def read_policy(page, cost=None):
    """Find and read the site's privacy policy. Returns the audit-format 'policy' dict."""
    link = find_policy_link(page)
    if link is None:
        return {"url": None, "found": False, "companies_named": [], "dpo_contact": None}
    link.click()
    page.wait_for_timeout(1500)

    full_link = find_by_phrases(page, FULL_POLICY_PHRASES)
    if full_link is not None:
        full_link.click()
        page.wait_for_timeout(1500)

    text = extract_page_text(page)
    info = ask_ai_for_policy_info(text, cost=cost)
    return {
        "url": page.url,
        "found": True,
        "companies_named": info.get("companies_named", []),
        "dpo_contact": info.get("dpo_contact"),
    }
