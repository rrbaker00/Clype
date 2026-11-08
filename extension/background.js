// Clype extension, background script. Runs once for the whole browser.
//
// When you finish loading a page on a NEW site, we ask the Clype server (api/main.py, running on
// this computer) to audit it. The server's own headless browser does the work (reject all, browse,
// read the policy, AI review), so your browsing isn't touched or slowed down. We poll for the
// result, show it as a badge on the toolbar icon, and alert you if it's CRITICAL.

const SERVER = "http://127.0.0.1:8000";
const POLL_MS = 5000;           // how often to check on audits that are still running
const REVISIT_MS = 60 * 1000;   // don't ask the server about the same host more than once a minute

// Never auto-audit these (sensitive, or not real websites). Users can add more from the popup.
const DEFAULT_SKIP = [
  // sensitive
  "bank", "paypal.", "nhs.uk", "gov.uk", "mail.google.", "outlook.", "office.com", "live.com",
  "accounts.", "login.", "auth.",
  // search engines: you pass through them all the time; audit the sites you click through to instead
  "google.", "bing.com", "duckduckgo.com", "search.yahoo.", "ecosia.org", "startpage.com",
  // tools / dashboards, not sites you're "visiting"
  "addons.mozilla.org", "mozilla.org", "claude.ai", "discord", "brevo.com", "github.com",
];

const sites = {};         // site -> last server response {site, status, audit, step, error}
const hostToSite = {};    // "www.bbc.co.uk" -> "bbc.co.uk" (the server works out the site)
const lastAsked = {};     // host -> time we last asked the server
let serverUp = true;

// ---------- settings (saved in the browser) ----------
async function settings() {
  const s = await browser.storage.local.get({ enabled: true, monitor: true, skip: [], alerted: [], dismissed: [] });
  return s;
}

function hostOf(url) {
  try {
    const u = new URL(url);
    return /^https?:$/.test(u.protocol) ? u.hostname : null;
  } catch { return null; }
}

function isSkipped(host, extraSkip) {
  if (!host || host === "localhost" || /^[\d.]+$/.test(host) || host.includes(":")) return true;  // local / IPs
  return [...DEFAULT_SKIP, ...extraSkip].some((part) => host.includes(part));
}

// ---------- talking to the Clype server ----------
async function api(path, options) {
  try {
    const r = await fetch(SERVER + path, options);
    serverUp = true;
    if (!r.ok) return { error: (await r.json().catch(() => ({}))).detail || `HTTP ${r.status}` };
    return await r.json();
  } catch (e) {
    serverUp = false;                     // server not running
    return null;
  }
}

async function checkHost(url, start, force = false) {
  const host = hostOf(url);
  if (!host) return null;
  const res = start
    ? await api("/api/extension/visit", { method: "POST", headers: { "Content-Type": "application/json" },
                                         body: JSON.stringify({ url, force }) })
    : await api("/api/extension/site?url=" + encodeURIComponent(url));
  if (!res || res.error || !res.site) return res;
  hostToSite[host] = res.site;
  const before = sites[res.site];
  sites[res.site] = res;
  if (res.status === "done" && (!before || before.status !== "done" || before.audit?.id !== res.audit?.id)) {
    await onFinished(res);
  }
  await refreshBadges();
  return res;
}

// ---------- reacting to navigation ----------
browser.webNavigation.onCompleted.addListener(async (details) => {
  if (details.frameId !== 0) return;                       // only the main page, not iframes
  const host = hostOf(details.url);
  const s = await settings();
  if (!host || isSkipped(host, s.skip)) return refreshBadges();
  if (Date.now() - (lastAsked[host] || 0) < REVISIT_MS) return refreshBadges();
  lastAsked[host] = Date.now();
  await checkHost(details.url, s.enabled);                // enabled: start an audit if needed; else just look
});

browser.tabs.onActivated.addListener(refreshBadges);
browser.tabs.onUpdated.addListener((tabId, change) => { if (change.url) refreshBadges(); });

// Keep polling audits that are queued or running until they finish.
setInterval(async () => {
  for (const res of Object.values(sites)) {
    if (res.status === "queued" || res.status === "running") {
      await checkHost(res.audit?.url || "https://" + res.site, false);
    }
  }
}, POLL_MS);

// ---------- badge on the toolbar icon (per tab) ----------
const BADGES = {
  critical: ["!", "#e11d48"], high: ["H", "#ea580c"], medium: ["M", "#d97706"], low: ["✓", "#16a34a"],
};

function badgeFor(res) {
  if (!res) return ["", "#888"];
  if (res.status === "queued" || res.status === "running") return ["…", "#6b7280"];
  if (res.status === "failed") return ["×", "#6b7280"];
  if (res.status !== "done" || !res.audit) return ["", "#888"];
  if (res.audit.loaded === false) return ["?", "#6b7280"];  // the site blocked the audit browser
  return BADGES[res.audit.worst] || ["✓", "#16a34a"];      // no findings = all good
}

async function refreshBadges() {
  const tabs = await browser.tabs.query({});
  for (const tab of tabs) {
    const host = hostOf(tab.url);
    const [text, color] = badgeFor(sites[hostToSite[host]]);
    browser.browserAction.setBadgeText({ tabId: tab.id, text: serverUp ? text : "off" });
    browser.browserAction.setBadgeBackgroundColor({ tabId: tab.id, color: serverUp ? color : "#6b7280" });
  }
}

// ---------- critical alerts ----------
function alertFor(res) {
  const a = res.audit;
  return { type: "clype-alert", site: res.site, auditId: a.id,
           findings: a.top_findings || [], reportUrl: `${SERVER}/audit.html?id=${encodeURIComponent(a.id)}` };
}

async function onFinished(res) {
  if (res.audit?.worst !== "critical") return;
  const s = await settings();
  // System notification once per audit (remembered across restarts).
  if (!s.alerted.includes(res.audit.id)) {
    await browser.storage.local.set({ alerted: [...s.alerted, res.audit.id].slice(-200) });
    browser.notifications.create("clype:" + res.audit.id, {
      type: "basic", iconUrl: browser.runtime.getURL("icons/clype.svg"),
      title: `Clype: critical issue on ${res.site}`,
      message: res.audit.top_findings?.[0]?.title || "Open the report for details.",
    });
  }
  // In-page box on every open tab of that site.
  if (s.dismissed.includes(res.audit.id)) return;
  const tabs = await browser.tabs.query({});
  for (const tab of tabs) {
    if (hostToSite[hostOf(tab.url)] === res.site) {
      browser.tabs.sendMessage(tab.id, alertFor(res)).catch(() => {});   // page may not have the script yet
    }
  }
}

browser.notifications.onClicked.addListener((id) => {
  if (id.startsWith("clype:")) {
    browser.tabs.create({ url: `${SERVER}/audit.html?id=${encodeURIComponent(id.slice(6))}` });
  }
});

// ---------- messages from the page (content.js) and the popup ----------
browser.runtime.onMessage.addListener(async (msg, sender) => {
  if (msg.type === "clype-hello") {
    // A page (or a frame in it) just loaded. Tell it: show the critical box? click reject?
    const res = sites[hostToSite[hostOf(sender.tab?.url)]];
    const s = await settings();
    const alert = sender.frameId === 0 && res?.status === "done" && res.audit?.worst === "critical"
      && !s.dismissed.includes(res.audit.id) ? alertFor(res) : null;
    const session = sessions[sender.tab?.id];
    return { alert, autoReject: Boolean(session && !session.sent && !session.rejected) };
  }
  if (msg.type === "clype-rejected") {
    await markRejected(sender.tab?.id, msg.label);
    return true;
  }
  if (msg.type === "popup-reset-site") {
    // Forget this site's cookies + stored consent (localStorage), so its banner shows again.
    const hosts = [...new Set([msg.host, msg.site, msg.site && "www." + msg.site].filter(Boolean))];
    await browser.browsingData.remove({ hostnames: hosts }, { cookies: true, localStorage: true });
    // Start over for this site: (1) forget this tab's finished recording, so after the reload we
    // reject the banner again and record a fresh "your browser" capture; (2) re-audit on the server
    // now, even if it was audited in the last 7 days.
    const old = sessions[msg.tabId];
    if (old) { clearTimeout(old.timer); delete sessions[msg.tabId]; }
    lastAsked[msg.host] = Date.now();               // the reload shouldn't send a second (normal) request
    const s = await settings();
    if (s.enabled && msg.url) await checkHost(msg.url, true, true);
    return true;
  }
  if (msg.type === "popup-monitor") {
    await browser.storage.local.set({ monitor: msg.monitor });
    return true;
  }
  if (msg.type === "clype-dismiss") {
    const s = await settings();
    await browser.storage.local.set({ dismissed: [...s.dismissed, msg.auditId].slice(-200) });
    return true;
  }
  if (msg.type === "popup-state") {
    // Everything the popup needs about the current tab.
    const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
    const host = hostOf(tab?.url);
    const s = await settings();
    let res = sites[hostToSite[host]];
    if (host && !res && !isSkipped(host, s.skip)) res = await checkHost(tab.url, false);
    const yours = res?.site ? await api("/api/sessions/latest?site=" + encodeURIComponent(res.site)) : null;
    const live = sessions[tab?.id];
    return { server: SERVER, serverUp, enabled: s.enabled, monitor: s.monitor, host, url: tab?.url, yours,
             recording: live && !live.sent ? { requests: live.requests.length, rejected: live.rejected,
                                               label: live.label } : null,
             skipped: host ? isSkipped(host, s.skip) : true, userSkipped: s.skip.includes(host), site: res };
  }
  if (msg.type === "popup-audit-now") {
    lastAsked[hostOf(msg.url)] = Date.now();
    return checkHost(msg.url, true);
  }
  if (msg.type === "popup-toggle") {
    await browser.storage.local.set({ enabled: msg.enabled });
    return true;
  }
  if (msg.type === "popup-skip") {
    const s = await settings();
    const skip = msg.skip ? [...new Set([...s.skip, msg.host])] : s.skip.filter((h) => h !== msg.host);
    await browser.storage.local.set({ skip });
    return true;
  }
});


// =====================================================================================
// Phase 2: YOUR browser. When you open a new site we (1) click "reject" on its cookie banner in
// your tab (content.js; reject-only, never accept), (2) record your tab's requests before/after that
// click, then (3) send the capture + the cookies of the domains involved to the local server, which
// runs the same plain-code checks as an audit. Nothing leaves this computer.
// =====================================================================================
const SEND_AFTER_REJECT_MS = 25000;   // keep recording this long after the reject, then send
const SEND_NO_BANNER_MS = 40000;      // no banner found / already answered: send after this long
const MAX_REQUESTS = 3000;
const sessions = {};                  // tabId -> {host, url, started, rejected, label, requests, sent, timer}

async function startSession(tabId, url) {
  const s = await settings();
  const host = hostOf(url);
  const old = sessions[tabId];
  if (old && old.host === host) return;               // same site, keep recording
  if (old && !old.sent) await sendSession(tabId);     // left the site: send what we have
  if (!s.monitor || !host || isSkipped(host, s.skip)) { delete sessions[tabId]; return; }
  sessions[tabId] = { host, url, started: new Date().toISOString(), rejected: false, label: null,
                      bannerFound: false, requests: [], cookiesBefore: null, sent: false,
                      timer: setTimeout(() => sendSession(tabId), SEND_NO_BANNER_MS) };
}

// Main-frame navigation starts (or continues) a session BEFORE the page's own requests fire.
browser.webNavigation.onBeforeNavigate.addListener((d) => { if (d.frameId === 0) startSession(d.tabId, d.url); });
browser.tabs.onRemoved.addListener((tabId) => { if (sessions[tabId] && !sessions[tabId].sent) sendSession(tabId); });

function bodyText(details) {
  const b = details.requestBody;
  if (!b) return "";
  if (b.formData) return new URLSearchParams(Object.entries(b.formData).flatMap(([k, vs]) => vs.map((v) => [k, v]))).toString().slice(0, 20000);
  if (b.raw?.[0]?.bytes) {
    try { return new TextDecoder("utf-8", { fatal: false }).decode(b.raw[0].bytes).slice(0, 20000); } catch { return ""; }
  }
  return "";
}

browser.webRequest.onBeforeRequest.addListener((details) => {
  const session = sessions[details.tabId];
  if (!session || session.sent || details.url.startsWith(SERVER)) return;
  if (session.requests.length >= MAX_REQUESTS) return;
  session.requests.push({ url: details.url, method: details.method, type: details.type,
                          phase: session.rejected ? "after_reject" : "before_consent", _post: bodyText(details) });
}, { urls: ["<all_urls>"] }, ["requestBody"]);

// Cookies for THIS site only: the site's own + those of domains its requests went to (never the
// whole cookie jar). Includes Firefox's partitioned (Total Cookie Protection) cookies for the site.
async function siteCookies(session) {
  const site = hostToSite[session.host] || session.host;
  const domains = new Set([site, ...session.requests.map((r) => hostOf(r.url)).filter(Boolean)]);
  const related = (c) => [...domains].some((d) => d.endsWith(c.domain.replace(/^\./, "")) ||
                                                   c.domain.replace(/^\./, "").endsWith(d));
  let all = [];
  try { all = all.concat((await browser.cookies.getAll({})).filter(related)); } catch {}
  try {
    const part = await browser.cookies.getAll({ partitionKey: { topLevelSite: "https://" + site } });
    all = all.concat(part.filter((c) => c.partitionKey).map((c) => ({ ...c, partitioned: true })));
  } catch {}
  const same = { no_restriction: "None", lax: "Lax", strict: "Strict" };
  return all.map((c) => ({ name: c.name, value: c.value, domain: c.domain, path: c.path,
                           expires: c.expirationDate ?? -1, httpOnly: c.httpOnly, secure: c.secure,
                           sameSite: same[c.sameSite] ?? c.sameSite, partitioned: Boolean(c.partitioned) }));
}

async function markRejected(tabId, label) {
  const session = sessions[tabId];
  if (!session || session.sent || session.rejected) return;
  session.cookiesBefore = await siteCookies(session);   // snapshot at the moment of the click
  session.rejected = true;
  session.bannerFound = true;
  session.label = String(label || "").slice(0, 80);
  clearTimeout(session.timer);
  session.timer = setTimeout(() => sendSession(tabId), SEND_AFTER_REJECT_MS);
}

async function sendSession(tabId) {
  const session = sessions[tabId];
  if (!session || session.sent) return;
  session.sent = true;
  clearTimeout(session.timer);
  const now = await siteCookies(session);
  const capture = {
    url: session.url, started_at: session.started, banner_found: session.bannerFound,
    rejected: session.rejected, reject_label: session.label, browser: navigator.userAgent,
    requests: session.requests,
    cookies: session.rejected ? { before_consent: session.cookiesBefore, after_reject: now }
                              : { before_consent: now, after_reject: [] },
  };
  session.requests = [];                                 // free memory either way
  if (capture.requests.length) {
    await api("/api/extension/session", { method: "POST", headers: { "Content-Type": "application/json" },
                                          body: JSON.stringify(capture) });
  }
}
