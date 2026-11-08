"""
Cross-site tracking evidence. Plain code, no AI. Research behind it:
reports/Cross site tracking detection.md (T1-T3).

Two parts:

A. ID leaks, inside every audit (find_ids + find_leaks + find_syncs + findings):
   1. Which cookie values are per-browser IDs? Compare the audit's cookies with a FRESH browser's
      cookies for the same site, piece by piece (OpenWPM / Chen et al.): a piece that differs
      clearly between the two browsers is an ID; a piece both browsers got is the same for everyone.
   2. Search every request to ANOTHER company (URL + POST body) for those IDs, raw or base64 /
      md5 / sha1 / sha256. A hit = "your ID was sent to X".
   3. Ad-tech cookie matching signatures (Google cookie match, Prebid "eids").

B. Linkage pass, on demand (linkage_pass): ONE browser visits site A then site B, rejecting each
   banner. Proof of cross-site recognition = the same per-browser ID (cookie value that isn't
   partitioned, or a confirmed ID) reaching the same company from both sites.

What we never claim (Playwright quirk, see the report): third-party localStorage matches. Playwright's
Chromium turns storage partitioning off, so those would be false proof. Only cookies + IDs in requests.
"""
import base64
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib.parse import unquote

from . import trackers
from .capture import base_domain

# ---------- what counts as an ID ----------
MIN_LEN, MAX_LEN = 8, 100                  # OpenWPM's length rule
_EXCLUDE = [
    re.compile(r"^1[5-9]\d{8}(\d{3})?$"),                  # epoch seconds / ms
    re.compile(r"^\d{4}-\d{2}-\d{2}"),                       # ISO dates
    re.compile(r"^(G|UA|GTM|AW|DC)-[A-Z0-9-]+$", re.I),      # property / container IDs (same for everyone)
    re.compile(r"^[a-z]{2}([-_][A-Za-z]{2})?$"),             # locales
    re.compile(r"^https?", re.I),
]
# Consent cookies are long and unique-looking but record your CHOICE, not you.
CONSENT_COOKIES = re.compile(r"^(euconsent-v2|addtl_consent|gdpr_consent|us_privacy|OptanonConsent|"
                             r"OptanonAlertBoxClosed|CookieConsent|didomi_token|consentUUID|_sp_|ckns_)", re.I)
_SPLIT = re.compile(r"[^A-Za-z0-9_\-]")    # splits on "." too, so GA's GA1.1.<rand>.<ts> gives <rand>


def tokens(text):
    """Candidate pieces of a value (and GA-style '<rand>.<ts>' pairs, which is what GA sends as cid)."""
    text = unquote(unquote(text or ""))
    out = {t for t in _SPLIT.split(text) if MIN_LEN <= len(t) <= MAX_LEN}
    out |= set(re.findall(r"\d{6,}\.\d{9,}", text))
    return {t for t in out if not any(p.search(t) for p in _EXCLUDE)}


def _differs(a, b):
    """Clearly different pieces (OpenWPM: similarity < 66%; Demir: lengths within 25%)."""
    if a == b or abs(len(a) - len(b)) > 0.25 * max(len(a), len(b)):
        return False
    return SequenceMatcher(None, a, b).ratio() < 0.66


def id_pieces(a, b):
    """Pieces of value a that are per-browser IDs, given the same cookie's value b from another
    fresh browser. Piece by piece, because 'GA1.1.<rand>.<ts>' shares 'GA1.1.' and a timestamp
    between browsers and would look 'similar' as a whole (Chen et al.'s fix)."""
    ta, tb = tokens(a), tokens(b)
    return {x for x in ta - tb if any(_differs(x, y) for y in tb - ta)}


def _variants(v):
    """The forms an ID is sent in (Chen et al. / Blacklight)."""
    b = v.encode()
    return {"raw": v, "base64": base64.b64encode(b).decode().rstrip("="),
            "base64url": base64.urlsafe_b64encode(b).decode().rstrip("="),
            "md5": hashlib.md5(b).hexdigest(), "sha1": hashlib.sha1(b).hexdigest(),
            "sha256": hashlib.sha256(b).hexdigest()}


def _cookie_owner(cookie):
    return base_domain(cookie["domain"].lstrip("."))


def cross_site_capable(cookie, site_domain):
    """A third-party cookie the browser will send from ANY site: SameSite=None, Secure, not partitioned."""
    return (_cookie_owner(cookie) != site_domain and cookie.get("sameSite") == "None"
            and cookie.get("secure") and "partitionKey" not in cookie)


def find_ids(cookies, fresh_cookies):
    """{piece: {"cookie", "cookie_domain", "confidence"}} for cookie values that are per-browser IDs.
    confidence: "confirmed" (differs from a fresh browser) or "likely" (fresh browser never got it)."""
    fresh = {(c["domain"], c["name"]): c["value"] for c in fresh_cookies}
    ids = {}
    for c in cookies:
        if CONSENT_COOKIES.search(c["name"]):
            continue
        other = fresh.get((c["domain"], c["name"]))
        if other is None:
            confidence, pieces = "likely", tokens(c["value"])
        else:
            confidence, pieces = "confirmed", id_pieces(c["value"], other)   # empty = same for everyone
        for t in pieces:
            ids.setdefault(t, {"cookie": c["name"], "cookie_domain": _cookie_owner(c), "confidence": confidence})
    return ids


# ---------- A. leaks inside one audit ----------
def find_leaks(requests, ids, site_domain):
    """Requests to another COMPANY carrying one of our IDs. One entry per (ID, receiver, phase).
    requests need "_post" (body text) as well as url / domain / phase."""
    lookup = {}
    for t in ids:
        for kind, v in _variants(t).items():
            lookup[v] = (t, kind)
    leaks = {}
    for r in requests:
        domain = r.get("domain")
        if not domain or domain == site_domain:
            continue
        for where, text in (("address", r.get("url")), ("body", r.get("_post"))):
            if not text:
                continue
            for tok in tokens(text) | set(re.findall(r"[a-f0-9]{32,64}", text)):
                hit = lookup.get(tok)
                if not hit:
                    continue
                t, kind = hit
                info = ids[t]
                if trackers.owner(domain) == trackers.owner(info["cookie_domain"]):
                    continue                                   # the ID's own company: not a leak
                key = (t, domain, r.get("phase"))
                if key not in leaks:
                    tr = trackers.match(domain, site_domain, url=r.get("url"))
                    leaks[key] = {
                        "cookie": info["cookie"], "cookie_domain": info["cookie_domain"],
                        "id_preview": t[:6] + "…" + t[-4:] if len(t) > 12 else t,   # enough to match, not the whole ID
                        "to": domain, "company": tr.get("company") if tr.get("is_tracker") else None,
                        "category": tr.get("category"), "phase": r.get("phase"), "in": where,
                        "encoding": kind, "confidence": info["confidence"], "example": r.get("url", "")[:160],
                        "_id": t,      # full ID, for the linkage pass only; removed before saving
                    }
    return list(leaks.values())


def find_syncs(requests):
    """Ad-tech cookie matching seen in requests: Google cookie match, Prebid "eids" (shared user IDs)."""
    out = []
    for r in requests:
        u, body = r.get("url", ""), r.get("_post") or ""
        if re.search(r"cm\.g\.doubleclick\.net/pixel|[?&]google_(gid|nid|push|hm)=", u):
            out.append({"type": "Google cookie matching", "to": r.get("domain"), "phase": r.get("phase"),
                        "example": u[:160]})
        if '"eids"' in body:
            try:
                eids = (json.loads(body).get("user") or {}).get("ext", {}).get("eids") or []
                sources = sorted({e.get("source") for e in eids if isinstance(e, dict) and e.get("source")})
            except Exception:
                sources = []
            if sources:
                out.append({"type": "Prebid shared user IDs", "to": r.get("domain"), "phase": r.get("phase"),
                            "sources": sources})
    return out


CATEGORY_SEVERITY = {"Advertising": "high", "Session replay": "high", "Analytics": "medium", "Monitoring": "low"}
_WHEN = {"before_consent": "before you answered the cookie banner", "after_reject": "after you rejected cookies"}


def findings(leaks, syncs):
    """Findings for KNOWN tracker companies only (an unknown receiver could be a CDN: we keep it in
    id_leaks as evidence but don't accuse anyone). One finding per (company, phase)."""
    out, groups = [], {}
    for l in leaks:
        if l["company"] and l["confidence"] == "confirmed":     # "likely" IDs: evidence only, no accusation
            groups.setdefault((l["company"], l["phase"]), []).append(l)
    for (company, phase), ls in sorted(groups.items()):
        category = ls[0]["category"]
        cookies = sorted({l["cookie"] for l in ls})
        law = ("PECR reg. 6 (reading an identifier stored on your device and sending it on is 'access' and "
               "needs consent); UK GDPR Art. 4(1) (an online identifier is personal data)")
        if category == "Analytics":
            law += ("; the 2025 statistics exemption (PECR Sch. A1 para 5) doesn't cover sharing with a "
                    "third party for its own purposes" + (", or continuing after you objected" if phase == "after_reject" else ""))
        out.append({
            "severity": CATEGORY_SEVERITY.get(category, "medium"),
            "title": f"Your ID was sent to {company} {_WHEN.get(phase, '')}".strip(),
            "detail": f"The value of {', '.join(cookies)} (an ID unique to this browser) was sent to "
                      f"{', '.join(sorted({l['to'] for l in ls}))} in the request "
                      f"{'address' if all(l['in'] == 'address' for l in ls) else 'address/body'}"
                      f"{' (encoded: ' + ', '.join(sorted({l['encoding'] for l in ls} - {'raw'})) + ')' if {l['encoding'] for l in ls} - {'raw'} else ''}. "
                      f"This lets {company} recognise this browser on later visits.",
            "law": law,
        })
    sync_groups = {}
    for s in syncs:
        sync_groups.setdefault(s["phase"], []).append(s)
    for phase, ss in sync_groups.items():
        kinds = sorted({s["type"] for s in ss})
        sources = sorted({x for s in ss for x in s.get("sources", [])})
        out.append({
            "severity": "high",
            "title": f"Ad companies matched IDs for this browser {_WHEN.get(phase, '')}".strip(),
            "detail": f"{' and '.join(kinds)} seen ({len(ss)} request{'s' if len(ss) > 1 else ''}, to "
                      f"{', '.join(sorted({s['to'] for s in ss}))})"
                      + (f"; shared ID systems: {', '.join(sources)}" if sources else "")
                      + ". Matching lets ad companies join up what each knows about this browser.",
            "law": "PECR reg. 6; ICO: consent is needed for any cross-site tracking, and advertising was never exempt",
        })
    return out


# ---------- B. linkage pass across sites ----------
def _logger(log, top, phase):
    def on_done(req):
        try:
            cookie = req.all_headers().get("cookie", "")
        except Exception:
            cookie = ""
        log.append({"top": top, "phase": phase["phase"], "url": req.url, "domain": base_domain(req.url),
                    "cookie": cookie, "_post": _body(req)})
    return on_done


def _body(req):
    """POST body as text. req.post_data crashes on binary (gzip) bodies, so decode leniently."""
    try:
        return (req.post_data_buffer or b"").decode("utf-8", "ignore")[:20000]
    except Exception:
        return ""


def linkage_pass(urls, reject, cost=None, progress=None, engine="chromium", firefox_prefs=None):
    """Visit urls in ONE browser context (rejecting each banner), then each in a fresh context for
    the ID check. Returns the linkage result dict (see .claude/docs/audit-format.md).
    engine: "chromium" (default, what Clype uses) or "firefox" (for comparison; Firefox's Total Cookie
    Protection gives each site its own cookie jar, so real cross-site links should disappear there)."""
    from playwright.sync_api import sync_playwright
    say = progress or (lambda text: None)
    started, t0 = datetime.now(timezone.utc), time.monotonic()
    log, visits = [], []
    with sync_playwright() as p:
        launch = {"firefox_user_prefs": firefox_prefs} if engine == "firefox" and firefox_prefs else {}
        browser = getattr(p, engine).launch(headless=True, **launch)
        try:
            shared = browser.new_context()
            for url in urls:
                site = base_domain(url)
                say(f"Visiting {site} in the shared browser")
                phase = {"phase": "before_consent"}
                page = shared.new_page()
                page.set_default_timeout(15000)
                page.on("requestfinished", _logger(log, site, phase))
                visit = {"site": site, "url": url, "loaded": False, "rejected": False}
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(4000)
                    visit["loaded"] = True
                    consent = reject(page, cost=cost)
                    visit["rejected"] = bool(consent.get("rejected"))
                    if visit["rejected"]:
                        phase["phase"] = "after_reject"
                        page.wait_for_timeout(1000)
                        page.reload(wait_until="domcontentloaded")   # a second page view after reject
                        page.wait_for_timeout(4000)
                except Exception as e:
                    visit["error"] = str(e).splitlines()[0][:150]
                page.close()
                visits.append(visit)
            cookies = shared.cookies()
            shared.close()
            fresh = []
            for v in visits:
                if not v["loaded"]:
                    continue
                say(f"Checking which values are IDs on {v['site']}")
                ctx = browser.new_context()
                try:
                    pg = ctx.new_page()
                    pg.goto(v["url"], wait_until="domcontentloaded", timeout=30000)
                    pg.wait_for_timeout(4000)
                    fresh += ctx.cookies()
                except Exception:
                    pass
                ctx.close()
        finally:
            browser.close()
    links = _links(log, cookies, fresh, [v["site"] for v in visits])
    return {"started_at": started.isoformat(), "duration_s": round(time.monotonic() - t0, 1),
            "engine": engine, "sites": visits, "requests": len(log), "links": links,
            "cost": cost.as_dict() if cost else None}


def _preview(value):
    """Start of the ID part of a value ('UserID=6a152cdc-…' -> '6a152cdc…'): enough to match, not the whole ID."""
    piece = max(tokens(value) or {value}, key=len)
    return piece[:8] + "…" if len(piece) > 10 else piece


def _links(log, cookies, fresh_cookies, sites):
    """The same per-browser ID reaching the same company from 2+ different sites."""
    fresh = {(c["domain"], c["name"]): c["value"] for c in fresh_cookies}
    seen = {}   # (company, how, value) -> {site: {"phases", "example"}}

    def note(company, how, value, r):
        s = seen.setdefault((company, how, value), {}).setdefault(r["top"], {"phases": set(), "example": r["url"][:160]})
        s["phases"].add(r["phase"])

    # 1. A cross-site cookie (third-party, SameSite=None, Secure, unpartitioned) sent with the same value.
    cross = {(_cookie_owner(c), c["name"]): c for c in cookies if c.get("sameSite") == "None"
             and c.get("secure") and "partitionKey" not in c and _cookie_owner(c) not in sites
             and not CONSENT_COOKIES.search(c["name"])}
    for r in log:
        if not r["cookie"] or r["domain"] == r["top"]:
            continue
        for part in r["cookie"].split(";"):
            name, _, value = part.strip().partition("=")
            c = cross.get((r["domain"], name))
            if not c or value != c["value"]:
                continue
            other = fresh.get((c["domain"], name))
            if other is not None and not id_pieces(value, other):
                continue                                     # same for every browser: not an ID
            if not tokens(value):
                continue                                     # too short / only a timestamp
            note(trackers.owner(r["domain"]), f"cookie {name}", value, r)

    # 2. A confirmed ID (from any cookie) appearing in requests to the same company from 2+ sites.
    ids = {t: i for t, i in find_ids(cookies, fresh_cookies).items() if i["confidence"] == "confirmed"}
    for site in sites:
        for leak in find_leaks([r for r in log if r["top"] == site], ids, site):
            note(trackers.owner(leak["to"]), f"ID from {leak['cookie']}", leak["_id"],
                 {"top": site, "phase": leak["phase"], "url": leak["example"]})

    links = []
    for (company, how, value), tops in seen.items():
        if len(tops) < 2:
            continue
        tr_company = trackers.TRACKER_COMPANIES.get(company, (company, None))
        links.append({
            "company": tr_company[0], "category": tr_company[1], "via": how,
            "id_preview": _preview(value),
            "sites": {s: {"phases": sorted(v["phases"]), "example": v["example"]} for s, v in sorted(tops.items())},
            "after_reject_on": sorted(s for s, v in tops.items() if "after_reject" in v["phases"]),
        })
    return sorted(links, key=lambda l: (-len(l["after_reject_on"]), -len(l["sites"])))
