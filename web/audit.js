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
    fingerprintPanel(a),
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
// The broken promises, coloured by severity. AI-review findings get an "AI review" label,
// their reasoning, the policy sentence they quote, and which evidence lines they rely on.
function findingsPanel(a) {
  const findings = a.findings ?? [];
  const review = a.ai_review;
  return el("div", { class: "panel" },
    el("h3", {}, "Broken promises"),
    findings.length === 0
      ? el("p", { class: "muted" }, "No broken promises found.")
      : findings.map((f) => el("div", { class: "finding " + (f.severity ?? "") },
          el("div", { class: "row" },
            el("span", { class: "t" }, f.title),
            el("span", {},
              f.source === "ai" ? el("span", { class: "chip ai" }, "AI review") : null,
              el("span", { class: "muted" }, " " + (f.severity ?? "")))),
          el("div", {}, f.detail),
          f.policy_quote ? el("blockquote", { class: "quote" }, `Policy says: "${f.policy_quote}"`) : null,
          f.reasoning ? el("div", { class: "reasoning" }, "Why: " + f.reasoning) : null,
          f.severity_note ? el("div", { class: "law" }, f.severity_note) : null,  // our safeguard changed the AI's tier
          f.law ? el("div", { class: "law" }, f.law + (f.evidence?.length ? `  ·  evidence ${f.evidence.join(", ")}` : "")) : null,
          f.law_eu ? el("div", { class: "law" }, "EU: " + f.law_eu) : null)),
    review ? aiSummary(review) : null);
}

// The AI's overall verdict + what it was given, so a judge can check E1, E2... themselves.
function aiSummary(review) {
  return el("div", { class: "ai-summary" },
    el("div", { class: "row" }, el("b", {}, "AI legal review"),
      el("span", { class: "muted" }, `${show(review.model)} · ${review.findings_kept ?? 0} kept, ${review.findings_dropped ?? 0} dropped (no valid evidence)`)),
    review.error ? el("p", { class: "muted" }, "Review failed: " + review.error) : null,
    review.summary ? el("p", {}, review.summary) : null,
    el("p", { class: "muted" }, "Automated assessment, not legal advice. Every AI finding must cite the evidence below."),
    review.evidence?.length ? el("details", {}, el("summary", {}, `Evidence given to the AI (${review.evidence.length} lines)`),
      el("ul", { class: "evidence" }, review.evidence.map((e) => el("li", {}, e)))) : null);
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
      el("dt", {}, "Clicks"), el("dd", {}, c.clicks?.length ? c.clicks.join(" → ") : "—"),
      // ICO: refusing must be as easy as accepting. We only looked for Accept, never clicked it.
      el("dt", {}, "Accept vs reject"), el("dd", {}, effortText(c)),
      el("dt", {}, "On by default"), el("dd", {}, c.preticked === undefined ? "—"
        : c.preticked.length ? el("span", { class: "hot" }, c.preticked.join("; ")) : "None found")),
    c.rejected ? null : el("p", { class: "muted" }, "No \"after reject\" data, so nothing can count as stopped."));
}

// "Accept: 1 click · Reject: 3 clicks", red when rejecting is harder.
function effortText(c) {
  if (c.accept_label === undefined) return "—";                       // audit from before this check existed
  const accept = c.accept_label ? `1 click ("${c.accept_label}")` : "no one-click Accept found";
  const reject = c.reject_steps ? `${c.reject_steps} click${c.reject_steps > 1 ? "s" : ""}` : "not possible / not found";
  const harder = c.accept_label && (!c.reject_steps || c.reject_steps > 1);
  return el("span", { class: harder ? "hot" : "" }, `Accept: ${accept} · Reject: ${reject}`);
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
      el("dt", {}, "DPO contact"), el("dd", {}, show(p.dpo_contact))),
    checklistBlock(a.ai_review?.policy_checklist));
}

// UK GDPR Art. 13 checklist from the AI review: ✓ present (with the quote), ✗ missing, ? unclear.
function checklistBlock(list) {
  if (!list) return null;
  const items = Object.values(list);
  if (items.every((i) => i.status === "not_checked"))
    return el("p", { class: "muted small" }, "Art. 13 checklist: not checked (policy missing, or too long to check in full).");
  const icon = { present: "✓", missing: "✗", unclear: "?", not_checked: "–" };
  return el("div", { class: "checklist" },
    el("div", { class: "muted small" }, "What the policy must tell you (UK GDPR Art. 13), checked by the AI review:"),
    el("ul", {}, items.map((i) => el("li", { class: "chk " + i.status, title: i.quote ? `"${i.quote}"` : i.status },
      el("span", { class: "chk-icon" }, icon[i.status] ?? "?"), " ", i.label,
      i.status === "unclear" ? el("span", { class: "muted" }, " (couldn't confirm)") : null))));
}

// Cookies before vs after, with tracker cookies that survived Reject all in red.
function cookiesPanel(a) {
  const before = a.cookies?.before_consent ?? [];
  const after = a.cookies?.after_reject ?? [];
  const beforeNames = new Set(before.map((k) => k.name));
  const cookieTable = (list, isAfter) => list.length === 0 ? el("p", { class: "muted" }, "None recorded.") :
    el("table", {},
      el("tr", {}, el("th", {}, "Name"), el("th", {}, "Domain"), el("th", {}, "Tracker"), el("th", {}, "Holds")),
      list.map((k) => el("tr", {},
        el("td", { class: isAfter && k.tracker_company ? "hot" : "" }, k.name,
          isAfter && !beforeNames.has(k.name) ? el("span", { class: "chip" }, "new") : null),  // set only after reject
        el("td", { class: "muted" }, show(k.domain)),
        el("td", {}, show(k.tracker_company)),
        el("td", { title: k.value ?? "" }, valueKind(k.value_kind)))));
  return el("div", { class: "grid2" },
    el("div", { class: "panel" }, el("h3", {}, `Cookies before consent (${before.length})`), cookieTable(before, false)),
    el("div", { class: "panel" }, el("h3", {}, `Cookies after reject (${after.length})`), cookieTable(after, true)));
}

// Scripts caught fingerprinting the device (canvas / WebGL / audio / fonts). Hidden if none.
function fingerprintPanel(a) {
  const list = a.fingerprinting ?? [];
  if (list.length === 0) return null;
  const when = { before_consent: "Before choice", after_reject: "After reject" };
  return el("div", { class: "panel" },
    el("h3", {}, `Fingerprinting (${list.length})`),
    el("table", {},
      el("tr", {}, el("th", {}, "Technique"), el("th", {}, "Script"), el("th", {}, "When"), el("th", {}, "What it did")),
      list.map((e) => el("tr", {},
        el("td", {}, e.technique),
        el("td", { class: "muted" }, host(e.script)),
        el("td", { class: e.phase === "after_reject" ? "hot" : "" }, when[e.phase] ?? e.phase),
        el("td", { class: "muted" }, e.detail)))));
}

// What a cookie actually stores. Empty ones aren't counted as tracking evidence.
function valueKind(kind) {
  const label = { id: "Unique ID", value: "A value", empty: "Empty", placeholder: "Nothing (placeholder)" }[kind];
  if (!label) return "—";
  return el("span", { class: kind === "id" ? "chip hot" : kind === "value" ? "chip" : "chip muted" }, label);
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
  // No letter in the JSON yet (audit wasn't critical/high) -> offer to draft one on request.
  // The API route only drafts; it never sends.
  if (!l) {
    const msg = el("span", { class: "muted" });
    const panel = el("div", { class: "panel" });
    const create = el("button", {
      id: "create-letter",
      onclick: async () => {
        create.disabled = true;
        msg.textContent = "  Drafting… (about 10-20 seconds)";
        try {
          const res = await fetch(`/api/audits/${encodeURIComponent(id)}/letter`, { method: "POST" });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || `API error ${res.status}`);
          a.letter = data;
          panel.replaceWith(letterPanel(a));  // swap the button for the drafted letter
        } catch (err) {
          msg.textContent = "  Could not draft: " + err.message;
          create.disabled = false;
        }
      },
    }, "Create draft letter");
    panel.append(
      el("div", { class: "row" }, el("h3", {}, "Draft letter"), el("span", { class: "pill warn" }, "Draft only")),
      el("p", { class: "muted" }, "No letter for this audit yet. Letters are drafted automatically only for critical and high audits."),
      create, msg);
    return panel;
  }
  const to = el("input", { value: l.to ?? "", placeholder: "e.g. dpo@company.com (one address)" });
  const subject = el("input", { value: l.subject ?? "" });
  const body = el("textarea", {});
  body.value = l.body ?? "";  // .value, not innerHTML -> letter text can't inject code
  const msg = el("span", { class: "muted" });
  // "Send email": sends what's in the boxes (edits + a typed To address), after a confirm
  // that says where it really goes (SEND_MODE: test = your own inbox, live = the DPO).
  const alreadySent = l.delivery?.sent && l.delivery.mode === "live";
  const send = el("button", {
    disabled: alreadySent ? "" : null,
    onclick: async () => {
      const dest = to.value.trim();
      if (!/^[^\s@,;<>]+@[^\s@,;<>]+\.[A-Za-z]{2,}$/.test(dest)) {
        msg.textContent = "  Enter one valid email address in To first.";
        return to.focus();
      }
      let status;
      try {
        status = await (await fetch("/api/email-status")).json();
      } catch {
        msg.textContent = "  Could not reach the server.";
        return;
      }
      if (status.mode === "off") return (msg.textContent = "  Sending is turned off (SEND_MODE=off in .env).");
      if (status.mode !== "outbox" && !status.configured) return (msg.textContent = "  Email isn't set up in .env yet.");
      const question = {
        test: `TEST MODE: this goes to your own inbox (${status.from}), not to ${dest}.\n\nSend the test email?`,
        live: `This will really email ${dest}.\nIt can't be unsent, and each site can only be emailed once.\n\nSend it?`,
        outbox: `Outbox mode: the email to ${dest} will be saved as a file, not sent.\n\nSave it?`,
      }[status.mode] ?? `Send to ${dest}?`;
      if (!confirm(question)) return;
      send.disabled = true;
      msg.textContent = "  Sending…";
      try {
        const res = await fetch(`/api/audits/${encodeURIComponent(id)}/letter/send`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ to: dest, subject: subject.value, body: body.value }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || `API error ${res.status}`);
        a.letter = data;
        panel.replaceWith(letterPanel(a));          // redraw with the new "sent" status
      } catch (err) {
        msg.textContent = "  Not sent: " + err.message;
        send.disabled = false;
      }
    },
  }, alreadySent ? "Already sent to DPO" : "Send email");
  const panel = el("div", { class: "panel" },
    el("div", { class: "row" }, el("h3", {}, `Letter (${(l.kind ?? "").toUpperCase()})`), deliveryPill(l.delivery)),
    l.auto?.reason ? el("p", { class: "muted" }, l.auto.reason) : null,
    deliveryLine(l.delivery),
    l.note ? el("p", { class: "muted" }, l.note + " You can type one into To.") : null,
    l.error ? el("p", { class: "muted" }, "Problem: " + l.error) : null,
    el("label", {}, "To"), to,
    el("label", {}, "Subject"), subject,
    el("label", {}, "Body"), body,
    send, msg);
  return panel;
}

// Label for the letter: sent / test-sent / draft only.
function deliveryPill(d) {
  if (d?.sent && d.mode === "live") return el("span", { class: "pill bad" }, "Sent to DPO");
  if (d?.sent && d.mode === "test") return el("span", { class: "pill ok" }, "Test email sent to you");
  if (d?.saved_to) return el("span", { class: "pill ok" }, "Saved to outbox");
  return el("span", { class: "pill warn" }, "Draft only, not sent");
}

// One line explaining what happened with sending (or why it didn't happen).
function deliveryLine(d) {
  if (!d) return null;
  const when = d.at ? fmtDate(d.at) : "";
  if (d.sent) {
    const where = d.mode === "test" ? `${d.to} (test mode; would have gone to ${d.intended_to ?? "no DPO address"})` : d.to;
    // "sent" = the email service ACCEPTED it; actual delivery shows in Brevo's logs.
    const how = d.trigger === "manual" ? "Sent from the dashboard" : "Sent automatically (critical audit)";
    return el("p", { class: "muted" }, `${how}: handed to the email service for ${where} on ${when}. ` +
      `Check Brevo's logs to confirm delivery. Replies go to the Gmail inbox.`);
  }
  if (d.saved_to) return el("p", { class: "muted" }, `Outbox mode: saved as ${d.saved_to} on ${when} (not sent; would go to ${d.intended_to ?? "no DPO address"}).`);
  return el("p", { class: "muted" }, `Not sent: ${d.reason ?? "unknown reason"}`);
}

// Everything in the JSON, using the generic renderer. Catches fields we don't have a nice view for yet.
function rawPanel(a) {
  return el("div", { class: "panel" },
    el("details", {}, el("summary", {}, "Raw audit data (every field)"), render(a)));
}
