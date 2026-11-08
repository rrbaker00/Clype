// Clype extension popup: the current site's status + every report (newest audit per site).

const $ = (id) => document.getElementById(id);

// Tiny element helper (same idea as web/common.js): text is always textContent, never HTML.
function el(tag, props = {}, ...children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  for (const c of children.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    e.append(c instanceof Node ? c : String(c));
  }
  return e;
}

const fmtDate = (iso) => iso ? new Date(iso).toLocaleString(undefined,
  { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "";

function sevPill(audit) {
  if (!audit) return null;
  if (audit.loaded === false) return el("span", { class: "pill sev-none" }, "blocked");
  const worst = audit.worst || "ok";
  return el("span", { class: `pill sev-${worst}` }, worst === "ok" ? "no issues" : worst);
}

function currentCard(state) {
  if (!state.serverUp) {
    return el("div", { class: "card" },
      el("b", {}, "Clype server isn't running"),
      el("p", { class: "muted small" }, "Start it in the project folder with:"),
      el("code", { class: "small" }, "uvicorn api.main:app"));
  }
  if (!state.host) return el("div", { class: "card muted" }, "Open a website to audit it.");
  const res = state.site, audit = res?.audit;
  const report = audit ? `${state.server}/audit.html?id=${encodeURIComponent(audit.id)}` : null;
  let status;
  if (state.skipped) status = state.userSkipped ? "Skipped (you chose to skip this site)" : "Skipped automatically (search engines, sensitive and local sites aren't audited)";
  else if (!res) status = "Not audited yet";
  else if (res.status === "queued") status = "Waiting in the audit queue…";
  else if (res.status === "running") status = `Auditing: ${res.step || "working"}…`;
  else if (res.status === "failed") status = "Audit failed: " + (res.error || "the site couldn't be loaded");
  else if (res.status === "none") status = state.enabled ? "Not audited yet" : "Not audited (auto-audit is off)";
  else if (audit?.loaded === false) status = "The site blocked our audit browser";
  else status = `Audited ${fmtDate(audit?.started_at)}`;

  const busy = res && (res.status === "queued" || res.status === "running");
  return el("div", { class: "card" + (audit?.worst === "critical" ? " critical" : "") },
    el("div", { class: "row" }, el("span", { class: "site" }, res?.site || state.host),
      res?.status === "done" ? sevPill(audit) : null),
    el("div", { class: "muted small" }, status),
    res?.status === "done" && audit?.top_findings?.length
      ? el("ul", { class: "small" }, audit.top_findings.map((f) =>
          el("li", {}, el("span", { class: `sev-${f.severity}` }, f.severity), " ", f.title)))
      : null,
    yoursBlock(state),
    el("div", { class: "actions" },
      report ? el("a", { href: report, target: "_blank" }, el("button", {}, "Open report")) : null,
      !state.skipped && !busy && res?.status !== "done"
        ? el("button", { onclick: () => auditNow(state.url) }, "Audit now") : null,
      state.host && !(state.skipped && !state.userSkipped)
        ? el("button", { class: "secondary", onclick: () => setSkip(state.host, !state.userSkipped) },
            state.userSkipped ? "Stop skipping" : "Skip this site") : null,
      state.host && !state.skipped
        ? el("button", { class: "secondary", title: "Clear this site's cookies and saved cookie choice, then reload",
                         onclick: () => resetSite(state) }, "Reset this site's cookies") : null));
}

// "Your browser": what Firefox itself sent on this site after the extension clicked reject in your tab.
function yoursBlock(state) {
  const live = state.recording, y = state.yours;
  if (live) {
    return el("div", { class: "yours small" }, el("b", {}, "Your browser: "),
      live.rejected ? `clicked "${live.label}", recording what's still sent (${live.requests} requests)…`
                    : `recording (${live.requests} requests), looking for the cookie banner…`);
  }
  if (!y) return null;
  const after = y.companies_after_reject ?? [];
  return el("div", { class: "yours small" },
    el("b", {}, "Your browser "), el("span", { class: "muted" }, fmtDate(y.started_at)), el("br"),
    !y.rejected ? el("span", { class: "muted" }, y.banner_found ? "Banner found but not rejected."
                   : "No cookie banner found (if you answered it before, use Reset this site's cookies).")
      : after.length ? el("span", { class: "sev-critical" }, `After you rejected: ${after.join(", ")} still received data.`)
      : el("span", { class: "sev-low" }, "After you rejected, no known trackers received data."));
}

async function resetSite(state) {
  const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
  // Clears cookies, forgets the tab's recording and queues a fresh audit (even if one ran recently).
  await browser.runtime.sendMessage({ type: "popup-reset-site", host: state.host, site: state.site?.site,
                                      url: state.url, tabId: tab?.id });
  if (tab) browser.tabs.reload(tab.id);            // banner shows again -> the extension rejects it again
  window.close();
}

async function auditNow(url) {
  await browser.runtime.sendMessage({ type: "popup-audit-now", url });
  load();
}

async function setSkip(host, skip) {
  await browser.runtime.sendMessage({ type: "popup-skip", host, skip });
  load();
}

async function loadReports(server) {
  try {
    const r = await fetch(server + "/api/audits");
    const all = await r.json();                 // newest first
    const seen = new Set();
    const latest = all.filter((a) => !seen.has(a.site) && seen.add(a.site));
    $("reports").replaceChildren(...(latest.length ? latest.map((a) =>
      el("a", { class: "report", href: `${server}/audit.html?id=${encodeURIComponent(a.id)}`, target: "_blank" },
        el("div", {}, el("div", { class: "site" }, a.site), el("div", { class: "date" }, fmtDate(a.started_at))),
        sevPill(a)))
      : [el("p", { class: "muted small" }, "No reports yet.")]));
  } catch {
    $("reports").replaceChildren(el("p", { class: "muted small" }, "Can't reach the Clype server."));
  }
}

let timer = null;
async function load() {
  const state = await browser.runtime.sendMessage({ type: "popup-state" });
  $("enabled").checked = state.enabled;
  $("monitor").checked = state.monitor;
  $("dashboard").href = state.server + "/";
  $("current").replaceChildren(currentCard(state));
  if (state.serverUp) loadReports(state.server);
  clearTimeout(timer);
  const busy = ["queued", "running"].includes(state.site?.status) || state.recording;
  if (busy) timer = setTimeout(load, 3000);     // refresh while an audit runs
}

$("monitor").addEventListener("change", (e) =>
  browser.runtime.sendMessage({ type: "popup-monitor", monitor: e.target.checked }));
$("enabled").addEventListener("change", (e) =>
  browser.runtime.sendMessage({ type: "popup-toggle", enabled: e.target.checked }));

load();
