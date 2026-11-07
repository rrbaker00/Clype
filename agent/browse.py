"""
Browse step: after rejecting cookies, visit a few more same-site pages like
a normal visitor, so capture.py's request/cookie logging (already attached
to `page`) keeps running past just the landing page. Plain code, no AI.

Acting like a real visitor matters: many trackers only fire on scroll /
engagement (lazy-loaded ads, analytics "engaged time" pings, session
replay), so each page is scrolled down in steps, not just loaded.

Passive-only rule: never browse into sign-in / account pages. Links that
look like them are skipped, and if a page REDIRECTS to one anyway it's
dropped from visited_pages and we move on.
"""
from urllib.parse import urlparse

from .capture import base_domain

SKIP_KEYWORDS = [
    "cookie", "privacy", "legal", "terms", "about", "contact",
    "accessibility", "sitemap", "signin", "sign-in", "login", "log-in",
    "register", "account", "session", "auth", "notification", "subscribe",
    "checkout", "basket", "cart", "logout", "password",
]

# If we land on a URL containing one of these, it was a redirect to a login wall.
AUTH_WALL_KEYWORDS = ["signin", "sign-in", "login", "log-in", "account.", "/auth", "session."]


def is_content_link(href):
    """False for non-content pages (cookie/privacy/login/account/...) and
    same-page anchor jumps (fragment-only links aren't real navigation)."""
    if "#" in href:
        return False
    href_lower = href.lower()
    return not any(word in href_lower for word in SKIP_KEYWORDS)


def _same_page(a, b):
    """Same page, ignoring a trailing slash and #anchor."""
    return a.split("#")[0].rstrip("/") == b.split("#")[0].rstrip("/")


def _section(href):
    """First part of the path: /news/uk-123 -> 'news'. Used to spread visits across sections."""
    parts = [p for p in urlparse(href).path.split("/") if p]
    return parts[0] if parts else ""


def find_internal_links(page, site_domain, limit=10):
    """Return a deduped list of same-site, content-looking URLs linked from
    the current page (skips cookie/privacy/login-style pages and the page
    we're already on). One link per site section first, so 3 visits cover
    e.g. /news, /sport, /weather instead of three /news articles."""
    seen = {page.url.split("#")[0].rstrip("/")}
    candidates = []
    for frame in page.frames:
        try:
            hrefs = frame.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
        except Exception:
            continue
        for href in hrefs:
            key = href.split("#")[0].rstrip("/")
            if not href.startswith("http") or key in seen:
                continue
            seen.add(key)
            if base_domain(href) != site_domain or not is_content_link(href):
                continue
            if urlparse(href).path in ("", "/"):
                continue  # the homepage again
            candidates.append(href)

    # Spread across sections: first link of each new section, then the rest.
    first_per_section, rest, sections = [], [], set()
    for href in candidates:
        (rest if _section(href) in sections else first_per_section).append(href)
        sections.add(_section(href))
    return (first_per_section + rest)[:limit]


def scroll_like_a_visitor(page, steps=4, pause_ms=700):
    """Scroll down the page in steps so scroll/engagement trackers get a chance to fire."""
    for _ in range(steps):
        try:
            page.mouse.wheel(0, 1200)
        except Exception:
            return
        page.wait_for_timeout(pause_ms)


def browse(page, site_domain, max_pages=3):
    """Visit a few same-site pages, scrolling each, so capture.py can log their traffic.
    Returns the URLs we actually ended up on (not sign-in redirects)."""
    start_url = page.url
    scroll_like_a_visitor(page)  # the landing page counts too
    links = find_internal_links(page, site_domain)
    visited = []
    for link_url in links:
        if len(visited) >= max_pages:
            break
        try:
            page.goto(link_url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(1500)
        except Exception:
            continue
        landed = page.url.lower()
        if any(k in landed for k in AUTH_WALL_KEYWORDS) or base_domain(page.url) != site_domain:
            continue  # redirected to a login wall or off-site: don't count it, don't interact
        if _same_page(page.url, start_url) or any(_same_page(page.url, v) for v in visited):
            continue
        scroll_like_a_visitor(page)
        visited.append(page.url)
    return visited
