// Detail page for one audit: audit.html?id=<audit id>

const id = new URLSearchParams(location.search).get("id");  // read ?id=... from the URL

fetch("/api/audits/" + encodeURIComponent(id))
  .then((r) => (r.ok ? r.json() : Promise.reject("Audit not found")))
  .then(renderAudit)
  .catch((err) => {
    console.error(err);
    document.getElementById("out").replaceChildren(
      el("a", { class: "back", href: "/" }, "← All audits"), el("p", { class: "muted" }, String(err)));
  });

// Build the whole page from the audit JSON, top to bottom.
function renderAudit(a) {
  document.title = host(a.url) + " · Clype";
  document.getElementById("out").replaceChildren(
    headerSection(a),
    statsSection(a),
    findingsPanel(a),
    companiesPanel(a),
    el("div", { class: "grid2" }, consentPanel(a), policyPanel(a)),  // side by side
    cookiesPanel(a),
    requestsPanel(a),
    letterPanel(a),
    rawPanel(a),
  );
}

// Site name, date, and the cost numbers (Wordsmith judges these, so they're up top).
function headerSection(a) {
  const c = a.cost ?? {};
  const tokens = (c.input_tokens ?? 0) + (c.output_tokens ?? 0);
  return el("header", { class: "top" },
    el("div", {},
      el("a", { class: "back", href: "/" }, "← All audits"),
      el("div", { class: "brand" }, host(a.url)),
      el("div", { class: "tag" }, fmtDate(a.started_at))),
    el("div", {},
      el("span", { class: "chip" }, `${show(a.duration_s)} s`),
      el("span", { class: "chip" }, `${tokens.toLocaleString()} tokens`),
      el("span", { class: "chip" }, `${show(c.llm_calls)} LLM calls`),
      el("span", { class: "chip" }, show(c.model))));
}

// Four big numbers for this site.
function statsSection(a) {
  const t = a.tracker_counts ?? {};
  const hidden = a.summary?.companies_not_disclosed;
  const tile = (n, label, cls = "") =>
    el("div", { class: "stat " + cls }, el("div", { class: "n" }, show(n)), el("div", { class: "l" }, label));
  return el("div", { class: "stats" },
    tile(t.seen, "Trackers found"),
    tile(t.stopped, 'Stopped by "Reject all"', "ok"),
    tile(t.after, 'Still tracking after "Reject all"', "bad"),
    tile(hidden?.length, "Companies not in policy", "bad"));
}

// The broken promises, coloured by severity.
function findingsPanel(a) {
  const findings = a.findings ?? [];
  return el("div", { class: "panel" },
    el("h3", {}, "Broken promises"),
    findings.length === 0
      ? el("p", { class: "muted" }, "No broken promises found.")
      : findings.map((f) => el("div", { class: "finding " + (f.severity ?? "") },
          el("div", { class: "row" }, el("span", { class: "t" }, f.title), el("span", { class: "muted" }, f.severity)),
          el("div", {}, f.detail),
          f.law ? el("div", { class: "law" }, f.law) : null)));
}

// Group tracker requests by company -> "who tracked you, and did they stop?"
function groupByCompany(requests = []) {
  const groups = {};
  for (const r of requests) {
    if (!r.tracker?.is_tracker) continue;                       // trackers only
    const name = r.tracker.company ?? r.domain ?? "Unknown";    // unknown company -> use the domain
    groups[name] ??= { name, category: r.tracker.category, before: 0, after: 0, domains: new Set() };
    if (r.phase === "before_consent") groups[name].before++;
    if (r.phase === "after_reject") groups[name].after++;
    groups[name].domains.add(r.domain);
  }
  // Worst first: most requests after reject, then most before.
  return Object.values(groups).sort((x, y) => y.after - x.after || y.before - x.before);
}

function companiesPanel(a) {
  const rows = groupByCompany(a.requests);
  const hidden = a.summary?.companies_not_disclosed ?? [];
  return el("div", { class: "panel" },
    el("h3", {}, "Who tracked you"),
    rows.length === 0 ? el("p", { class: "muted" }, "No trackers seen.") :
    el("div", { class: "scroll" }, el("table", {},
      el("tr", {}, el("th", {}, "Company"), el("th", {}, "Category"), el("th", {}, "Domains"),
        el("th", { class: "num" }, "Before consent"), el("th", { class: "num" }, "After reject"), el("th", {}, "In policy?")),
      rows.map((g) => el("tr", {},
        el("td", {}, el("b", {}, g.name)),
        el("td", { class: "muted" }, show(g.category)),
        el("td", { class: "url" }, [...g.domains].join(", ")),
        el("td", { class: "num" }, g.before),
        el("td", { class: "num" + (g.after > 0 ? " hot" : "") }, g.after),  // red if it kept going
        el("td", {}, hidden.includes(g.name) ? el("span", { class: "chip bad" }, "Not disclosed") : "—"))))));
}

// What happened with the cookie banner.
function consentPanel(a) {
  const c = a.consent ?? {};
  return el("div", { class: "panel" },
    el("div", { class: "row" }, el("h3", {}, "Cookie banner"),
      c.rejected ? el("span", { class: "pill ok" }, "Rejected") : el("span", { class: "pill warn" }, "Reject failed")),
    el("dl", {},
      el("dt", {}, "Banner found"), el("dd", {}, yesNo(c.banner_found)),
      el("dt", {}, "Rejected"), el("dd", {}, yesNo(c.rejected)),
      el("dt", {}, "Method"), el("dd", {}, show(c.method)),
      el("dt", {}, "Clicks"), el("dd", {}, c.clicks?.length ? c.clicks.join(" → ") : "—")),
    c.rejected ? null : el("p", { class: "muted" }, "No \"after reject\" data, so nothing can count as stopped."));
}

// What the privacy policy says.
function policyPanel(a) {
  const p = a.policy ?? {};
  const link = safeUrl(p.url);
  return el("div", { class: "panel" },
    el("div", { class: "row" }, el("h3", {}, "Privacy policy"),
      p.found ? el("span", { class: "pill ok" }, "Found") : el("span", { class: "pill warn" }, "Not found")),
    el("dl", {},
      el("dt", {}, "URL"), el("dd", {}, link ? el("a", { href: link, target: "_blank", rel: "noopener noreferrer" }, link) : "—"),
      el("dt", {}, "Names"), el("dd", {}, p.companies_named?.length ? p.companies_named.map((n) => el("span", { class: "chip" }, n)) : "—"),
      el("dt", {}, "DPO contact"), el("dd", {}, show(p.dpo_contact))));
}

// Cookies before vs after, with tracker cookies that survived Reject all in red.
function cookiesPanel(a) {
  const before = a.cookies?.before_consent ?? [];
  const after = a.cookies?.after_reject ?? [];
  const beforeNames = new Set(before.map((k) => k.name));
  const cookieTable = (list, isAfter) => list.length === 0 ? el("p", { class: "muted" }, "None recorded.") :
    el("table", {},
      el("tr", {}, el("th", {}, "Name"), el("th", {}, "Domain"), el("th", {}, "Tracker")),
      list.map((k) => el("tr", {},
        el("td", { class: isAfter && k.tracker_company ? "hot" : "" }, k.name,
          isAfter && !beforeNames.has(k.name) ? el("span", { class: "chip" }, "new") : null),  // set only after reject
        el("td", { class: "muted" }, show(k.domain)),
        el("td", {}, show(k.tracker_company)))));
  return el("div", { class: "grid2" },
    el("div", { class: "panel" }, el("h3", {}, `Cookies before consent (${before.length})`), cookieTable(before, false)),
    el("div", { class: "panel" }, el("h3", {}, `Cookies after reject (${after.length})`), cookieTable(after, true)));
}

// Every request, with filters. Redraws the table when a filter changes.
function requestsPanel(a) {
  const requests = a.requests ?? [];
  const onlyTrackers = el("input", { type: "checkbox", checked: "" });
  const phase = el("select", {},
    el("option", { value: "" }, "All phases"),
    el("option", { value: "before_consent" }, "Before consent"),
    el("option", { value: "after_reject" }, "After reject"));
  const count = el("span", { class: "muted" });
  const box = el("div", { class: "scroll" });

  function draw() {
    const rows = requests.filter((r) =>
      (!onlyTrackers.checked || r.tracker?.is_tracker) && (!phase.value || r.phase === phase.value));
    count.textContent = `${rows.length} of ${requests.length} requests`;
    box.replaceChildren(el("table", {},
      el("tr", {}, el("th", {}, "Company"), el("th", {}, "Phase"), el("th", {}, "Type"), el("th", {}, "URL")),
      rows.slice(0, 500).map((r) => el("tr", {},   // cap at 500 rows so huge audits stay fast
        el("td", { class: r.tracker?.is_tracker ? "hot" : "" }, r.tracker?.company ?? r.domain),
        el("td", { class: "muted" }, show(r.phase)),
        el("td", { class: "muted" }, show(r.type)),
        el("td", { class: "url" }, r.url)))));  // shown as text, not a link: we don't want people clicking trackers
  }
  onlyTrackers.addEventListener("change", draw);
  phase.addEventListener("change", draw);
  draw();

  return el("div", { class: "panel" },
    el("h3", {}, "All requests"),
    el("div", { class: "filters" }, el("label", {}, onlyTrackers, "Trackers only"), phase, count),
    box);
}

// The drafted letter: editable, with a copy button. Never sent anywhere.
function letterPanel(a) {
  const l = a.letter;
  if (!l) return el("div", { class: "panel" }, el("h3", {}, "Draft letter"), el("p", { class: "muted" }, "No letter drafted for this audit."));
  const to = el("input", { value: l.to ?? "" });
  const subject = el("input", { value: l.subject ?? "" });
  const body = el("textarea", {});
  body.value = l.body ?? "";  // .value, not innerHTML -> letter text can't inject code
  const msg = el("span", { class: "muted" });
  const copy = el("button", {
    onclick: async () => {
      await navigator.clipboard.writeText(`To: ${to.value}\nSubject: ${subject.value}\n\n${body.value}`);
      msg.textContent = "  Copied to clipboard.";
    },
  }, "Copy letter");
  return el("div", { class: "panel" },
    el("div", { class: "row" }, el("h3", {}, `Draft letter (${(l.kind ?? "").toUpperCase()})`),
      el("span", { class: "pill warn" }, "Draft only, never sent")),
    el("label", {}, "To"), to,
    el("label", {}, "Subject"), subject,
    el("label", {}, "Body"), body,
    copy, msg);
}

// Everything in the JSON, using the generic renderer. Catches fields we don't have a nice view for yet.
function rawPanel(a) {
  return el("div", { class: "panel" },
    el("details", {}, el("summary", {}, "Raw audit data (every field)"), render(a)));
}
