# Clype: tiny web server that hands audit JSON files to the web page.
# Run: uvicorn api.main:app --reload   then open http://127.0.0.1:8000
#   "api.main" = the file api/main.py, ":app" = the variable called app below.
#   --reload   = restart automatically whenever you save a .py file.

from urllib.parse import urlsplit  # built-in: page address -> its homepage
import time       # built-in: how long ago a failed audit was
from contextlib import asynccontextmanager  # built-in: startup/shutdown hook
import threading  # built-in: runs the cross-site check in the background
import json   # built-in: turns JSON text into Python dicts/lists and back
import re     # built-in: regular expressions, used to check the audit id is safe
from datetime import datetime, timezone  # built-in: "today" for the usage panel
from pathlib import Path  # built-in: nicer way to work with file paths than plain strings

from fastapi import FastAPI, HTTPException      # FastAPI = the web framework; HTTPException = send an error back (e.g. 404)
from fastapi.staticfiles import StaticFiles     # serves plain files (our HTML/CSS) from a folder
from pydantic import BaseModel                  # validates the JSON body of incoming requests

from agent.letter import draft_letter           # drafts the complaint letter (LLM job 3)
from api import jobs                            # background audit queue (runs the pipeline in the background)
from agent.capture import base_domain           # "https://www.bbc.co.uk/news" -> "bbc.co.uk"
from agent import llm                           # Cost tracker for the letter call
from agent import mailer                        # sends letters (SEND_MODE decides where)
from agent.eu_law import add_eu_law             # EU GDPR / ePrivacy equivalents for each finding
from agent.trackers import cookie_value_kind    # empty / placeholder / id / value
from agent.compare import SEVERITY_ORDER         # worst finding first

# __file__ is this file's path (api/main.py). .resolve() makes it absolute,
# .parent is the api/ folder, .parent again is the project root (HTB/).
# Doing it this way means it works no matter which folder you run uvicorn from.
ROOT = Path(__file__).resolve().parent.parent
AUDITS = ROOT / "audits"   # the "/" operator joins paths: HTB/audits
@asynccontextmanager
async def lifespan(app):
    yield                  # the server runs here
    jobs.stop()            # shutting down / --reload: audit workers stop taking new jobs


app = FastAPI(title="Clype", lifespan=lifespan)  # create the web app; uvicorn looks for this variable


def tracker_counts(audit):
    """Count unique tracker DOMAINS (not requests) for one audit.

    seen    = tracker domains seen at any point
    stopped = fired before consent, went quiet after Reject all
    after   = still sending after Reject all (the bad ones)
    """
    before, after = set(), set()  # sets ignore duplicates, so each domain counts once
    for r in audit.get("requests", []):
        # "or {}" copes with a request that has no tracker info at all
        if not (r.get("tracker") or {}).get("is_tracker"):
            continue  # not a tracker -> ignore
        if r.get("phase") == "before_consent":
            before.add(r.get("domain"))
        elif r.get("phase") == "after_reject":
            after.add(r.get("domain"))
    rejected = (audit.get("consent") or {}).get("rejected")  # did the Reject click work?
    return {
        "seen": len(before | after),                        # | = union: in either set
        "stopped": len(before - after) if rejected else 0,  # - = in before but not in after
        "after": len(after),
    }


class AuditRequest(BaseModel):
    url: str  # pydantic checks the request body actually has a "url" string


class BatchRequest(BaseModel):
    urls: list[str]  # the dashboard reads the uploaded file and sends the list
    skip_audited: bool = False   # tick box: skip sites that already have a successful audit


# POST /api/audit {"url": "bbc.co.uk"} -> queues one audit and returns the job straight away.
# The audit itself runs in the background (api/jobs.py), one at a time. The dashboard
# polls GET /api/jobs to show progress, then opens the finished audit.
@app.post("/api/audit")
def post_audit(req: AuditRequest):
    try:
        url = jobs.clean_url(req.url)
    except ValueError as e:
        raise HTTPException(400, f"{req.url}: {e}")  # 400 = "your request was wrong"
    return jobs.submit(url)


# POST /api/audit/batch {"urls": [...]} -> queues up to jobs.MAX_BATCH audits from an uploaded file.
# Bad or duplicate URLs are skipped and reported back, the rest are queued.
@app.post("/api/audit/batch")
def post_batch(req: BatchRequest):
    queued, rejected, seen = [], [], set()
    # Sites already waiting/running: never queue them twice (whatever the tick box says).
    in_queue = {base_domain(j["url"]) for j in jobs.list_jobs() if j["status"] in ("queued", "running")}
    # Tick box: sites with a SUCCESSFUL audit (blocked/failed ones are retried).
    audited = {s["site"] for s in _latest_by_site().values()} if req.skip_audited else set()
    for raw in req.urls:
        try:
            url = jobs.clean_url(raw)
        except ValueError as e:
            rejected.append({"url": raw, "reason": str(e)})
            continue
        site = base_domain(url)
        if site in seen:                      # by SITE: "bbc.co.uk" and "https://www.bbc.co.uk/" are one
            rejected.append({"url": raw, "reason": "duplicate"})
            continue
        if site in in_queue:
            rejected.append({"url": raw, "reason": "already in the queue"})
            continue
        if site in audited:
            rejected.append({"url": raw, "reason": "already audited"})
            continue
        if len(queued) >= jobs.MAX_BATCH:
            rejected.append({"url": raw, "reason": f"over the {jobs.MAX_BATCH}-URL limit per file"})
            continue
        seen.add(site)
        queued.append(jobs.submit(url))
    return {"queued": queued, "rejected": rejected}


# GET /api/jobs -> every recent job (queued / running / done / failed) with its current step.
@app.get("/api/jobs")
def get_jobs():
    return jobs.list_jobs()


# POST /api/jobs/cancel -> cancels every audit still waiting in the queue (running ones finish).
@app.post("/api/jobs/cancel")
def cancel_jobs():
    return {"cancelled": jobs.cancel_queued()}


# POST /api/jobs/<id>/cancel -> the ✕ on one job: stop it (running or waiting) and drop it from the list.
@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    url = jobs.cancel(job_id)
    if url is None:
        raise HTTPException(404, "No such audit in the queue (it may have just finished)")
    return {"cancelled": url}


# @app.get(...) is a "decorator": it tells FastAPI "when a browser asks for
# GET /api/audits, run the function below and send back what it returns".
# Reading every audit file on every refresh gets slow with hundreds of audits (each can be
# ~1 MB). So we keep a small summary per file and only re-read a file when it changes.
_summary_cache = {}   # path -> (modified time, summary dict)


def audit_summary(f):
    """Small summary of one audit file (cached until the file changes), or None if unreadable."""
    mtime = f.stat().st_mtime
    hit = _summary_cache.get(f)
    if hit and hit[0] == mtime:
        return hit[1]
    try:
        a = json.loads(f.read_text())  # read the file as text, then parse the JSON into a dict
    except json.JSONDecodeError:
        return None  # file is broken or half-written (agent still saving it) -> skip it, don't crash
    rejected = (a.get("consent") or {}).get("rejected")
    # Tracker companies seen on this site: any phase / still sending after a successful reject.
    seen, after, categories = set(), set(), {}
    for r in a.get("requests", []):
        t = r.get("tracker") or {}
        if t.get("is_tracker") and t.get("company"):
            seen.add(t["company"])
            categories.setdefault(t["company"], t.get("category"))
            if rejected and r.get("phase") == "after_reject":
                after.add(t["company"])
    for phase in ("before_consent", "after_reject"):
        for c in (a.get("cookies") or {}).get(phase, []):
            if c.get("tracker_company"):
                seen.add(c["tracker_company"])
    summary = {
        "id": f.stem,                                   # f.stem = file name without ".json"
        "url": a.get("url"),
        "site": base_domain(a.get("url") or ""),
        "started_at": a.get("started_at"),
        "loaded": a.get("loaded", True),                # False = site blocked us / didn't load
        "summary": a.get("summary", {}),                # second argument = default if missing
        "rejected": rejected,                           # for the card's status pill
        "tracker_counts": tracker_counts(a),
        "_companies": {"seen": sorted(seen), "after": sorted(after), "categories": categories},
        "_cost": a.get("cost") or {},                   # AI usage for /api/usage
        # For the per-site timeline: worst finding + how many findings.
        "worst": min((f.get("severity") for f in a.get("findings", [])),
                     key=lambda s: SEVERITY_ORDER.get(s, 9), default=None),
        "findings_count": len(a.get("findings", [])),
        "top_findings": [{"severity": f.get("severity"), "title": f.get("title")}   # findings are worst first
                         for f in a.get("findings", [])[:3]],
    }
    _summary_cache[f] = (mtime, summary)
    return summary


@app.get("/api/audits")
def list_audits():
    # sorted(..., reverse=True) puts them newest first (file names start with a timestamp).
    out = []
    for f in sorted(AUDITS.glob("*.json"), reverse=True):
        s = audit_summary(f)
        if s:
            out.append({k: v for k, v in s.items() if not k.startswith("_")})  # don't send internals
    return out  # FastAPI automatically converts the Python list to JSON for the browser


# GET /api/usage -> AI (OpenAI) usage added up over EVERY saved audit (re-runs too: they all cost).
# US$ is an estimate from LLM_PRICES in .env; audits from before the per-model split can't be priced.
@app.get("/api/usage")
def usage():
    today = datetime.now(timezone.utc).date().isoformat()
    keys = ("llm_calls", "input_tokens", "output_tokens")
    total, day = dict.fromkeys(keys, 0), dict.fromkeys(keys, 0)
    by_model, priced_usd, unpriced, audits, with_ai = {}, 0.0, 0, 0, 0
    day_usd, day_unpriced = 0.0, 0
    for f in AUDITS.glob("*.json"):
        s = audit_summary(f)
        if not s:
            continue
        audits += 1
        c = s["_cost"]
        is_today = (s.get("started_at") or "").startswith(today)
        if c.get("llm_calls"):
            with_ai += 1
        for k in keys:
            total[k] += c.get(k) or 0
            if is_today:
                day[k] += c.get(k) or 0
        for model, u in (c.get("by_model") or {}).items():
            m = by_model.setdefault(model, dict.fromkeys(keys, 0))
            for k in keys:
                m[k] += u.get(k, 0)
        # Price this audit. No per-model split (older audits) or a model without a price -> unpriced.
        usd = llm.estimate_usd(c.get("by_model")) if c.get("by_model") else None
        if c.get("llm_calls") and usd is None:
            unpriced += 1
            day_unpriced += is_today
        else:
            priced_usd += usd or 0
            day_usd += (usd or 0) if is_today else 0
    for model, m in by_model.items():
        m["usd"] = llm.estimate_usd({model: m})
    return {
        "audits": audits,
        "audits_with_ai": with_ai,
        "total": total,
        "today": day,
        "avg_per_audit": {k: round(total[k] / with_ai) if with_ai else 0 for k in keys},
        "by_model": by_model,
        "usd": round(priced_usd, 4) if llm.PRICES else None,     # None = no prices set
        "usd_today": round(day_usd, 4) if llm.PRICES else None,
        "unpriced_audits": unpriced,                              # left out of the US$ estimate
        "unpriced_today": day_unpriced,
        "budget": llm.BUDGET,
        "call_cap_per_audit": llm.MAX_CALLS_PER_AUDIT,
    }


# GET /api/cross-site -> which tracker companies follow you across MANY sites.
# Uses the newest successfully-loaded audit per site, so re-running a site doesn't double count.
@app.get("/api/cross-site")
def cross_site():
    latest = {}
    for f in sorted(AUDITS.glob("*.json")):            # oldest first, so newer audits overwrite
        s = audit_summary(f)
        if s and s["loaded"] and s["site"]:
            latest[s["site"]] = s
    companies = {}
    for site, s in latest.items():
        c = s["_companies"]
        for name in c["seen"]:
            e = companies.setdefault(name, {"company": name, "category": c["categories"].get(name),
                                            "sites": [], "sites_after_reject": []})
            e["category"] = e["category"] or c["categories"].get(name)
            e["sites"].append(site)
        for name in c["after"]:
            companies[name]["sites_after_reject"].append(site)
    total = len(latest)
    rows = sorted(companies.values(), key=lambda e: (-len(e["sites"]), e["company"]))
    for e in rows:
        e["sites"].sort()
        e["sites_after_reject"].sort()
        e["share"] = round(100 * len(e["sites"]) / total) if total else 0
    rejected_sites = sum(1 for s in latest.values() if s["rejected"])
    return {"sites_audited": total, "sites_rejected": rejected_sites, "companies": rows}


# ---- Firefox extension (extension/) ----
# The extension tells us which site you're on; we audit it in the background (same queue as the
# dashboard) unless it was audited recently, and it polls for the result to show a badge / alert.
RECENT_DAYS = 7     # reuse an audit this recent instead of re-auditing (saves AI cost)


class VisitRequest(BaseModel):
    url: str
    force: bool = False      # True after "Reset this site's cookies": re-audit even if audited recently


def _site_status(url, start=False, force=False):
    """{site, status, audit, job}. status: done / queued / running / failed / none.
    start=True queues an audit if there's no recent report and none in the queue.
    force=True (with start): ignore the recent report / recent failure and audit again now."""
    try:
        url = jobs.clean_url(url)            # also refuses localhost / private addresses
    except ValueError as e:
        raise HTTPException(400, str(e))
    site = base_domain(url)
    latest = None
    for f in sorted(AUDITS.glob("*.json"), reverse=True):     # newest first
        s = audit_summary(f)
        if s and s["site"] == site:
            latest = s
            break
    public = (lambda s: {k: v for k, v in s.items() if not k.startswith("_")}) if latest else None
    job = next((j for j in jobs.list_jobs() if base_domain(j["url"]) == site), None)   # newest job for site
    recent = False
    if latest and latest.get("started_at"):
        age = datetime.now(timezone.utc) - datetime.fromisoformat(latest["started_at"])
        recent = age.days < RECENT_DAYS
    if job and job["status"] in ("queued", "running"):
        # A dashboard batch has this site waiting but there's a recent report: show that report
        # (the batch re-audit still happens later). Otherwise show the job, and if it's waiting in the
        # normal lane while you're on the site, move it into the fast lane.
        if recent and not force and job.get("source") != "extension":
            return {"site": site, "status": "done", "audit": public(latest)}
        if start and job["status"] == "queued":
            jobs.promote(job["id"])
        return {"site": site, "status": job["status"], "step": job["step"], "audit": public(latest) if latest else None}
    if recent and not force:
        return {"site": site, "status": "done", "audit": public(latest)}
    if job and job["status"] == "failed" and not force and time.time() - (job["finished"] or 0) < 3600:
        return {"site": site, "status": "failed", "error": job["error"], "audit": public(latest) if latest else None}
    if start and jobs.recently_cancelled(site) and not force:
        # You cancelled this site's audit a moment ago: don't let the extension's polling restart it.
        return {"site": site, "status": "none", "audit": public(latest) if latest else None}
    if start:
        # Audit the site's homepage, not the page you're on: a deep link / login page / 404 would make
        # the audit look "blocked", and the audit is per site anyway.
        parts = urlsplit(url)
        job = jobs.submit(f"{parts.scheme}://{parts.netloc}/", allow_send=False, source="extension")  # never emails
        return {"site": site, "status": "queued", "step": job["step"], "audit": public(latest) if latest else None}
    return {"site": site, "status": "none", "audit": public(latest) if latest else None}


@app.get("/api/extension/site")
def extension_site(url: str):
    return _site_status(url)


@app.post("/api/extension/visit")
def extension_visit(req: VisitRequest):
    return _site_status(req.url, start=True, force=req.force)


# ---- Phase 2: what YOUR browser did (extension rejects in your tab and records the traffic) ----
# Same plain-code analysis as an audit (trackers, compare, ID leaks), no AI. Saved in sessions/,
# separate from audits/, so the dashboard's audit numbers only ever come from the agent.
SESSIONS = ROOT / "sessions"
MAX_SESSION_REQUESTS = 5000


class SessionCapture(BaseModel):
    url: str
    started_at: str | None = None
    banner_found: bool = False
    rejected: bool = False
    reject_label: str | None = None
    browser: str | None = None
    requests: list[dict] = []          # {url, method, type, phase, _post?}
    cookies: dict = {}                 # {"before_consent": [...], "after_reject": [...]}


def _latest_audit_for(site):
    for f in sorted(AUDITS.glob("*.json"), reverse=True):
        s = audit_summary(f)
        if s and s["site"] == site:
            return json.loads(f.read_text())
    return None


@app.post("/api/extension/session")
def extension_session(cap: SessionCapture):
    from agent import trackers as tr, crosssite
    from agent.compare import compare
    from agent.run_audit import tag_cookie_trackers
    try:
        url = jobs.clean_url(cap.url)
    except ValueError as e:
        raise HTTPException(400, str(e))
    site = base_domain(url)
    requests = []
    for r in cap.requests[:MAX_SESSION_REQUESTS]:
        u = str(r.get("url") or "")
        if not u.startswith(("http://", "https://")):
            continue
        d = base_domain(u)
        requests.append({"url": u[:2000], "domain": d, "third_party": d != site,
                         "method": str(r.get("method") or "GET")[:10], "type": str(r.get("type") or "")[:30],
                         "phase": "after_reject" if r.get("phase") == "after_reject" else "before_consent",
                         "_post": str(r.get("_post") or "")[:20000],
                         "tracker": tr.match(d, site, url=u)})
    keep = ("name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite", "partitioned")
    cookies = {ph: [{k: c.get(k) for k in keep} for c in (cap.cookies.get(ph) or [])[:2000] if c.get("name")]
               for ph in ("before_consent", "after_reject")}
    if not cap.rejected:
        cookies["after_reject"] = []               # no reject = no "after reject"
    for ph in cookies.values():
        tag_cookie_trackers(ph, site)
    consent = {"banner_found": cap.banner_found, "rejected": cap.rejected, "method": "extension",
               "clicks": [cap.reject_label] if cap.reject_label else []}
    audit = _latest_audit_for(site)               # policy + a second, independent browser's cookies
    policy = (audit or {}).get("policy") or {"found": False, "companies_named": []}
    findings, summary = compare(requests, cookies, policy, consent)
    # ID leaks: the headless audit is the "other browser" for the per-browser-ID check.
    other = [c for ph in ((audit or {}).get("cookies") or {}).values() for c in ph]
    all_cookies = list({(c["domain"], c["name"]): c for c in cookies["before_consent"] + cookies["after_reject"]}.values())
    leaks = crosssite.find_leaks(requests, crosssite.find_ids(all_cookies, other), site) if other else []
    syncs = crosssite.find_syncs(requests)
    findings = sorted(findings + crosssite.findings(leaks, syncs), key=lambda f: SEVERITY_ORDER[f["severity"]])
    for f in findings:
        f["source"] = "your_browser"
    for r in requests:
        r.pop("_post", None)
    session = {"site": site, "url": url, "source": "extension", "browser": (cap.browser or "")[:100],
               "started_at": cap.started_at or datetime.now(timezone.utc).isoformat(),
               "saved_at": datetime.now(timezone.utc).isoformat(), "consent": consent,
               "requests": requests, "cookies": cookies, "findings": findings, "summary": summary,
               "id_leaks": [{k: v for k, v in l.items() if k != "_id"} for l in leaks], "id_syncs": syncs,
               "compared_with_audit": (audit or {}).get("id")}
    session["tracker_counts"] = tracker_counts(session)
    SESSIONS.mkdir(exist_ok=True)
    name = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{site}"
    (SESSIONS / f"{name}.json").write_text(json.dumps(session, indent=2))
    return _session_brief(name, session)


def _session_brief(name, s):
    return {"id": name, "site": s["site"], "started_at": s["started_at"], "rejected": s["consent"]["rejected"],
            "banner_found": s["consent"]["banner_found"], "reject_label": (s["consent"]["clicks"] or [None])[0],
            "tracker_counts": s["tracker_counts"], "companies_after_reject": s["summary"].get("companies_after_reject", []),
            "findings": [{"severity": f["severity"], "title": f["title"]} for f in s["findings"][:5]],
            "requests": len(s["requests"])}


@app.get("/api/sessions/latest")
def latest_session(site: str):
    """Newest capture from your own browser for a site (for the audit page and the popup)."""
    if not re.fullmatch(r"[\w.\-]+", site):
        raise HTTPException(400, "bad site")
    files = sorted(SESSIONS.glob(f"*_{site}.json")) if SESSIONS.exists() else []
    if not files:
        return None
    return _session_brief(files[-1].stem, json.loads(files[-1].read_text()))


# ---- Proving cross-site links (agent/crosssite.py linkage_pass) ----
# The panel above only shows PRESENCE (each audit uses a fresh browser, so a tracker sees a new ID on
# every site). The linkage pass visits a few sites in ONE browser and checks whether a tracker gets
# the same ID from each. One run at a time, in a background thread; results saved in linkage/.
LINKAGE = ROOT / "linkage"
_proof = {"status": "idle", "progress": None, "sites": [], "error": None}
_proof_lock = threading.Lock()


def _latest_by_site():
    latest = {}
    for f in sorted(AUDITS.glob("*.json")):            # oldest first, so newer audits overwrite
        s = audit_summary(f)
        if s and s["loaded"] and s["site"]:
            latest[s["site"]] = s
    return latest


def pick_proof_sites(limit=4):
    """Audited sites most likely to share a tracker: score = shared tracker companies (x2 if they
    kept going after reject on that site). Only companies seen on 2+ sites count."""
    data = cross_site()
    score = {}
    for c in data["companies"]:
        if len(c["sites"]) < 2:
            continue
        for site in c["sites"]:
            score[site] = score.get(site, 0) + (2 if site in c["sites_after_reject"] else 1)
    return sorted(score, key=lambda x: (-score[x], x))[:limit]


class ProofRequest(BaseModel):
    sites: list[str] | None = None     # audited site names; omitted = pick automatically


def _run_proof(urls):
    from agent.consent import reject_cookies
    from agent import crosssite
    try:
        result = crosssite.linkage_pass(urls, reject_cookies, cost=llm.Cost(),
                                        progress=lambda text: _proof.update(progress=text))
        LINKAGE.mkdir(exist_ok=True)
        name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + ".json"
        (LINKAGE / name).write_text(json.dumps(result, indent=2))
        _proof.update(status="idle", progress=None, error=None)
    except Exception as e:
        _proof.update(status="idle", progress=None, error=f"{type(e).__name__}: {e}"[:200])


@app.post("/api/cross-site/prove")
def prove_links(req: ProofRequest):
    latest = _latest_by_site()
    sites = req.sites or pick_proof_sites()
    if not 2 <= len(sites) <= 5 or any(s not in latest for s in sites):
        raise HTTPException(400, "Pick 2-5 sites that have been audited")   # never arbitrary URLs
    with _proof_lock:
        if _proof["status"] == "running":
            raise HTTPException(409, "A cross-site check is already running")
        _proof.update(status="running", progress="Starting", sites=sites, error=None)
    threading.Thread(target=_run_proof, args=([latest[s]["url"] for s in sites],), daemon=True).start()
    return {"status": "running", "sites": sites}


@app.get("/api/cross-site/proof")
def proof_status():
    """Current run status + the newest saved result (or None)."""
    files = sorted(LINKAGE.glob("*.json")) if LINKAGE.exists() else []
    latest = json.loads(files[-1].read_text()) if files else None
    return {**_proof, "suggested_sites": pick_proof_sites(), "result": latest}


# {audit_id} in the path is a variable: GET /api/audits/abc puts "abc" into audit_id.
# GET /api/audits/<id>/history -> every audit of the SAME site, newest first (for the timeline).
@app.get("/api/audits/{audit_id}/history")
def audit_history(audit_id: str):
    f = AUDITS / f"{audit_id}.json"
    if not re.fullmatch(r"[\w.\-]+", audit_id) or not f.exists():
        raise HTTPException(404, "not found")
    me = audit_summary(f)
    if not me:
        raise HTTPException(404, "not found")
    out = []
    for g in sorted(AUDITS.glob("*.json"), reverse=True):   # file names start with a timestamp
        s = audit_summary(g)
        if s and s["site"] == me["site"]:
            out.append({k: s[k] for k in ("id", "started_at", "loaded", "rejected", "tracker_counts",
                                          "worst", "findings_count")})
    return out


@app.get("/api/audits/{audit_id}")
def get_audit(audit_id: str):
    f = AUDITS / f"{audit_id}.json"  # build the path, e.g. audits/abc.json
    # Safety check. re.fullmatch means the WHOLE id must match the pattern:
    #   [\w.\-]+  = one or more letters, digits, underscores, dots or dashes.
    # No "/" is allowed, so nobody can ask for "../.env" and read files outside audits/.
    # Also return 404 if the file simply doesn't exist.
    if not re.fullmatch(r"[\w.\-]+", audit_id) or not f.exists():
        raise HTTPException(404, "not found")  # stops here and sends a 404 error to the browser
    a = json.loads(f.read_text())
    a["tracker_counts"] = tracker_counts(a)  # add the counts (in the response only, the file isn't changed)
    add_eu_law([f for f in a.get("findings", []) if "law_eu" not in f])  # older audits: fill in EU law on the fly
    for phase in (a.get("cookies") or {}).values():                         # older audits: label cookie values too
        for c in phase:
            c.setdefault("value_kind", cookie_value_kind(c.get("value")))
    return a  # send the full audit back as JSON


# POST /api/audits/{id}/letter -> the "Create draft letter" button.
# Drafts a letter for an audit that didn't get one automatically, saves it into the
# audit file, and returns it. DRAFT ONLY: this route never sends email.
@app.post("/api/audits/{audit_id}/letter")
def create_letter(audit_id: str):
    f = AUDITS / f"{audit_id}.json"
    if not re.fullmatch(r"[\w.\-]+", audit_id) or not f.exists():
        raise HTTPException(404, "not found")
    a = json.loads(f.read_text())
    cost = llm.Cost()
    letter = draft_letter(a, cost=cost)
    if letter.get("error") and not letter.get("body"):
        raise HTTPException(422, letter["error"])  # e.g. nothing to complain about
    letter["auto"] = {"tier": None, "reason": "Requested from the dashboard."}
    a["letter"] = letter
    # Add this call's tokens to the audit's running cost, so the totals stay honest.
    c, new = a.setdefault("cost", {}), cost.as_dict()
    for k in ("llm_calls", "input_tokens", "output_tokens"):
        c[k] = (c.get(k) or 0) + new[k]
    for model, u in new["by_model"].items():
        m = c.setdefault("by_model", {}).setdefault(model, {"llm_calls": 0, "input_tokens": 0, "output_tokens": 0})
        for k in m:
            m[k] += u[k]
    if new["model"] and new["model"] not in (c.get("model") or ""):
        c["model"] = "+".join(filter(None, [c.get("model"), new["model"]]))
    f.write_text(json.dumps(a, indent=2))
    return letter


# One plain email address, nothing else (no lists, no "Name <addr>", no newlines).
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


class SendRequest(BaseModel):
    to: str
    subject: str
    body: str


# GET /api/email-status -> {"mode", "configured", "from"} so the Send button can say
# where the email will really go (e.g. test mode = your own inbox). No secrets.
@app.get("/api/email-status")
def email_status():
    return mailer.email_status()


# POST /api/audits/{id}/letter/send -> the "Send email" button. Sends what's in the
# To / Subject / Body boxes (so edits and a hand-typed To address are used), following
# SEND_MODE and the same live limits as automatic sends (1 per site, 5 per day).
# Saves the edited letter + delivery result into the audit file.
@app.post("/api/audits/{audit_id}/letter/send")
def send_letter_now(audit_id: str, req: SendRequest):
    f = AUDITS / f"{audit_id}.json"
    if not re.fullmatch(r"[\w.\-]+", audit_id) or not f.exists():
        raise HTTPException(404, "not found")
    to, subject, body = req.to.strip(), req.subject.strip(), req.body.strip()
    if not EMAIL_RE.fullmatch(to):
        raise HTTPException(400, "Enter one valid email address in To.")
    if not subject or not body:
        raise HTTPException(400, "Subject and body can't be empty.")
    a = json.loads(f.read_text())
    letter = a.get("letter") or {"kind": "complaint"}
    letter.update(to=to, subject=subject[:200], body=body)
    letter.pop("note", None)                      # "no DPO email found" no longer applies
    delivery = mailer.send_letter(letter, a, trigger="manual")
    letter["delivery"] = delivery
    a["letter"] = letter
    f.write_text(json.dumps(a, indent=2))
    if not (delivery["sent"] or delivery.get("saved_to")):
        raise HTTPException(409, delivery.get("reason") or "Not sent.")   # e.g. limit reached / SEND_MODE off
    return letter


# Serve everything in web/ as normal files: /index.html, /audit.html, /style.css.
# html=True means visiting "/" shows index.html automatically.
# This MUST come after the routes above: "/" matches everything, so if it were
# first it would swallow the /api/... requests too.
app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
