// Home page: totals at the top + one card per audit.

function load() {
  fetchAudits();
}

function fetchAudits() {
  fetch("/api/audits")
    // If the server answered OK, read the JSON. Otherwise jump to .catch with an error message.
    .then((r) => (r.ok ? r.json() : Promise.reject(`API error ${r.status}`)))
    .then((audits) => {
      renderStats(audits);
      renderCards(audits);
      fetchCrossSite();   // the cross-site view changes whenever the audits do
      fetchUsage();       // so does the AI usage total
    })
    // Show errors on the page AND in the console, instead of failing silently.
    .catch((err) => {
      console.error(err);
      document.getElementById("cards").replaceChildren(el("p", { class: "muted" }, "Could not load audits: " + err));
    });
}

// Fill the 4 big numbers.
function renderStats(audits) {
  // Add up one field of tracker_counts across all audits. Missing -> 0.
  const sum = (key) => audits.reduce((total, a) => total + (a.tracker_counts?.[key] ?? 0), 0);
  const seen = sum("seen");
  const stopped = sum("stopped");

  document.getElementById("totalSites").textContent = audits.length;
  document.getElementById("totalSeen").textContent = seen;
  document.getElementById("totalBlocked").textContent = stopped;
  document.getElementById("totalAfter").textContent = sum("after");

  // Percentage stopped. "seen ? ... : 0" avoids dividing by zero when there are no trackers.
  const pct = seen ? Math.round((stopped / seen) * 100) : 0;
  document.getElementById("stopBar").style.width = pct + "%";
  document.getElementById("stopPct").textContent = `${pct}% of trackers found`;
}

// Pick the coloured label for a card.
function statusPill(a) {
  if (a.loaded === false) return el("span", { class: "pill warn" }, "Blocked / didn't load");
  if (a.rejected !== true) return el("span", { class: "pill warn" }, "Reject failed");
  if ((a.tracker_counts?.after ?? 0) > 0) return el("span", { class: "pill bad" }, "Ignored your no");
  return el("span", { class: "pill ok" }, "Respected your choice");
}

// Severe = we successfully clicked "Reject all" AND trackers kept sending anyway.
// (Same rule as the red "Ignored your no" pill above.)
function isSevere(a) {
  return a.rejected === true && (a.tracker_counts?.after ?? 0) > 0;
}

// Build one clickable card for an audit.
function makeCard(a) {
  const t = a.tracker_counts ?? {};
  const hidden = a.summary?.companies_not_disclosed ?? [];  // companies the policy didn't mention
  return el("a", { class: "card" + (isSevere(a) ? " severe" : ""), href: "audit.html?id=" + encodeURIComponent(a.id) },
    el("div", { class: "row" }, el("span", { class: "host" }, host(a.url)), statusPill(a)),
    el("div", { class: "date" }, fmtDate(a.started_at)),
    el("div", { class: "mini" },
      el("div", {}, el("b", {}, show(t.seen)), el("span", {}, "found")),
      el("div", { class: "ok" }, el("b", {}, show(t.stopped)), el("span", {}, "stopped")),
      el("div", { class: "bad" }, el("b", {}, show(t.after)), el("span", {}, "after reject"))),
    hidden.length ? el("div", {}, el("span", { class: "muted" }, "Not in policy: "),
      hidden.map((name) => el("span", { class: "chip bad" }, name))) : null);
}

// Split audits into Severe (top section) and everything else (Audits section).
function renderCards(audits) {
  const severe = audits.filter(isSevere)
    .sort((x, y) => (y.tracker_counts?.after ?? 0) - (x.tracker_counts?.after ?? 0));  // worst first
  const rest = audits.filter((a) => !isSevere(a));

  // Severe section only appears if there's at least one severe audit.
  document.getElementById("severeSection").hidden = severe.length === 0;
  document.getElementById("severeCount").textContent = `(${severe.length})`;
  document.getElementById("severeCards").replaceChildren(...severe.map(makeCard));

  const cards = document.getElementById("cards");
  if (rest.length === 0) {
    const msg = audits.length === 0 ? "No audits yet. Run one and it will appear here." : "No other audits.";
    cards.replaceChildren(el("p", { class: "muted" }, msg));
    return;
  }
  cards.replaceChildren(...rest.map(makeCard));
}


// ---------- Cross-site tracking ----------
let crossShowAll = false;

function fetchUsage() {
  fetch("/api/usage")
    .then((r) => (r.ok ? r.json() : Promise.reject(`API error ${r.status}`)))
    .then(renderUsage)
    .catch((err) => console.error(err));
}

// 12345 -> "12.3k", 1234567 -> "1.23M"
function fmtTokens(n) {
  if (n >= 1e6) return (n / 1e6).toFixed(2) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(1) + "k";
  return String(n);
}
const fmtUsd = (x) => "$" + (x < 1 ? x.toFixed(3) : x.toFixed(2));

// AI usage panel: calls, tokens, estimated spend (only if LLM_PRICES is set in .env).
function renderUsage(u) {
  const section = document.getElementById("usageSection");
  if (!u.audits) return (section.hidden = true);
  section.hidden = false;
  const tile = (n, l, sub) => el("div", { class: "usage-tile" },
    el("div", { class: "n" }, n), el("div", { class: "l" }, l), sub ? el("div", { class: "l" }, sub) : null);
  const priced = u.usd !== null && u.unpriced_audits < u.audits_with_ai;  // at least one audit has a real price
  const spend = priced ? fmtUsd(u.usd) + (u.unpriced_audits ? "+" : "") : "—";   // "+" = some audits not priced
  document.getElementById("usageGrid").replaceChildren(
    tile(u.total.llm_calls, "AI calls", `${u.today.llm_calls} today`),
    tile(fmtTokens(u.total.input_tokens), "Tokens in", `${fmtTokens(u.today.input_tokens)} today`),
    tile(fmtTokens(u.total.output_tokens), "Tokens out", `${fmtTokens(u.today.output_tokens)} today`),
    tile(spend, "Estimated spend", u.usd === null ? "set LLM_PRICES in .env"
      : priced ? `${fmtUsd(u.usd_today)} today` : "new audits will be priced"),
    tile(u.avg_per_audit.llm_calls, "Calls per audit (avg)",
      `${fmtTokens(u.avg_per_audit.input_tokens + u.avg_per_audit.output_tokens)} tokens · cap ${u.call_cap_per_audit}`));

  // Budget bar, only when both a budget and prices are set.
  const budget = document.getElementById("usageBudget");
  if (u.budget && priced) {
    const pct = Math.min(100, (u.usd / u.budget) * 100);
    budget.replaceChildren(el("div", { class: "bar" + (pct > 80 ? " warn" : "") }, el("i", { style: `width:${pct}%` })),
      el("div", { class: "muted small" }, `${fmtUsd(u.usd)} of $${u.budget} budget (${pct.toFixed(1)}%)`));
  } else budget.replaceChildren();

  const models = Object.entries(u.by_model).map(([m, x]) =>
    `${m}: ${x.llm_calls} calls, ${fmtTokens(x.input_tokens)} in / ${fmtTokens(x.output_tokens)} out` +
    (x.usd === null ? "" : ` (${fmtUsd(x.usd)})`));
  document.getElementById("usageModels").textContent = models.join(" · ");
  document.getElementById("usageNote").textContent =
    `${u.audits_with_ai} of ${u.audits} audits used AI` +
    (u.unpriced_audits ? ` · ${u.unpriced_audits} older audit${u.unpriced_audits > 1 ? "s" : ""} not in the spend estimate` : "");
}

function fetchCrossSite() {
  fetch("/api/cross-site")
    .then((r) => (r.ok ? r.json() : Promise.reject(`API error ${r.status}`)))
    .then(renderCrossSite)
    .catch((err) => console.error(err));
}

// One row per company: name, category, a bar for "share of sites", and the sites behind it.
function renderCrossSite(data) {
  const section = document.getElementById("crossSection");
  const rows = data.companies ?? [];
  // Only worth showing once we have a few sites and someone appears on more than one.
  if (data.sites_audited < 2 || !rows.some((c) => c.sites.length > 1)) return (section.hidden = true);
  section.hidden = false;
  document.getElementById("crossNote").textContent =
    `${rows.length} tracking companies across ${data.sites_audited} sites (newest audit per site)`;
  const shown = crossShowAll ? rows : rows.slice(0, 12);
  document.getElementById("crossRows").replaceChildren(...shown.map((c) => {
    const after = c.sites_after_reject.length;
    return el("details", { class: "cross-row" },
      el("summary", {},
        el("span", { class: "cross-name" }, c.company, " ", el("span", { class: "chip" }, show(c.category))),
        el("span", { class: "cross-bar" }, el("i", { style: `width:${c.share}%` })),
        el("span", { class: "cross-num" }, `${c.sites.length} of ${data.sites_audited} sites (${c.share}%)`,
          after ? el("span", { class: "hot" }, ` · ${after} after reject`) : null)),
      el("div", { class: "cross-sites muted small" },
        "Seen on: ", c.sites.join(", "),
        after ? el("div", {}, el("b", {}, "Still tracking after Reject all on: "), c.sites_after_reject.join(", ")) : null));
  }));
  const more = document.getElementById("crossMore");
  more.hidden = rows.length <= 12;
  more.textContent = crossShowAll ? "Show top 12" : `Show all ${rows.length} companies`;
  more.onclick = () => { crossShowAll = !crossShowAll; renderCrossSite(data); };
}
