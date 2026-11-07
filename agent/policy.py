"""
Policy step (job 2 of the 3 LLM jobs): find the privacy policy page and
ask the fast model to extract which companies it says data is shared
with, plus a contact email for data requests. Plain code finds the link
and grabs the page text; the LLM only reads and extracts, it never
navigates or clicks anything itself.

Trust rules (a wrong "not named in policy" finding is a false accusation):
  - Find the link by scoring every link on the page, not by the first
    thing that says "privacy" (that's often the banner's "Privacy settings").
  - Don't cut long policies blindly: keep the parts about sharing/partners.
  - If reading or extracting fails, say so ("error") so compare.py skips
    the "not named" check instead of treating an empty list as the truth.
  - Only keep a contact email that really appears in the policy text.
"""
import re
from urllib.parse import urlparse

from .capture import base_domain
from . import llm

# Policies are long. ~60k characters is about 15k tokens: still cheap on the fast model.
MAX_POLICY_CHARS = 60000

# A "policy" page shorter than this is probably a hub that links to the real policy.
HUB_PAGE_CHARS = 8000

# Link text that means "this is the full policy" (scored as a bonus in score_policy_link).
FULL_POLICY_PHRASES = [
    "full version",
    "full policy",
    "full privacy policy",
    "read the full",
    "complete policy",
]

# Consent-banner vendors: their own "privacy" links are about the vendor, not the site.
CMP_VENDOR_DOMAINS = {
    "onetrust.com", "cookielaw.org", "sourcepoint.com", "cookiebot.com", "didomi.io",
    "trustarc.com", "quantcast.com", "consensu.org", "usercentrics.eu", "iubenda.com",
}

# Lines worth keeping from a long policy: who data goes to, plus contact emails.
RELEVANT = re.compile(
    r"third[- ]part|partner|shar(e|ing)|disclos|recipient|processor|vendor|provider|"
    r"advertis|analytic|social media|cookie|transfer|sell|@",
    re.IGNORECASE,
)

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")


def score_policy_link(href, text, site_domain):
    """How likely a link is the site's privacy policy. Higher = better, None = never."""
    if not href.lower().startswith("http"):
        return None                     # javascript:, mailto:, etc.
    domain = base_domain(href)
    if domain in CMP_VENDOR_DOMAINS:
        return None                     # the banner vendor's policy, not this site's
    # Only the PATH counts: "privacy" inside a ?referrer=...privacy query string means nothing.
    path = urlparse(href).path.lower()
    text_l = (text or "").lower().strip()
    if "privacy" not in path and "privacy" not in text_l and "data protection" not in text_l:
        return None
    words = text_l + " " + path
    score = 0
    if "privacy" in path:
        score += 2
    if re.search(r"privacy[-_]?(policy|notice)", path):
        score += 2                      # /privacy-policy beats a general /privacy section
    if "privacy policy" in text_l or "privacy notice" in text_l:
        score += 3
    elif "privacy" in text_l or "data protection" in text_l:
        score += 1
    if any(p in text_l for p in FULL_POLICY_PHRASES):
        score += 3                      # "View the full version of the privacy policy"
    if re.search(r"setting|preference|choice|manage|centre|center", words):
        score -= 4                      # "Privacy settings" = the cookie pop-up, not the policy
    if "cookie" in words and "privacy" not in words:
        score -= 4                      # cookie-only policy ("Privacy and Cookies Policy" is fine)
    if re.search(r"child|kids|cbbc|u13|addendum|california|ccpa|video", words):
        score -= 3                      # side policies: children's / US-only / explainer videos
    if "#" in href:
        score -= 1                      # usually opens a pop-up rather than a page
    if domain != site_domain:
        score -= 2                      # allowed (parent company domains), but prefer the site's own
    return score


def _same_page(a, b):
    """True if two URLs are the same page (ignoring #anchors and a trailing slash)."""
    return a.split("#")[0].rstrip("/") == b.split("#")[0].rstrip("/")


def score_cookie_link(href, text, site_domain):
    """Same idea as score_policy_link, for the site's COOKIE policy page.
    Must avoid the banner's "Cookie settings" / "Manage cookies" buttons."""
    if not href.lower().startswith("http"):
        return None
    domain = base_domain(href)
    if domain in CMP_VENDOR_DOMAINS:
        return None
    path = urlparse(href).path.lower()
    text_l = (text or "").lower().strip()
    if "cookie" not in path and "cookie" not in text_l:
        return None
    words = text_l + " " + path
    score = 0
    if "cookie" in path:
        score += 2
    if re.search(r"cookies?[-_]?(policy|notice|statement)", path):
        score += 2
    if re.search(r"cookies? (policy|notice|statement)", text_l):
        score += 3
    elif "cookie" in text_l:
        score += 1
    if re.search(r"setting|preference|choice|manage|centre|center|consent", words):
        score -= 4                      # the cookie pop-up, not the cookie policy
    if "#" in href:
        score -= 1
    if domain != site_domain:
        score -= 2
    return score


def pick_policy_link(links, site_domain, exclude=(), scorer=score_policy_link):
    """links: [{"href", "text"}] -> best href, or None if nothing looks like a policy.
    exclude: URLs to skip (e.g. the page we're already on).
    scorer: score_policy_link (privacy policy) or score_cookie_link (cookie policy)."""
    scored = []
    for l in links:
        if any(_same_page(l["href"], x) for x in exclude):
            continue
        s = scorer(l["href"], l["text"], site_domain)
        if s is not None and s > 0:
            scored.append((s, l["href"]))
    return max(scored)[1] if scored else None


def page_links(page):
    """[{"href", "text"}] for every link on the page. Main frame only: banner iframes
    are where the misleading "Privacy settings" / vendor-policy links live."""
    try:
        return page.main_frame.eval_on_selector_all(
            "a[href]", "els => els.map(e => ({href: e.href, text: e.innerText}))")
    except Exception:
        return []


def find_policy_url(page, site_domain, exclude=(), scorer=score_policy_link):
    """Best privacy-policy (or, with scorer=score_cookie_link, cookie-policy) URL on the page."""
    return pick_policy_link(page_links(page), site_domain, exclude, scorer)


def select_relevant(text, max_chars=MAX_POLICY_CHARS):
    """Short policy -> all of it. Long policy -> the lines about sharing/partners/contacts
    plus the 10 lines after each (lists of company names often follow a heading)."""
    if len(text) <= max_chars:
        return text
    lines = [l for l in text.splitlines() if l.strip()]
    keep = set()
    for i, line in enumerate(lines):
        if RELEVANT.search(line):
            keep.update(range(max(0, i - 1), min(len(lines), i + 11)))
    out, total = [], 0
    for i in sorted(keep):
        if total + len(lines[i]) > max_chars:
            break
        out.append(lines[i])
        total += len(lines[i]) + 1
    # Nothing matched (odd page layout)? Better the start of the policy than nothing at all.
    return "\n".join(out) if out else text[:max_chars]


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
    # 1500 output tokens: some policies list dozens of partners; 800 could cut the JSON off mid-list.
    return llm.ask_fast(prompt, json_schema=True, max_tokens=1500, cost=cost)


def clean_contact(candidate, text):
    """Keep the model's email only if it really appears in the policy (no invented addresses).
    If the model gave none, fall back to an email in the text that looks privacy-related."""
    if isinstance(candidate, str) and candidate.strip() and candidate.strip().lower() in text.lower():
        return candidate.strip()
    for m in EMAIL.finditer(text):
        if re.search(r"privacy|dpo|data|gdpr", m.group(0), re.IGNORECASE):
            return m.group(0)
    return None


def read_cookie_policy(page, site_domain, cookie_href, result, texts):
    """Read the cookie policy into texts["cookie"] and record its URL in result.
    If it's the same page as the privacy policy (BBC: one combined policy), don't fetch twice."""
    if cookie_href is None:
        return
    if result.get("url") and _same_page(cookie_href, result["url"]):
        result["cookie_policy_url"] = result["url"]
        texts["cookie"] = texts["privacy"]
        return
    try:
        page.goto(cookie_href, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(1500)
        result["cookie_policy_url"] = page.url
        texts["cookie"] = page.inner_text("body")
    except Exception as e:
        result["cookie_policy_error"] = f"{type(e).__name__}: {e}"[:300]


def read_policy(page, cost=None):
    """Find and read the site's privacy policy AND cookie policy.
    Returns (policy dict for the audit JSON, {"privacy": text, "cookie": text}).
    The texts are NOT saved in the audit (too big); legal_review.py reads them.
    Never raises: a broken policy step shouldn't lose the whole audit."""
    result = {"url": None, "found": False, "companies_named": [], "dpo_contact": None,
              "cookie_policy_url": None}
    texts = {"privacy": "", "cookie": ""}
    site_domain = base_domain(page.url)

    # Pick both links from the same page before we navigate away from it.
    links = page_links(page)
    href = pick_policy_link(links, site_domain)
    cookie_href = pick_policy_link(links, site_domain, scorer=score_cookie_link)

    if href is None:
        read_cookie_policy(page, site_domain, cookie_href, result, texts)
        return result, texts
    try:
        page.goto(href, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(1500)
        result.update(url=page.url, found=True)
        full_text = page.inner_text("body")

        # Short page = probably a hub/summary (BBC, Guardian both do this) with the real
        # policy one more click away. Follow the best policy link on it, once.
        if len(full_text) < HUB_PAGE_CHARS:
            deeper = find_policy_url(page, site_domain, exclude=[href, page.url])
            if deeper is not None:
                page.goto(deeper, wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(1500)
                deeper_text = page.inner_text("body")
                if len(deeper_text) > len(full_text):   # only keep it if it's actually more policy
                    result["url"], full_text = page.url, deeper_text

        texts["privacy"] = full_text
        if cookie_href is None:  # not linked from the homepage? try the privacy policy page
            cookie_href = find_policy_url(page, site_domain, scorer=score_cookie_link)

        text = select_relevant(full_text)
        result["text_chars"] = len(full_text)       # so we can see if a policy was trimmed
        result["chars_sent"] = len(text)

        info = ask_ai_for_policy_info(text, cost=cost) or {}
        names = info.get("companies_named") or []  # "or []": the model may return null
        result["companies_named"] = [n.strip() for n in names if isinstance(n, str) and n.strip()]
        result["dpo_contact"] = clean_contact(info.get("dpo_contact"), full_text)
    except Exception as e:
        # We may have found the page but couldn't read it. compare.py sees "error" and
        # skips "not named in policy", because an empty list here means nothing.
        result["error"] = f"{type(e).__name__}: {e}"[:300]

    read_cookie_policy(page, site_domain, cookie_href, result, texts)
    return result, texts
