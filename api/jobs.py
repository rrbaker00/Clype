"""
Audit queue for the dashboard: audits run in background threads, AUDIT_WORKERS at a
time (default 4, max 8, set in .env), so the web server stays responsive. Each
worker runs one audit with its own headless browser (~0.5-1 GB RAM each). Audits started
by the Firefox extension use a fast lane: they run before waiting dashboard/batch audits.

  submit(url)  -> adds a job, returns it straight away (status "queued")
  list_jobs()  -> recent jobs, newest first, with live status + current step

Jobs live in memory only: restarting the server (or uvicorn --reload after a code
change) forgets the queue. Finished audits are already saved in audits/, so
nothing is lost except jobs that hadn't finished.
"""
import ipaddress
import itertools
import os
import queue
import threading
import time
import uuid
from urllib.parse import urlparse

from agent.run_audit import run as run_audit, AuditCancelled, AUDITS_DIR
from agent.letter import audit_tier

MAX_BATCH = 300       # most URLs accepted from one file (~1 h at 4 workers)
MAX_KEEP = 1000       # jobs remembered for the dashboard (must be > MAX_BATCH)
# How many audits run at once. More = faster batches, but more RAM/CPU and more
# page-load timeouts if the laptop gets busy. Clamped to 1..8.
WORKERS = max(1, min(8, int(os.getenv("AUDIT_WORKERS", "4"))))

_jobs = {}            # job id -> job dict
# Priority queue with a FAST LANE: audits for the site you're browsing (the Firefox extension) jump
# ahead of waiting dashboard/batch audits. Items are (priority, order, job id): lower priority runs
# first, and "order" keeps first-come-first-served within the same priority. Running audits are
# never interrupted; the batch just continues once the fast lane is empty.
FAST, NORMAL = 0, 1
_queue = queue.PriorityQueue()
_order = itertools.count()
_lock = threading.Lock()
_stopping = threading.Event()   # set when the server shuts down / reloads: take no NEW jobs


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


def submit(url, allow_send=True, source="dashboard"):
    """Queue one audit (url must already be clean). Returns the job dict.
    allow_send=False: never email (extension audits). source: "dashboard" or "extension"
    (extension audits go in the fast lane)."""
    job = {"id": uuid.uuid4().hex[:8], "url": url, "status": "queued", "step": "Waiting in queue",
           "allow_send": allow_send, "source": source,
           "created": time.time(), "started": None, "finished": None,
           "audit_id": None, "tier": None, "emailed": None, "errors": 0, "error": None}
    with _lock:
        _jobs[job["id"]] = job
        if len(_jobs) > MAX_KEEP:                    # forget the oldest finished jobs
            for old in sorted(_jobs.values(), key=lambda j: j["created"])[: len(_jobs) - MAX_KEEP]:
                if old["status"] in ("done", "failed", "cancelled"):
                    _jobs.pop(old["id"], None)
    job["lane"] = "fast" if source == "extension" else "normal"
    _queue.put((FAST if source == "extension" else NORMAL, next(_order), job["id"]))
    return job


def promote(job_id):
    """Move a waiting job into the fast lane (you opened that site in the browser while it was
    waiting in a batch). Its old place in the queue is skipped when reached (status no longer "queued")."""
    with _lock:
        job = _jobs.get(job_id)
        if not job or job["status"] != "queued" or job.get("lane") == "fast":
            return False
        job["lane"] = "fast"
    _queue.put((FAST, next(_order), job_id))
    return True


CANCEL_HOLD_S = 15 * 60
_cancelled_sites = {}   # site -> when it was cancelled (the extension must not quietly re-queue it)


def cancel(job_id):
    """The ✕ on one job. Waiting: dropped, never runs. Running: flagged; it stops at its next step,
    closes its browser and saves nothing. Either way it disappears from the list straight away.
    Returns the removed job's url, or None if there was no such job."""
    from agent.capture import base_domain
    with _lock:
        job = _jobs.pop(job_id, None)            # gone from the list now (the worker keeps its own reference)
        if job is None:
            return None
        job["cancel"] = True
        if job["status"] == "queued":
            job.update(status="cancelled", step="Cancelled", finished=time.time())
        _cancelled_sites[base_domain(job["url"])] = time.time()
    if job["status"] == "running" and job.get("_kill"):
        job["_kill"]()                            # stop its browser now, even if it's stuck mid-step
    return job["url"]


def recently_cancelled(site):
    return time.time() - _cancelled_sites.get(site, 0) < CANCEL_HOLD_S


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
    with _lock:   # "_kill" etc. are internal (not JSON): leave them out
        return sorted(({k: v for k, v in j.items() if not k.startswith("_")} for j in _jobs.values()),
                      key=lambda j: j["created"], reverse=True)


def stop():
    """Server is shutting down (or uvicorn --reload restarting): workers finish the audit they're on
    but take no new ones. Without this the old process kept working through a whole batch while
    shutting down, so the restarted server couldn't come up (API down for up to an hour)."""
    _stopping.set()
    for _ in range(WORKERS):
        _queue.put((-1, -1, None))                # wake idle workers so they see the stop flag


def _worker():
    """Runs in the background: take the next job, run the audit, record the result."""
    while not _stopping.is_set():
        job = _jobs.get(_queue.get()[2])          # (priority, order, job id)
        if _stopping.is_set():
            return
        if job is None or job["status"] != "queued":     # cancelled, or already run via the fast lane
            continue
        job.update(status="running", started=time.time(), step="Starting")
        try:
            audit = run_audit(job["url"], progress=lambda text: job.update(step=text),
                              allow_send=job.get("allow_send", True),
                              should_stop=lambda: job.get("cancel", False) or job.get("timed_out", False),
                              on_browser=lambda kill: job.update(_kill=kill))
            if job.get("cancel") and audit.get("id"):
                # Cancelled in the instant between the last check and saving: remove the saved file.
                (AUDITS_DIR / f"{audit['id']}.json").unlink(missing_ok=True)
                continue
            delivery = (audit.get("letter") or {}).get("delivery") or {}
            job.update(status="done", step="Finished", audit_id=audit.get("id"),
                       tier=audit_tier(audit), emailed=delivery.get("sent"),
                       errors=len(audit.get("errors") or []))
            if not audit.get("loaded"):
                first = (audit.get("errors") or [{}])[0].get("error") or "The site could not be loaded."
                job.update(status="failed", error=first.split("\n")[0][:200])   # first line only, e.g. "Site refused the automated browser (HTTP 403...)"
        except AuditCancelled:
            if job.get("timed_out"):                 # stopped by the watchdog: show it as failed
                job.update(status="failed", step="Timed out", finished=time.time(),
                           error=f"Timed out after {AUDIT_TIMEOUT_S // 60} min: the site hung the audit browser, so it was stopped.")
            continue                                 # (cancelled from the dashboard: job already removed)
        except Exception as e:                       # run_audit shouldn't raise, but never kill the worker
            job.update(status="failed", step="Failed", error=f"{type(e).__name__}: {e}"[:300])
        job["finished"] = time.time()


# Watchdog: an audit normally takes ~1 min. One running longer than this is stuck (some sites hang
# the browser in ways no timeout catches), so its browser is killed and it's marked failed. The worker
# then moves on to the next URL: you always keep all workers busy.
AUDIT_TIMEOUT_S = max(120, int(os.getenv("AUDIT_TIMEOUT_S", "360")))


def _watchdog():
    while not _stopping.is_set():
        time.sleep(10)
        now = time.time()
        with _lock:
            stuck = [j for j in _jobs.values() if j["status"] == "running" and j.get("started")
                     and now - j["started"] > AUDIT_TIMEOUT_S and not j.get("timed_out")]
        for job in stuck:
            job["timed_out"] = True
            job["step"] = "Timed out: stopping its browser"
            if job.get("_kill"):
                job["_kill"]()


threading.Thread(target=_watchdog, daemon=True, name="audit-watchdog").start()

for n in range(WORKERS):  # each thread takes the next queued job when it's free
    threading.Thread(target=_worker, daemon=True, name=f"audit-worker-{n + 1}").start()


def worker_count():
    return WORKERS
