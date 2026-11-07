# Tiny web server that hands audit JSON files to the web page.
# Run: uvicorn api.main:app --reload   then open http://127.0.0.1:8000
#   "api.main" = the file api/main.py, ":app" = the variable called app below.
#   --reload   = restart automatically whenever you save a .py file.

import json   # built-in: turns JSON text into Python dicts/lists and back
import re     # built-in: regular expressions, used to check the audit id is safe
from pathlib import Path  # built-in: nicer way to work with file paths than plain strings

from fastapi import FastAPI, HTTPException      # FastAPI = the web framework; HTTPException = send an error back (e.g. 404)
from fastapi.staticfiles import StaticFiles     # serves plain files (our HTML/CSS) from a folder

# __file__ is this file's path (api/main.py). .resolve() makes it absolute,
# .parent is the api/ folder, .parent again is the project root (HTB/).
# Doing it this way means it works no matter which folder you run uvicorn from.
ROOT = Path(__file__).resolve().parent.parent
AUDITS = ROOT / "audits"   # the "/" operator joins paths: HTB/audits
app = FastAPI()            # create the web app; uvicorn looks for this variable


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
                    "summary": a.get("summary", {})})   # second argument = default if missing
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
    return json.loads(f.read_text())  # send the full audit back as JSON


# Serve everything in web/ as normal files: /index.html, /audit.html, /style.css.
# html=True means visiting "/" shows index.html automatically.
# This MUST come after the routes above: "/" matches everything, so if it were
# first it would swallow the /api/... requests too.
app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
