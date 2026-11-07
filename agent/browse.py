"""
Browse step: after rejecting cookies, visit a few more same-site pages like
a normal visitor, so capture.py's request/cookie logging (already attached
to `page`) keeps running past just the landing page. Plain code, no AI.
"""
from .capture import base_domain

SKIP_KEYWORDS = [
    "cookie", "privacy", "legal", "terms", "about", "contact",
    "accessibility", "sitemap", "signin", "sign-in", "login", "log-in",
    "register", "account", "session",
]

def is_content_link(href):
    """False for non-content pages (cookie/privacy/login/account/...) and
    same-page anchor jumps (fragment-only links aren't real navigation)."""
    if "#" in href:
        return False
    href_lower = href.lower()
    return not any(word in href_lower for word in SKIP_KEYWORDS)

def find_internal_links(page, site_domain, limit=10):
    """Return a deduped list of same-site, content-looking URLs linked from
    the current page (skips cookie/privacy/legal/about-style pages)."""
    links = []
    seen = set()
    for frame in page.frames:
        try:
            hrefs = frame.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
        except Exception:
            continue
        for href in hrefs:
            if not href.startswith("http") or href in seen:
                continue
            seen.add(href)
            if base_domain(href) != site_domain:
                continue
            if not is_content_link(href):
                continue
            links.append(href)
            if len(links) >= limit:
                return links
    return links

def browse(page, site_domain, max_pages=3):
    """Visit a few same-site pages, waiting after each so capture.py can log their traffic."""
    links = find_internal_links(page, site_domain)
    visited = []
    for link_url in links[:max_pages]:
        try:
            page.goto(link_url)
            page.wait_for_timeout(2000)
            visited.append(link_url)
        except Exception:
            continue
    return visited
