"""
Audit queue for the dashboard: audits run in background threads, AUDIT_WORKERS at a
time (default 4, max 8, set in .env), so the web server stays responsive. Each
worker runs one audit with its own Chromium (~0.5-1 GB RAM each).

  submit(url)  -> adds a job, returns it straight away (status "queued")
  list_jobs()  -> recent jobs, newest first, with live status + current step

Jobs live in memory only: restarting the server (or uvicorn --reload after a code
change) forgets the queue. Finished audits are already saved in audits/, so
nothing is lost except jobs that hadn't finished.
"""
import ipaddress
import os
import queue
import threading
import time
import uuid
from urllib.parse import urlparse

from agent.run_audit import run as run_audit
from agent.letter import audit_tier

MAX_BATCH = 300       # most URLs accepted from one file (~1 h at 4 workers)
MAX_KEEP = 1000       # jobs remembered for the dashboard (must be > MAX_BATCH)
# How many audits run at once. More = faster batches, but more RAM/CPU and more
# page-load timeouts if the laptop gets busy. Clamped to 1..8.
WORKERS = max(1, min(8, int(os.getenv("AUDIT_WORKERS", "4"))))

_jobs = {}            # job id -> job dict
_queue = queue.Queue()
_lock = threading.Lock()


def clean_url(raw):
    """Turn user input into a safe http(s) URL, or raise ValueError saying why not.
    Blocks local / private addresses: the server must never be used to poke at our own network."""
    url = str(raw).strip().strip("\"'")
    if not url:
        raise ValueError("empty")
    if "://" not in url:
        url = "https://" + url                       # "bbc.co.uk" -> "https://bbc.co.uk"
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https"):
        raise ValueError("only http(s) websites can be audited")
    if not host or "." not in host:
        raise ValueError("not a website address")
    if host == "localhost" or host.endswith((".local", ".localhost", ".internal")):
        raise ValueError("local addresses are not allowed")
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError("private / local IP addresses are not allowed")
    except ValueError as e:
        if "not allowed" in str(e):
            raise
    if len(url) > 500:
        raise ValueError("URL too long")
    return url


def submit(url):
    """Queue one audit (url must already be clean). Returns the job dict."""
    job = {"id": uuid.uuid4().hex[:8], "url": url, "status": "queued", "step": "Waiting in queue",
           "created": time.time(), "started": None, "finished": None,
           "audit_id": None, "tier": None, "emailed": None, "errors": 0, "error": None}
    with _lock:
        _jobs[job["id"]] = job
        if len(_jobs) > MAX_KEEP:                    # forget the oldest finished jobs
            for old in sorted(_jobs.values(), key=lambda j: j["created"])[: len(_jobs) - MAX_KEEP]:
                if old["status"] in ("done", "failed", "cancelled"):
                    _jobs.pop(old["id"], None)
    _queue.put(job["id"])
    return job


def cancel_queued():
    """Cancel every job that hasn't started yet. Running audits are left to finish
    (stopping a browser mid-audit could leave a half-written audit file).
    Returns how many were cancelled."""
    n = 0
    with _lock:
        for job in _jobs.values():
            if job["status"] == "queued":
                job.update(status="cancelled", step="Cancelled", finished=time.time())
                n += 1
    return n


def list_jobs():
    with _lock:
        return sorted((dict(j) for j in _jobs.values()), key=lambda j: j["created"], reverse=True)


def _worker():
    """Runs forever in the background: take the next job, run the audit, record the result."""
    while True:
        job = _jobs.get(_queue.get())
        if job is None or job["status"] == "cancelled":   # cancelled while waiting: skip it
            continue
        job.update(status="running", started=time.time(), step="Starting")
        try:
            audit = run_audit(job["url"], progress=lambda text: job.update(step=text))
            delivery = (audit.get("letter") or {}).get("delivery") or {}
            job.update(status="done", step="Finished", audit_id=audit.get("id"),
                       tier=audit_tier(audit), emailed=delivery.get("sent"),
                       errors=len(audit.get("errors") or []))
            if not audit.get("loaded"):
                first = (audit.get("errors") or [{}])[0].get("error") or "The site could not be loaded."
                job.update(status="failed", error=first.split("\n")[0][:200])   # first line only, e.g. "Site refused the automated browser (HTTP 403...)"
        except Exception as e:                       # run_audit shouldn't raise, but never kill the worker
            job.update(status="failed", step="Failed", error=f"{type(e).__name__}: {e}"[:300])
        job["finished"] = time.time()


for n in range(WORKERS):  # each thread takes the next queued job when it's free
    threading.Thread(target=_worker, daemon=True, name=f"audit-worker-{n + 1}").start()


def worker_count():
    return WORKERS
