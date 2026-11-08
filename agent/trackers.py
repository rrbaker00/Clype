"""
Tracker step: match request domains against a known-tracker list, so we
can say which company a request belongs to, not just the bare domain.

data/trackers.json is a slim domain -> company map derived from
DuckDuckGo's Tracker Radar (github.com/duckduckgo/tracker-radar),
build-data/generated/domain_map.json, stripped down to just displayName.
Real per-domain categories only exist in that project's 38,000+
individual domain files (too much to fetch for a 24h build), so the
category below is a small hand-curated guess for the companies most
likely to actually show up in an audit — "best effort", not official
Tracker Radar data.

TRACKER_COMPANIES doubles as the actual tracker allowlist: Tracker
Radar's domain map is an *ownership* map, not an *evil tracker* list — it
includes a site's own CDN and generic infra (Cloudflare, AWS, etc.)
right alongside ad-tech. Only companies listed here count as trackers;
everything else in the raw dataset is treated as not-a-tracker rather
than risk accusing a CDN of spying in a real complaint letter.

Same idea one level down, for big companies that do lots of non-tracking
things too (Google owns gstatic.com fonts and firebaseapp.com hosting,
Amazon owns AWS, Microsoft owns Office, Facebook owns reactjs.org...).
For those, MIXED_COMPANY_TRACKING_DOMAINS lists the domains that are
actually used for ads/analytics, and every other domain they own is
treated as not-a-tracker. Without this, a site using Google Fonts or
hosted on AWS would get "X tracked you after you rejected cookies".
"""
import json
import os
import re
from urllib.parse import unquote, urlparse

_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "trackers.json")

with open(_DATA_PATH) as f:
    _DOMAIN_TO_COMPANY = json.load(f)

# Tracker Radar company name -> (name we show, category).
# Keys must match data/trackers.json EXACTLY (e.g. "Amazon.com", not "Amazon"),
# otherwise that company silently never matches.
TRACKER_COMPANIES = {
    # Advertising
    "Google": ("Google", "Advertising"),
    "Facebook": ("Facebook", "Advertising"),
    "ByteDance": ("TikTok", "Advertising"),
    "Amazon.com": ("Amazon", "Advertising"),
    "Microsoft": ("Microsoft", "Advertising"),      # Bing Ads, LinkedIn, Xandr (adnxs.com), Clarity
    "Twitter": ("Twitter", "Advertising"),
    "Pinterest": ("Pinterest", "Advertising"),
    "Snap": ("Snap", "Advertising"),
    "Verizon Media": ("Yahoo", "Advertising"),
    "Oracle": ("Oracle", "Advertising"),
    "Criteo": ("Criteo", "Advertising"),
    "Taboola": ("Taboola", "Advertising"),
    "Outbrain": ("Outbrain", "Advertising"),
    "Quantcast": ("Quantcast", "Advertising"),
    "Magnite": ("Magnite", "Advertising"),
    "PubMatic": ("PubMatic", "Advertising"),
    "OpenX": ("OpenX", "Advertising"),
    "Index Exchange": ("Index Exchange", "Advertising"),
    "The Trade Desk": ("The Trade Desk", "Advertising"),
    "LiveRamp": ("LiveRamp", "Advertising"),
    "ID5": ("ID5", "Advertising"),
    "Lotame Solutions": ("Lotame", "Advertising"),
    "Permutive": ("Permutive", "Advertising"),
    "Teads": ("Teads", "Advertising"),
    "Adform": ("Adform", "Advertising"),
    "TripleLift": ("TripleLift", "Advertising"),
    "Media.net Advertising": ("Media.net", "Advertising"),
    "Sovrn Holdings": ("Sovrn", "Advertising"),
    "The Ozone Project": ("Ozone", "Advertising"),
    "Bounce Exchange": ("Bounce Exchange", "Advertising"),
    # Analytics / audience measurement
    "Adobe": ("Adobe", "Analytics"),
    "comScore": ("comScore", "Analytics"),
    "The Nielsen Company": ("Nielsen", "Analytics"),
    "Dotmetrics": ("Dotmetrics", "Analytics"),
    "Chartbeat": ("Chartbeat", "Analytics"),
    "Parsely": ("Parse.ly", "Analytics"),
    "Gemius": ("Gemius", "Analytics"),
    "Optimizely": ("Optimizely", "Analytics"),
    "Amplitude": ("Amplitude", "Analytics"),
    "Segment.io": ("Segment", "Analytics"),
    "Mixpanel": ("Mixpanel", "Analytics"),
    "Tealium": ("Tealium", "Analytics"),
    # Session replay (records clicks / scrolling / typing)
    "Hotjar": ("Hotjar", "Session replay"),
    "FullStory": ("FullStory", "Session replay"),
    "Mouseflow": ("Mouseflow", "Session replay"),
    "Crazy Egg": ("Crazy Egg", "Session replay"),
    "ContentSquare": ("Contentsquare", "Session replay"),
    "Lucky Orange": ("Lucky Orange", "Session replay"),
    "Quantum Metric": ("Quantum Metric", "Session replay"),
    # Performance monitoring: technically sends data, but mostly speed/error stats.
    # Kept separate so compare.py can treat it as low severity.
    "New Relic": ("New Relic", "Monitoring"),
    "Datadog": ("Datadog", "Monitoring"),
}

# For big companies that also run fonts / hosting / CDNs / normal products:
# ONLY these domains count as tracking. Everything else they own is ignored.
MIXED_COMPANY_TRACKING_DOMAINS = {
    "Google": {"google-analytics.com", "googletagmanager.com", "googletagservices.com",
               "doubleclick.net", "doubleclick.com", "googlesyndication.com",
               "googleadservices.com", "2mdn.net", "googleoptimize.com",
               "app-measurement.com",  # not adtrafficquality.google: that's ad-FRAUD detection, not tracking
               "youtube.com"},  # embedded YouTube sets tracking cookies (youtube-nocookie.com doesn't)
    "Microsoft": {"bing.com", "clarity.ms", "adnxs.com", "adnxs-simple.com", "appnexus.com",
                  "linkedin.com", "bizographics.com", "adsymptotic.com"},
    "Amazon.com": {"amazon-adsystem.com", "amazonadsystem.com", "assoc-amazon.com",
                   "assoc-amazon.co.uk", "associates-amazon.com", "serving-sys.com",
                   "sizmek.com", "peer39.com", "peer39.net", "alexametrics.com"},
    "Facebook": {"facebook.net", "facebook.com", "instagram.com", "atdmt.com",
                 "fbthirdpartypixel.com", "fbthirdpartypixel.net", "fbthirdpartypixel.org"},
    "Twitter": {"ads-twitter.com", "twitter.com", "x.com", "t.co"},
    "ByteDance": {"tiktok.com"},
    "Pinterest": {"pinterest.com"},
    "Snap": {"sc-static.net", "snapchat.com"},
    "Verizon Media": {"yahoo.com", "oath.com", "advertising.com"},
    "Oracle": {"bluekai.com", "bkrtx.com", "addthis.com", "moatads.com", "grapeshot.co.uk"},
    "Adobe": {"omtrdc.net", "demdex.net", "everesttech.net", "2o7.net", "adobedtm.com",
              "adobetarget.com"},
}

# Domains of a big company that are ANALYTICS, not advertising (the company's default category is
# Advertising). Without this, Google Analytics traffic counted as ad tracking and could make an audit
# "critical" (just-eat.co.uk: GA4 consent-mode pings after reject were called advertising).
ANALYTICS_DOMAINS = {"google-analytics.com", "app-measurement.com", "googleoptimize.com", "clarity.ms"}
SESSION_REPLAY_DOMAINS = {"clarity.ms"}   # Microsoft Clarity records sessions
# Tag LOADERS deliver other scripts and collect nothing themselves: their own category, the weakest,
# so they never decide a company's category (the tracking they load shows up on its own domains).
TAG_MANAGER_DOMAINS = {"googletagmanager.com", "adobedtm.com"}

# Exact hostnames that are trackers even though their domain isn't in the lists above.
TRACKER_HOSTS = {
    "snap.licdn.com": "Microsoft",  # LinkedIn Insight tag (licdn.com is otherwise LinkedIn's image CDN)
}

# Paths on non-tracking domains that ARE tracking (google.com is mostly search/maps/reCAPTCHA).
TRACKER_URL_PARTS = {
    "google.com/pagead/": "Google",       # ad conversion tracking
    "google.com/ads/": "Google",          # e.g. /ads/ga-audiences (remarketing)
    "google.co.uk/pagead/": "Google",
    "google.co.uk/ads/": "Google",
}


# Tracker cookies that sit on the SITE'S OWN domain (set by the tracker's script, e.g.
# Google Analytics' _ga on .bbc.co.uk). Matching by cookie domain alone misses these.
# Name prefix -> Tracker Radar company key (must be in TRACKER_COMPANIES).
FIRST_PARTY_TRACKER_COOKIES = {
    "_ga": "Google", "_gid": "Google", "_gat": "Google", "_gcl_": "Google",   # _ga also covers GA4's _ga_XXXX
    "_fbp": "Facebook", "_fbc": "Facebook",
    "_ttp": "ByteDance",
    "_uetsid": "Microsoft", "_uetvid": "Microsoft", "_clck": "Microsoft", "_clsk": "Microsoft",
    "_pin_unauth": "Pinterest",
    "_scid": "Snap",
    "__qca": "Quantcast",
    "_hj": "Hotjar",
    "_cb": "Chartbeat", "_chartbeat": "Chartbeat",
    "AMCV_": "Adobe", "s_vi": "Adobe", "s_ecid": "Adobe",
    "ajs_anonymous_id": "Segment.io", "ajs_user_id": "Segment.io",
    "_pcid": "Permutive", "permutive-id": "Permutive",
    "optimizelyEndUserId": "Optimizely",
}


# Values that mean "nothing stored" (sites often overwrite a cookie like this after you reject).
_PLACEHOLDERS = {"deleted", "null", "undefined", "none", "false", "0", "-1", "no", "off", "[]", "{}", '""', "''"}
# A unique ID: a run of 8+ letters/digits that mixes both (e.g. "ca770cfd...", a UUID part),
# or 8+ digits in a row (client IDs / first-visit timestamps like GA1.1.123456789.1700000000).
_ID_TOKEN = re.compile(r"(?=[A-Za-z0-9_-]*\d)(?=[A-Za-z0-9_-]*[A-Za-z])[A-Za-z0-9_-]{8,}|\d{8,}")


def cookie_value_kind(value):
    """What a cookie actually holds:
      "empty"        nothing, or only labels with nothing after them ("DeviceID=", "a=&b=")
      "placeholder"  a "nothing" word: deleted / null / 0 / false ...
      "id"           looks like a unique identifier (can recognise you again)
      "value"        something else (a word like "external", a language code, a flag)
    Empty and placeholder cookies are NOT counted as tracking evidence."""
    v = unquote(value or "").strip()
    if not v:
        return "empty"
    # "DeviceID=" / "id=&ts=" -> keep only the parts after each "="; nothing left = empty.
    if "=" in v:
        parts = [p.split("=", 1)[1].strip() for p in re.split(r"[&;|]", v) if "=" in p]
        if parts and not any(parts):
            return "empty"
    if v.lower() in _PLACEHOLDERS:
        return "placeholder"
    return "id" if _ID_TOKEN.search(v) else "value"


def holds_value(cookie):
    """False for empty / placeholder cookies. Old audits without value_kind count as holding a value."""
    return cookie.get("value_kind", "value") not in ("empty", "placeholder")


def owner(domain):
    """Company that owns a domain (Tracker Radar entity, e.g. "Google" for both google-analytics.com
    and doubleclick.net), or the domain itself if unknown. Used so a company passing data between
    its own domains isn't called a leak."""
    return _DOMAIN_TO_COMPANY.get(domain) or domain


def match_cookie(name, cookie_domain, site_domain):
    """Tracker dict for a cookie: known tracker cookie NAME first, then the cookie's domain."""
    for prefix, company in FIRST_PARTY_TRACKER_COOKIES.items():
        if name.startswith(prefix):
            shown, category = TRACKER_COMPANIES[company]
            return {"is_tracker": True, "company": shown, "category": category}
    return match(cookie_domain, site_domain)


def match(domain, site_domain, url=None):
    """Return the audit-format 'tracker' dict for a request's base domain.
    Tracker Radar's entity list includes first-party sites, CDNs, and
    generic infra too (it's an ownership map, not a tracking-only list) —
    a site's own domain is never a tracker, and only companies in
    TRACKER_COMPANIES count as known trackers.

    url (optional) lets us check the exact hostname/path, e.g. to tell
    LinkedIn's tracking script apart from LinkedIn's image CDN."""
    if domain == site_domain:
        return {"is_tracker": False}

    company = None
    if url:
        host = urlparse(url).hostname or ""
        company = TRACKER_HOSTS.get(host)
        if company is None:
            company = next((c for part, c in TRACKER_URL_PARTS.items() if part in url), None)

    if company is None:
        company = _DOMAIN_TO_COMPANY.get(domain)
        # Big mixed company? Only its known tracking domains count.
        allowed = MIXED_COMPANY_TRACKING_DOMAINS.get(company)
        if allowed is not None and domain not in allowed:
            return {"is_tracker": False}

    if company not in TRACKER_COMPANIES:  # also covers company is None
        return {"is_tracker": False}
    name, category = TRACKER_COMPANIES[company]
    if domain in TAG_MANAGER_DOMAINS:
        category = "Tag manager"
    elif domain in SESSION_REPLAY_DOMAINS:
        category = "Session replay"
    elif domain in ANALYTICS_DOMAINS:
        category = "Analytics"
    return {"is_tracker": True, "company": name, "category": category}
