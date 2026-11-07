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
