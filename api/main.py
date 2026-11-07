# Clype: tiny web server that hands audit JSON files to the web page.
# Run: uvicorn api.main:app --reload   then open http://127.0.0.1:8000
#   "api.main" = the file api/main.py, ":app" = the variable called app below.
#   --reload   = restart automatically whenever you save a .py file.

import json   # built-in: turns JSON text into Python dicts/lists and back
import re     # built-in: regular expressions, used to check the audit id is safe
from pathlib import Path  # built-in: nicer way to work with file paths than plain strings

from fastapi import FastAPI, HTTPException      # FastAPI = the web framework; HTTPException = send an error back (e.g. 404)
from fastapi.staticfiles import StaticFiles     # serves plain files (our HTML/CSS) from a folder
from pydantic import BaseModel                  # validates the JSON body of incoming requests

from agent.letter import draft_letter           # drafts the complaint letter (LLM job 3)
from api import jobs                            # background audit queue (runs the pipeline one at a time)
from agent import llm                           # Cost tracker for the letter call

# __file__ is this file's path (api/main.py). .resolve() makes it absolute,
# .parent is the api/ folder, .parent again is the project root (HTB/).
# Doing it this way means it works no matter which folder you run uvicorn from.
ROOT = Path(__file__).resolve().parent.parent
AUDITS = ROOT / "audits"   # the "/" operator joins paths: HTB/audits
app = FastAPI(title="Clype")  # create the web app; uvicorn looks for this variable


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
    for raw in req.urls:
        try:
            url = jobs.clean_url(raw)
        except ValueError as e:
            rejected.append({"url": raw, "reason": str(e)})
            continue
        if url in seen:
            rejected.append({"url": raw, "reason": "duplicate"})
            continue
        if len(queued) >= jobs.MAX_BATCH:
            rejected.append({"url": raw, "reason": f"over the {jobs.MAX_BATCH}-URL limit per file"})
            continue
        seen.add(url)
        queued.append(jobs.submit(url))
    return {"queued": queued, "rejected": rejected}


# GET /api/jobs -> every recent job (queued / running / done / failed) with its current step.
@app.get("/api/jobs")
def get_jobs():
    return jobs.list_jobs()


# @app.get(...) is a "decorator": it tells FastAPI "when a browser asks for
# GET /api/audits, run the function below and send back what it returns".
@app.get("/api/audits")
def list_audits():
    out = []  # we'll fill this with one small summary per audit file
    # AUDITS.glob("*.json") finds every .json file in audits/.
    # sorted(..., reverse=True) puts them newest first (file names start with a timestamp).
    for f in sorted(AUDITS.glob("*.json"), reverse=True):
        try:
            a = json.loads(f.read_text())  # read the file as text, then parse the JSON into a dict
        except json.JSONDecodeError:
            continue  # file is broken or half-written (agent still saving it) -> skip it, don't crash
        # Only send the bits the list page needs, not the whole (possibly huge) audit.
        # a.get("url") returns None instead of crashing if the key is missing.
        out.append({"id": f.stem,                       # f.stem = file name without ".json"
                    "url": a.get("url"),
                    "started_at": a.get("started_at"),
                    "summary": a.get("summary", {}),    # second argument = default if missing
                    "rejected": (a.get("consent") or {}).get("rejected"),  # for the card's status pill
                    "tracker_counts": tracker_counts(a)})
    return out  # FastAPI automatically converts the Python list to JSON for the browser


# {audit_id} in the path is a variable: GET /api/audits/abc puts "abc" into audit_id.
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
    if new["model"] and new["model"] not in (c.get("model") or ""):
        c["model"] = "+".join(filter(None, [c.get("model"), new["model"]]))
    f.write_text(json.dumps(a, indent=2))
    return letter


# Serve everything in web/ as normal files: /index.html, /audit.html, /style.css.
# html=True means visiting "/" shows index.html automatically.
# This MUST come after the routes above: "/" matches everything, so if it were
# first it would swallow the /api/... requests too.
app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
