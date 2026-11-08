"""
Job 1: open a site and record every request + cookie it makes on load.
No consent handling and no tracker matching here yet — this is just the
raw capture, before/after-reject phase tagging comes with consent.py.
"""
import sys
import json
import tldextract
from playwright.sync_api import sync_playwright, Playwright

def base_domain(url):
    """Return the registrable domain (e.g. 'bbc.co.uk') for a URL."""
    ext = tldextract.extract(url)
    if not ext.suffix:  # no public suffix (localhost, IPs, made-up test domains like shop.example)
        return ".".join(p for p in (ext.subdomain, ext.domain) if p).removeprefix("www.")
    return f"{ext.domain}.{ext.suffix}"

def _body(request):
    """POST body as text (empty for GET). post_data crashes on binary (gzip) bodies: decode leniently."""
    try:
        return (request.post_data_buffer or b"").decode("utf-8", "ignore")[:20000]
    except Exception:
        return ""


def make_logger(site_domain):
    """Build a (requests_list, on_request_handler, phase_state) trio.
    Every captured request is tagged with phase_state['phase'] at the
    moment it fires — the caller flips phase_state['phase'] to
    'after_reject' once consent has actually been rejected."""
    requests_list = []
    phase_state = {"phase": "before_consent"}

    def on_request(request):
        requests_list.append({
            "url": request.url,
            "domain": base_domain(request.url),
            "third_party": base_domain(request.url) != site_domain,
            "method": request.method,
            "type": request.resource_type,
            "phase": phase_state["phase"],
            "_post": _body(request),   # for the ID-leak check (agent/crosssite.py); removed before saving
        })

    return requests_list, on_request, phase_state

def serialize_cookies(cookies):
    """Convert Playwright's cookie objects into plain JSON-safe dicts."""
    return [
        {
            "name": cookie["name"],
            "value": cookie["value"],
            "domain": cookie["domain"],
            "path": cookie["path"],
            "expires": cookie["expires"],
            "httpOnly": cookie["httpOnly"],
            "secure": cookie["secure"],
            "sameSite": cookie.get("sameSite"),
        }
        for cookie in cookies
    ]

def run(playwright: Playwright) -> None:
    """Load `url` headlessly, wait for it to settle, dump requests + cookies."""
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    page.on("request", on_request)
    page.goto(url)
    page.wait_for_timeout(3000)
    cookies = serialize_cookies(page.context.cookies())
    out_path = f"audits/{site_domain}.json"
    with open(out_path, "w") as f:
        json.dump({"requests": captured_requests, "cookies": cookies}, f, indent=4)

def main():
    global url, site_domain, captured_requests, on_request
    url = sys.argv[1]
    site_domain = base_domain(url)
    captured_requests, on_request, _ = make_logger(site_domain)
    with sync_playwright() as p:
        run(p)

if __name__ == "__main__":
    main()
