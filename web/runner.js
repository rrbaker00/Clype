// "Run an audit" panel: start one audit or a file of them, then show the live queue.
// The server runs audits one at a time (api/jobs.py); we poll GET /api/jobs every 2 s
// while anything is queued or running, and refresh the audit cards when one finishes.

let pollTimer = null;
const finishedSeen = new Set();   // job ids we've already refreshed the cards for

// Turn the uploaded file's text into a list of URLs.
// Accepts: ["a.com", "b.com"]  or  {"urls": [...]}  or  "a.com, b.com"  or one URL per line.
function parseUrlFile(text) {
  const t = text.trim();
  try {
    const data = JSON.parse(t);
    const list = Array.isArray(data) ? data : data.urls;
    if (Array.isArray(list)) return list.map(String);
  } catch { /* not JSON, fall through to plain text */ }
  return t.split(/[\s,;]+/).map((s) => s.replace(/^["']|["']$/g, "")).filter(Boolean);
}

function setMsg(text) {
  document.getElementById("runMsg").textContent = text;
}

// POST some JSON and return the parsed answer, or throw with the server's error message.
async function postJson(path, body) {
  const res = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `API error ${res.status}`);
  return data;
}

async function startOne(e) {
  e.preventDefault();                                   // stop the form reloading the page
  const input = document.getElementById("auditUrl");
  if (!input.value.trim()) return;
  try {
    const job = await postJson("/api/audit", { url: input.value });
    setMsg(`Queued ${job.url}.`);
    input.value = "";
    pollJobs();
  } catch (err) {
    setMsg("Could not start: " + err.message);
  }
}

// Cancel everything still waiting. Running audits finish on their own.
async function cancelQueued() {
  if (!confirm("Cancel all audits that haven't started yet? Running ones will still finish.")) return;
  try {
    const { cancelled } = await postJson("/api/jobs/cancel", {});
    setMsg(`Cancelled ${cancelled} waiting audit${cancelled === 1 ? "" : "s"}.`);
    pollJobs();
  } catch (err) {
    setMsg("Could not cancel: " + err.message);
  }
}

// A file was chosen: show its name + URL count, so you can check it before auditing.
async function showChosenFile() {
  const file = document.getElementById("auditFile").files[0];
  const info = document.getElementById("fileInfo");
  if (!file) return (info.hidden = true);
  const urls = parseUrlFile(await file.text());
  document.getElementById("fileInfoText").textContent =
    `${file.name}: ${urls.length} URL${urls.length === 1 ? "" : "s"} found` + (urls.length > 300 ? " (only the first 300 will be audited)" : "");
  info.hidden = false;
}

// "Remove file": clear the file picker so nothing is attached any more.
function removeFile() {
  document.getElementById("auditFile").value = "";   // the only way to empty a file input
  document.getElementById("fileInfo").hidden = true;
  setMsg("File removed.");
}

async function startFile() {
  const file = document.getElementById("auditFile").files[0];
  if (!file) return setMsg("Choose a file first.");
  const urls = parseUrlFile(await file.text());
  if (!urls.length) return setMsg("No URLs found in that file.");
  try {
    const skip_audited = document.getElementById("skipAudited").checked;
    const { queued, rejected } = await postJson("/api/audit/batch", { urls, skip_audited });
    let msg = `Queued ${queued.length} audit${queued.length === 1 ? "" : "s"}.`;
    if (rejected.length) {
      // Group by reason so a 300-line file gives one readable line, e.g. "120 already audited, 2 duplicate".
      const byReason = {};
      for (const r of rejected) (byReason[r.reason] ??= []).push(r.url);
      msg += " Skipped " + Object.entries(byReason).map(([reason, list]) =>
        `${list.length} ${reason}` + (list.length <= 3 ? ` (${list.join(", ")})` : "")).join(", ") + ".";
    }
    setMsg(msg);
    removeFileQuietly();
    pollJobs();
  } catch (err) {
    setMsg("Could not start: " + err.message);
  }
}

// Same as removeFile, without overwriting the "Queued N audits" message.
function removeFileQuietly() {
  document.getElementById("auditFile").value = "";
  document.getElementById("fileInfo").hidden = true;
}

// How a job looks in the list.
function jobRow(j) {
  const secs = j.started ? Math.round((j.finished ?? Date.now() / 1000) - j.started) : null;
  let status = j.status === "running" ? `${j.step}… ${secs}s` : j.status;
  if (j.status === "done") status = `done in ${secs}s` + (j.tier ? ` · worst finding: ${j.tier}` : " · no findings") +
    (j.emailed ? " · emailed" : "") + (j.errors ? ` · ${j.errors} step(s) failed` : "");
  if (j.status === "failed") status = "failed: " + (j.error ?? "unknown error");
  const label = j.audit_id
    ? el("a", { href: "audit.html?id=" + encodeURIComponent(j.audit_id) }, host(j.url))
    : el("span", {}, host(j.url));
  const active = j.status === "running" || j.status === "queued";
  return el("li", { class: "job " + j.status + (j.tier === "critical" ? " critical" : "") },
    el("span", { class: "job-text" }, label, el("span", { class: "muted" }, " " + status)),
    active ? el("button", { type: "button", class: "job-x", title: "Cancel this audit and remove it",
                            "aria-label": `Cancel the audit of ${host(j.url)}`, onclick: () => cancelJob(j) }, "✕") : null);
}

// ✕ on one job: a waiting audit is dropped; a running one stops at its next step and saves nothing.
async function cancelJob(j) {
  const running = j.status === "running";
  if (!confirm(`Cancel the audit of ${host(j.url)}?` + (running ? " It's running: its browser is stopped straight away and nothing is saved." : ""))) return;
  try {
    const r = await fetch(`/api/jobs/${encodeURIComponent(j.id)}/cancel`, { method: "POST" });
    if (!r.ok && r.status !== 404) throw new Error((await r.json().catch(() => ({}))).detail || `HTTP ${r.status}`);
    setMsg(`Cancelled the audit of ${host(j.url)}.`);
  } catch (err) {
    setMsg("Could not cancel: " + err.message);
  }
  pollJobs();
}

// Queue list open/closed. Remembered in this browser (localStorage can be unavailable: then just
// use the default: open for a few jobs, closed for a big batch).
function queueOpen(total) {
  try {
    const saved = localStorage.getItem("clype.queueOpen");
    if (saved !== null) return saved === "1";
  } catch {}
  return total <= 5;
}

function toggleQueue() {
  const list = document.getElementById("jobList");
  const open = list.hidden;                              // hidden now -> we're opening it
  try { localStorage.setItem("clype.queueOpen", open ? "1" : "0"); } catch {}
  pollJobs();
}

async function pollJobs() {
  clearTimeout(pollTimer);
  let list = [];
  try {
    list = await (await fetch("/api/jobs")).json();
  } catch {
    return;                                             // server restarting; next action will retry
  }
  // Summary line + progress bar, so a 300-URL batch is readable at a glance.
  const count = (s) => list.filter((j) => j.status === s).length;
  const [queued, running, done, failed] = ["queued", "running", "done", "failed"].map(count);
  const total = list.length, finished = done + failed + count("cancelled");
  const critical = list.filter((j) => j.tier === "critical").length;
  const open = queueOpen(total);
  document.getElementById("jobList").hidden = !open;
  document.getElementById("queueSummary").replaceChildren(...(total ? [
    el("div", { class: "queue-head" },
      el("span", { class: "muted small" },
        `${finished}/${total} finished · ${running} running · ${queued} waiting · ${failed} failed` +
        (count("cancelled") ? ` · ${count("cancelled")} cancelled` : "") +
        (critical ? ` · ${critical} critical` : "")),
      el("button", { type: "button", class: "secondary queue-toggle", "aria-expanded": String(open),
                     "aria-controls": "jobList", onclick: toggleQueue },
        open ? "Hide list ▴" : `Show list (${total}) ▾`)),
    el("div", { class: "bar" }, el("i", { style: `width:${Math.round((finished / total) * 100)}%` })),
  ] : []));
  // "Cancel waiting audits" only makes sense while something is waiting.
  document.getElementById("cancelQueuedBtn").hidden = queued === 0;
  // Show what's running first, then the most recent others (max 30 rows).
  const order = { running: 0, queued: 2, done: 1, failed: 1, cancelled: 3 };
  const shown = [...list].sort((a, b) => order[a.status] - order[b.status] || b.created - a.created).slice(0, 30);
  document.getElementById("jobList").replaceChildren(...shown.map(jobRow));
  if (list.length > 30) document.getElementById("jobList").append(el("li", { class: "muted small" }, `…and ${list.length - 30} more`));
  // A job just finished? Refresh the totals + audit cards so it appears.
  const newlyDone = list.filter((j) => ["done", "failed", "cancelled"].includes(j.status) && !finishedSeen.has(j.id));
  newlyDone.forEach((j) => finishedSeen.add(j.id));
  if (newlyDone.length) fetchAudits();
  // Keep polling only while something is still in progress.
  if (list.some((j) => j.status === "queued" || j.status === "running")) pollTimer = setTimeout(pollJobs, 2000);
}

window.addEventListener("load", () => {
  document.getElementById("auditForm").addEventListener("submit", startOne);
  document.getElementById("auditFileBtn").addEventListener("click", startFile);
  document.getElementById("auditFile").addEventListener("change", showChosenFile);
  document.getElementById("fileRemoveBtn").addEventListener("click", removeFile);
  document.getElementById("cancelQueuedBtn").addEventListener("click", cancelQueued);
  // Remember the "skip already audited" tick box in this browser.
  const skip = document.getElementById("skipAudited");
  try { const v = localStorage.getItem("clype.skipAudited"); if (v !== null) skip.checked = v === "1"; } catch {}
  skip.addEventListener("change", () => { try { localStorage.setItem("clype.skipAudited", skip.checked ? "1" : "0"); } catch {} });
  // Don't re-trigger "refresh cards" for jobs that finished before this page was opened.
  fetch("/api/jobs").then((r) => r.json()).then((list) => {
    list.filter((j) => ["done", "failed"].includes(j.status)).forEach((j) => finishedSeen.add(j.id));
    pollJobs();
  }).catch(() => {});
});
