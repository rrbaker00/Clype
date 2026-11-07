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

// One clickable card per audit.
function renderCards(audits) {
  const cards = document.getElementById("cards");
  if (audits.length === 0) {
    cards.replaceChildren(el("p", { class: "muted" }, "No audits yet. Run one and it will appear here."));
    return;
  }
  cards.replaceChildren(...audits.map((a) => {
    const t = a.tracker_counts ?? {};
    const hidden = a.summary?.companies_not_disclosed ?? [];  // companies the policy didn't mention
    return el("a", { class: "card", href: "audit.html?id=" + encodeURIComponent(a.id) },
      el("div", { class: "row" }, el("span", { class: "host" }, host(a.url)), statusPill(a)),
      el("div", { class: "date" }, fmtDate(a.started_at)),
      el("div", { class: "mini" },
        el("div", {}, el("b", {}, show(t.seen)), el("span", {}, "found")),
        el("div", { class: "ok" }, el("b", {}, show(t.stopped)), el("span", {}, "stopped")),
        el("div", { class: "bad" }, el("b", {}, show(t.after)), el("span", {}, "after reject"))),
      hidden.length ? el("div", {}, el("span", { class: "muted" }, "Not in policy: "),
        hidden.map((name) => el("span", { class: "chip bad" }, name))) : null);
  }));
}
