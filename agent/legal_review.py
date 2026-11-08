"""
Legal review (LLM job 4): give an LLM the evidence we collected plus the
site's privacy and cookie policies, and ask it to spot likely breaches of
UK data protection law. Its findings are merged into audit["findings"]
(tagged "source": "ai") so the UI and the letter use them.

The risk with this step is the model inventing things, so:
  - It never sees raw traffic. It gets a short numbered evidence list
    (E1, E2, ...) built by plain code from what we actually observed.
  - Every finding must cite evidence IDs. Findings with no valid ID are
    dropped. A "policy_quote" is kept only if that exact text is really
    in the policy.
  - Severity must be high / medium / low, anything else is dropped.
  - We record how many findings were dropped, so it's visible.
"""
import re
from datetime import datetime

from . import llm
from .policy import select_relevant
from .trackers import TRACKER_COMPANIES
from .capture import base_domain

MAX_POLICY_CHARS = 60000      # privacy policy sent in full up to this (~15k tokens), so the Art. 13 check sees all of it
MIN_FULL_POLICY_CHARS = 3000  # shorter = a hub / links page or a page that didn't render, not a full Art. 13
                              # policy (sky.com's privacy hub: 1,412 chars, mostly menu). Present items still
                              # count; nothing is called "missing".
MAX_COOKIE_CHARS = 20000      # cookie policy, after keeping the relevant parts (~5k tokens)
MAX_FINDINGS = 8              # keep the report focused
SEVERITIES = ("high", "medium", "low")   # what the AI may answer; "critical" is only ever set by regrade()
STRONG_CATEGORIES = {"Advertising", "Session replay"}
_CATEGORY_RANK = {"Advertising": 0, "Session replay": 1, "Analytics": 2, "Monitoring": 3, "Tag manager": 4}  # evidence that can make a finding critical
_CATEGORY_BY_SHOWN_NAME = {shown: cat for shown, cat in TRACKER_COMPANIES.values()}  # "Criteo" -> "Advertising"

SYSTEM_PROMPT = """You are a UK data protection and privacy compliance analyst. You review evidence \
from an automated, passive browser audit of a website and decide whether the data collection it \
shows is lawful, given the site's own privacy and cookie policies and UK law.

What happened in the audit: a fresh browser (no prior cookies) opened the site, recorded every \
network request and cookie, then clicked the cookie banner's reject option (if one could be found \
and clicked), browsed a few pages and scrolled them, and recorded everything again.

Law to apply (UK only):
- PECR reg. 6: storing or reading information on a user's device (cookies, local storage, \
pixels/scripts that read identifiers) needs clear information and prior consent, unless strictly \
necessary for the service the user asked for. Tracking that starts before the user has answered \
the banner, or continues after they rejected, is the core issue.
- The Data (Use and Access) Act 2025 added limited exceptions to PECR consent, for example for \
some analytics/statistical purposes and site functionality, typically only where the user gets \
clear information and a simple way to object. These exceptions do NOT cover advertising or \
cross-site profiling. If analytics continued after the user rejected, the exception may not apply \
because they objected; say this carefully, as "may".
- UK GDPR: Art. 4(11) and Art. 7 (valid consent: freely given, specific, informed, unambiguous; \
withdrawing must be as easy as giving), Art. 5(1)(a) (lawful, fair, transparent), Art. 6 (lawful \
basis), Art. 13(1)(e)-(f) (tell people the recipients or categories of recipients, and \
international transfers), Art. 21 (right to object), Art. 44 (transfers outside the UK).
- ICO guidance: rejecting must be as easy as accepting; no non-essential cookies before consent; \
"consent or pay" models are only acceptable if they are fair (e.g. reasonable price, clear choice).
- A site doing something its OWN policy says it doesn't do (or only does with consent) is a \
transparency and fairness problem even where the underlying law is uncertain.

Severity tiers (use exactly one):
- "high": clear evidence of tracking or device storage for advertising, profiling or session \
replay without consent (before the banner was answered or after rejecting), or a direct \
contradiction of a promise in the site's own policy.
- "medium": a likely issue where an exemption or innocent explanation is plausible (e.g. \
analytics after rejecting), or a significant transparency gap.
- "low": best-practice or transparency concerns with limited impact.

Rules:
- Use ONLY the evidence list and the policy text provided. Do not assume anything not shown. You \
cannot see request contents beyond the URLs listed.
- Every finding must cite at least one evidence ID (e.g. "E4") in "evidence".
- If you say the policy promises or omits something, put the exact sentence in "policy_quote", \
copied word for word from the policy text. If you can't quote it, use null.
- Only name companies that appear in the evidence or the policy text.
- "Not found" for a policy means our crawler could not find it, NOT that the site has none. A missing policy can be at most "low", and only if there is also tracking evidence.
- When unsure, choose the LOWER severity and say why. Do not overstate: this may be used in a \
complaint letter, and a wrong accusation is worse than a missed one.
- The "Automated check" items are already reported. Do not repeat them. Only add a finding that \
raises a different legal point (for example, a contradiction with a specific policy statement).
- At most %d findings. If nothing is wrong, return an empty list.
- This is an automated assessment, not legal advice.

Privacy policy checklist (UK GDPR Art. 13): for each item below, look through the PRIVACY POLICY TEXT (and the cookie policy) and answer "present" with a short exact quote (under 200 characters, copied word for word) that shows it, or "missing" only if the text really does not cover it anywhere. If no policy text was provided, set "policy_checklist" to null. Items:
- controller_identity: who the organisation responsible for the data is
- purposes: what personal data is used for
- lawful_basis: the legal basis (consent, contract, legitimate interests, legal obligation...)
- recipients: who data is shared with, by name or by category
- retention: how long data is kept, or how that is decided
- rights: the user's rights (access, erasure, objection, etc.)
- withdraw_consent: how to withdraw consent / change cookie choices
- complain_to_regulator: the right to complain to the ICO or another supervisory authority

Respond with JSON only, exactly this shape:
{
  "findings": [
    {
      "severity": "high" | "medium" | "low",
      "title": "short headline, under 90 characters",
      "detail": "what happened, in plain English, 1-2 sentences",
      "law": "the specific provision(s), e.g. PECR reg. 6",
      "evidence": ["E1", "E3"],
      "policy_quote": "exact sentence from the policy, or null",
      "reasoning": "why this is a problem and why you chose this severity, 1-3 sentences"
    }
  ],
  "summary": "2-4 sentences: overall view of this site's compliance and the main reasons",
  "policy_checklist": {
    "controller_identity": {"status": "present" | "missing", "quote": "exact short quote, or null"},
    "purposes": {...same shape...}, "lawful_basis": {...}, "recipients": {...}, "retention": {...},
    "rights": {...}, "withdraw_consent": {...}, "complain_to_regulator": {...}
  }
}""" % MAX_FINDINGS


def _days_until(expires, started_at):
    """Cookie lifetime in whole days, or None for session cookies."""
    try:
        if expires is None or expires < 0:
            return None
        start = datetime.fromisoformat(started_at).timestamp()
        return max(0, round((expires - start) / 86400))
    except (TypeError, ValueError):
        return None


def _short(url, n=160):
    return url if len(url) <= n else url[:n] + "..."


def build_evidence(audit):
    """Plain-code summary of what we observed, as numbered lines: ["E1: ...", "E2: ...", ...]."""
    items = []
    add = lambda text: items.append(f"E{len(items) + 1}: {text}")

    c = audit.get("consent") or {}
    add(f"Cookie banner found: {c.get('banner_found')}. Reject clicked successfully: {c.get('rejected')}. "
        f"Method: {c.get('method')}. Buttons clicked: {', '.join(c.get('clicks') or []) or 'none'}.")
    fp = {}
    for e in audit.get("fingerprinting") or []:   # one line per script domain that fingerprinted
        g = fp.setdefault(base_domain(e["script"]), (set(), set()))
        g[0].add(e["technique"]); g[1].add(e["phase"])
    for d, (techniques, phases) in sorted(fp.items()):
        add(f"Fingerprinting by scripts from {d}: {', '.join(sorted(techniques))}; phases: {', '.join(sorted(phases))}.")
    for l in audit.get("id_leaks") or []:          # agent/crosssite.py: our per-browser IDs sent elsewhere
        if l.get("company") and l.get("confidence") == "confirmed":
            add(f"ID sent to another company: the value of cookie {l['cookie']} (unique to this browser) was sent to "
                f"{l['to']} ({l['company']}, {l.get('category')}) in the request {l['in']}, "
                f"{'after reject' if l['phase'] == 'after_reject' else 'before the banner was answered'}.")
    for s in audit.get("id_syncs") or []:
        add(f"{s['type']} request to {s['to']} "
            f"{'after reject' if s['phase'] == 'after_reject' else 'before the banner was answered'}"
            f"{'; shared ID systems: ' + ', '.join(s['sources']) if s.get('sources') else ''}.")
    if c.get("preticked"):
        add(f"Non-essential cookie toggles already ON before any choice: {'; '.join(c['preticked'])}.")

    # One line per tracker company: counts per phase, domains, a couple of example URLs.
    companies = {}
    for r in audit.get("requests", []):
        t = r.get("tracker") or {}
        if not t.get("is_tracker"):
            continue
        g = companies.setdefault(t["company"], {"category": t.get("category"), "before_consent": 0,
                                               "after_reject": 0, "domains": set(), "examples": []})
        if _CATEGORY_RANK.get(t.get("category"), 9) < _CATEGORY_RANK.get(g["category"], 9):
            g["category"] = t.get("category")      # mixed company (Google): its most serious category
        g[r.get("phase", "before_consent")] = g.get(r.get("phase", "before_consent"), 0) + 1
        g["domains"].add(r.get("domain"))
        if len(g["examples"]) < 2 and r.get("phase") == "after_reject":
            g["examples"].append(_short(r.get("url", "")))
    for name, g in sorted(companies.items()):
        line = (f"Tracker {name} ({g['category']}): {g['before_consent']} requests before consent, "
                f"{g['after_reject']} after reject, to {', '.join(sorted(g['domains']))}.")
        if g["examples"]:
            line += f" Example after-reject requests: {' | '.join(g['examples'])}"
        add(line)

    started = audit.get("started_at")
    cookies = audit.get("cookies") or {}
    before_names = {k.get("name") for k in cookies.get("before_consent", [])}
    for phase, label in (("before_consent", "before the banner was answered"), ("after_reject", "after reject")):
        for k in cookies.get(phase, []):
            if not k.get("tracker_company"):
                continue
            if k.get("value_kind") in ("empty", "placeholder"):
                # Worded differently on purpose: strong_evidence_ids() must NOT count these.
                add(f"Empty cookie {k.get('name')} ({k['tracker_company']}) present {label}: it holds no value, "
                    f"so it stores nothing about the user.")
                continue
            days = _days_until(k.get("expires"), started)
            life = "session cookie" if days is None else f"expires in {days} days"
            new = " (NEW, not present before)" if phase == "after_reject" and k.get("name") not in before_names else ""
            held = "; holds what looks like a unique ID" if k.get("value_kind") == "id" else ""
            add(f"Tracking cookie {k.get('name')} from {k['tracker_company']} on {k.get('domain')} present "
                f"{label}{new}; {life}{held}.")

    visited = audit.get("visited_pages") or []
    if visited:
        add(f"Pages browsed and scrolled after reject: {', '.join(visited)}.")

    p = audit.get("policy") or {}
    add(f"Privacy policy: {p.get('url') or 'not found'}. Companies it names: "
        f"{', '.join(p.get('companies_named') or []) or 'none extracted'}. Contact email found: {p.get('dpo_contact')}.")
    add(f"Cookie policy: {p.get('cookie_policy_url') or 'not found'}"
        f"{' (same document as the privacy policy)' if p.get('cookie_policy_url') and p.get('cookie_policy_url') == p.get('url') else ''}.")

    for f in audit.get("findings", []):
        add(f"Automated check ({f.get('severity')}): {f.get('title')}. {f.get('detail')}")
    return items


def build_prompt(audit, texts):
    """The user message: evidence list + the two policy texts (trimmed to the relevant parts)."""
    privacy = select_relevant(texts.get("privacy") or "", MAX_POLICY_CHARS)
    cookie_raw = texts.get("cookie") or ""
    if cookie_raw and cookie_raw == texts.get("privacy"):
        cookie = "(Same document as the privacy policy above.)"
    else:
        cookie = select_relevant(cookie_raw, MAX_COOKIE_CHARS) or "(Not found.)"
    return (
        f"SITE: {audit.get('url')}\n\n"
        "EVIDENCE (cite by ID):\n" + "\n".join(build_evidence(audit)) + "\n\n"
        "PRIVACY POLICY TEXT:\n<<<\n" + (privacy or "(Not found.)") + "\n>>>\n\n"
        "COOKIE POLICY TEXT:\n<<<\n" + cookie + "\n>>>"
    )


def _norm(text):
    """Lowercase + collapse whitespace, so a quote still matches across line breaks."""
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


MIN_REQUESTS_FOR_CRITICAL = 3   # a single stray request isn't enough to accuse anyone automatically
# Tag LOADERS: they deliver other scripts but collect nothing themselves. Requests ONLY to these
# don't prove ad tracking (sky.com: 4 hits to googletagmanager.com were rated critical).
# Any real tracking they trigger shows up separately (google-analytics.com, doubleclick.net...).
TAG_LOADER_DOMAINS = {"googletagmanager.com", "adobedtm.com", "tealiumiq.com"}


def strong_evidence_ids(evidence_lines):
    """IDs of evidence lines that can back a "critical" finding: ADVERTISING or SESSION REPLAY
    trackers with SUBSTANTIAL evidence. Parses the lines build_evidence() writes, e.g.
      "E4: Tracker Criteo (Advertising): 2 requests before consent, 5 after reject, to ..."
      "E9: Tracking cookie _fbp from Facebook on ..."
    Counts as strong: any tracking cookie (actual storage on the device), any request AFTER
    Reject all, or at least MIN_REQUESTS_FOR_CRITICAL requests. One request before consent
    with nothing else (iana.org: one hit to an ad-fraud check) is not enough."""
    strong = set()
    for line in evidence_lines:
        m = re.match(r"(E\d+): Tracker .+? \(([^)]+)\): (\d+) requests before consent, (\d+) after reject, "
                     r"to (.+?)\.(?:\s|$)", line)   # domain list ends at ". " or the end
        if m and m.group(2) in STRONG_CATEGORIES:
            before, after = int(m.group(3)), int(m.group(4))
            domains = {d.strip() for d in m.group(5).split(",")}
            if domains <= TAG_LOADER_DOMAINS:
                continue                       # only a tag loader: not evidence of ad tracking on its own
            if after > 0 or before + after >= MIN_REQUESTS_FOR_CRITICAL:
                strong.add(m.group(1))
            continue
        m = re.match(r"(E\d+): Tracking cookie \S+ from (.+?) on ", line)
        if m and _CATEGORY_BY_SHOWN_NAME.get(m.group(2)) in STRONG_CATEGORIES:
            strong.add(m.group(1))
    return strong


def regrade(severity, evidence_ids, strong_ids):
    """The safeguard on the AI's tiers. Returns (new severity, note explaining any change).
    AI "high" + cites advertising/session-replay evidence -> "critical" (the ones to act on).
    AI "high" without that evidence -> "medium": analytics may be exempt, so "high" overstates it."""
    if severity != "high":
        return severity, None
    if set(evidence_ids) & strong_ids:
        return "critical", "Raised to critical: rated high and backed by advertising or session-replay evidence."
    return "medium", ("Lowered from high: no substantial advertising or session-replay evidence cited "
                      "(a tracking cookie, activity after reject, or 3+ requests to an actual tracking domain; "
                      "a tag loader like Google Tag Manager alone doesn't count), "
                      "so an exemption or innocent explanation is plausible.")


def validate(raw, n_evidence, policy_texts, strong_ids=frozenset()):
    """Keep only well-formed, evidence-backed findings, then apply regrade().
    Returns (findings, dropped_count)."""
    valid_ids = {f"E{i}" for i in range(1, n_evidence + 1)}
    haystack = _norm(" ".join(policy_texts))
    kept, dropped = [], 0
    for f in (raw or [])[:MAX_FINDINGS]:
        if not isinstance(f, dict):
            dropped += 1
            continue
        severity = str(f.get("severity", "")).lower().strip()
        evidence = [e for e in (f.get("evidence") or []) if isinstance(e, str) and e.strip().upper() in valid_ids]
        title = str(f.get("title") or "").strip()
        if severity not in SEVERITIES or not evidence or not title:
            dropped += 1                      # no tier, no evidence, or no headline -> not trustworthy
            continue
        quote = f.get("policy_quote")
        if not (isinstance(quote, str) and len(quote) > 15 and _norm(quote) in haystack):
            quote = None                      # not really in the policy -> don't repeat it
        ids = sorted({e.strip().upper() for e in evidence}, key=lambda e: int(e[1:]))
        final, note = regrade(severity, ids, strong_ids)
        kept.append({
            "severity": final,
            "ai_severity": severity,          # what the AI said, before our safeguard
            "severity_note": note,            # why we changed it (None if unchanged)
            "title": title[:120],
            "detail": str(f.get("detail") or "").strip()[:600],
            "law": str(f.get("law") or "").strip()[:200],
            "source": "ai",
            "evidence": ids,
            "policy_quote": quote,
            "reasoning": str(f.get("reasoning") or "").strip()[:600],
        })
    return kept, dropped


# UK GDPR Art. 13 items: (label shown to people, keywords that suggest the policy DOES cover it).
# The keywords are a safety net: if the AI says "missing" but these words appear in the policy,
# we mark it "unclear" instead of accusing the site.
CHECKLIST = {
    "controller_identity": ("Who is responsible (the controller)",
                            r"controller|registered (office|address|in)|company number|operated by|\bltd\b|limited|\bplc\b"),
    "purposes": ("What the data is used for", r"purpose|we use (your|this|personal)|in order to"),
    "lawful_basis": ("The legal basis for using it",
                     r"lawful basis|legal basis|legitimate interest|basis for processing|article 6|legal obligation|"
                     r"perform(ance of)? (a|the|our|your) contract"),
    "recipients": ("Who it is shared with", r"third[- ]part|share|recipient|service provider|processor|partner|disclos"),
    "retention": ("How long it is kept", r"retain|retention|keep (your|personal|this|it)|how long|stored for|delete"),
    "rights": ("Your rights (access, erasure, objection...)",
               r"right to (access|erasure|rectif|object|restrict|portab|be forgotten)|your rights|subject access"),
    "withdraw_consent": ("How to withdraw consent",
                         r"withdraw|change your (mind|preferences|settings|choices)|opt[- ]out|switch (these|them|it) off"),
    "complain_to_regulator": ("Right to complain to the ICO",
                              r"information commissioner|\bico\b|ico\.org\.uk|supervisory authority|data protection authority"),
}


def check_policy(raw, texts, evidence):
    """Turn the AI's Art. 13 checklist into {item: {"label", "status", "quote"}} plus maybe one finding.
    status: present (quote verified) / missing (AI says so AND no keywords anywhere) /
            unclear (anything doubtful) / not_checked (no policy, or too long to have been sent in full)."""
    privacy = texts.get("privacy") or ""
    both = _norm(privacy + " " + (texts.get("cookie") or ""))
    whole = bool(privacy) and len(privacy) <= MAX_POLICY_CHARS   # did the AI see ALL of it?
    full_policy = len(privacy) >= MIN_FULL_POLICY_CHARS          # long enough to be the real policy?
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    for key, (label, keywords) in CHECKLIST.items():
        item = raw.get(key) if isinstance(raw.get(key), dict) else {}
        status = str(item.get("status") or "").lower()
        quote = item.get("quote") if isinstance(item.get("quote"), str) else None
        if not whole:
            result = "not_checked"
        elif status == "present" and quote and _norm(quote) in both:
            result = "present"
        elif status == "missing" and full_policy and not re.search(keywords, both, re.IGNORECASE):
            result, quote = "missing", None
        else:
            result, quote = "unclear", None            # unverified quote, or "missing" but keywords found
        out[key] = {"label": label, "status": result, "quote": quote if result == "present" else None}

    missing = [v["label"] for v in out.values() if v["status"] == "missing"]
    finding = None
    if missing:
        policy_ids = [e.split(":")[0] for e in evidence if re.match(r"E\d+: Privacy policy:", e)]
        finding = {
            "severity": "medium" if len(missing) >= 2 else "low",
            "ai_severity": None, "severity_note": None,
            "title": f"Privacy policy is missing {len(missing)} required item{'s' if len(missing) > 1 else ''}",
            "detail": "Not covered anywhere in the policy we read: " + "; ".join(missing) + ".",
            "law": "UK GDPR Art. 13(1)-(2) (information that must be given to people)",
            "source": "ai",
            "evidence": policy_ids[:1],
            "policy_quote": None,
            "reasoning": "Checked against the Art. 13 list. Each item marked missing was reported missing by the "
                         "AI review AND has no matching keywords anywhere in the full policy text.",
        }
    return out, finding


def review(audit, texts, cost=None):
    """Run the AI legal review. Returns (ai_findings, ai_review_info).
    Never raises: if the model fails, the audit still saves with an error noted."""
    info = {"model": llm.REVIEW_MODEL, "summary": None, "findings_kept": 0, "findings_dropped": 0}
    evidence = build_evidence(audit)
    try:
        raw = llm.ask_review(build_prompt(audit, texts), system=SYSTEM_PROMPT, cost=cost) or {}
        findings, dropped = validate(raw.get("findings"), len(evidence),
                                     [texts.get("privacy"), texts.get("cookie")],
                                     strong_ids=strong_evidence_ids(evidence))
        info.update(summary=str(raw.get("summary") or "").strip()[:1200] or None,
                    findings_kept=len(findings), findings_dropped=dropped)
        info["evidence"] = evidence  # saved so anyone can check what E1, E2... referred to
        checklist, policy_finding = check_policy(raw.get("policy_checklist"), texts, evidence)
        info["policy_checklist"] = checklist
        if policy_finding:
            findings.append(policy_finding)
            info["findings_kept"] = len(findings)
        return findings, info
    except Exception as e:
        info["error"] = f"{type(e).__name__}: {e}"[:300]
        return [], info
