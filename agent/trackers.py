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
"""
import json
import os

_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "trackers.json")

with open(_DATA_PATH) as f:
    _DOMAIN_TO_COMPANY = json.load(f)

CATEGORY_BY_COMPANY = {
    "Google": "Advertising",
    "Facebook": "Advertising",
    "ByteDance": "Advertising",
    "Amazon": "Advertising",
    "Microsoft": "Analytics",
    "Adobe": "Analytics",
    "Criteo": "Advertising",
    "Taboola": "Advertising",
    "Outbrain": "Advertising",
    "Hotjar": "Analytics",
    "Twitter": "Advertising",
    "LinkedIn": "Advertising",
    "Pinterest": "Advertising",
    "Oracle": "Advertising",
    "comScore": "Analytics",
    "Nielsen": "Analytics",
    "Quantcast": "Advertising",
    "Magnite": "Advertising",
    "PubMatic": "Advertising",
    "OpenX": "Advertising",
    "Index Exchange": "Advertising",
    "Xandr": "Advertising",
    "Yahoo": "Advertising",
    "Snap Inc.": "Advertising",
    "Amplitude": "Analytics",
    "Segment": "Analytics",
    "Mixpanel": "Analytics",
    "New Relic": "Analytics",
    "Datadog": "Analytics",
}

def match(domain, site_domain):
    """Return the audit-format 'tracker' dict for a request's base domain.
    Tracker Radar's entity list includes first-party sites too (it's an
    ownership map, not a tracking-only list) — a site's own domain is
    never a tracker, so site_domain is required, not optional."""
    if domain == site_domain:
        return {"is_tracker": False}
    company = _DOMAIN_TO_COMPANY.get(domain)
    if company is None:
        return {"is_tracker": False}
    return {
        "is_tracker": True,
        "company": company,
        "category": CATEGORY_BY_COMPANY.get(company),
    }
