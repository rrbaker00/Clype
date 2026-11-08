# Clype: how the agent works, start to finish

*Briefing for building the HackTheBurgh 2026 presentation. Written 8 Nov 2026. Figures come from the live dashboard at the time of writing.*

---

## 1. One-line pitch

**Clype is a browser agent that clicks "Reject all" on a website's cookie banner, then records what the site still sends anyway, compares that with what its privacy policy promises, has an AI legal reviewer check it against UK law, and drafts (or sends) a complaint letter, all with evidence attached.**

It runs three ways: as a **dashboard** (audit one site or a file of 300), as a **Firefox extension** (audits each site you visit while you browse), and as a **cross-site check** (proves a tracker recognises you across different sites).

## 2. The problem

- Almost every UK website shows a cookie banner. Most people click "Reject all" and assume that's the end of it.
- Often it isn't: trackers keep loading, cookies get set before you choose, IDs are passed to ad companies, and the privacy policy doesn't name who receives your data.
- Checking this by hand needs developer tools, legal knowledge and hours per site. Regulators (the ICO) can't check every site; individuals can't either.

## 3. What Clype does about it

For any website, Clype produces:

1. **Evidence**: every network request and cookie, split into *before you chose* and *after you rejected*, matched to the company behind it.
2. **Findings**: plain-English problems with a severity (low / medium / high / critical) and the law each one relates to (UK, with the EU equivalent).
3. **An AI legal review** that must cite the numbered evidence for every claim, and whose quotes from the policy are checked word for word.
4. **A complaint letter** to the company's data protection contact, drafted automatically for serious cases and emailed for critical ones (controlled by a safety switch).
5. **Cost and time** for every audit (tokens, model, seconds), shown on the dashboard.

## 4. The audit, step by step

This is what happens when one site is audited (`agent/run_audit.py`). Every step is wrapped so that if it fails, the error is recorded and the audit carries on.

```
URL ─▶ queue ─▶ headless Firefox ─▶ open site ─▶ banner: find Accept (never click) + click Reject
     ─▶ browse 3 pages ─▶ read privacy + cookie policy ─▶ fresh-browser ID check
     ─▶ plain-code checks ─▶ AI legal review (+ safeguard) ─▶ EU law ─▶ letter (+ email) ─▶ saved report
```

### Step 1. Queue
- A URL comes from the dashboard box, an uploaded file (up to 300 URLs), or the Firefox extension.
- It is checked first: local/private addresses are refused, duplicates are dropped by *site* (bbc.co.uk = www.bbc.co.uk), and sites already audited can be skipped (tick box).
- **4 audits run in parallel** (configurable up to 8). Sites you're browsing in the extension take a **fast lane** ahead of waiting batch jobs.

### Step 2. A fresh browser
- A brand-new **headless Firefox** (no cookies, no history) for every audit. Firefox because the extension is for Firefox users, so audits show what they experience.
- Before the site's own code runs, Clype installs **fingerprinting detectors** (canvas, WebGL GPU model, audio, font probing) that record which script used them.
- **No disguise**: a site that blocks automated browsers is reported as "blocked", never sneaked past. Blocked sites cost no AI calls.

### Step 3. Open the site and watch
- Loads the homepage, waits like a visitor, and records **every request** and **every cookie**, all tagged *before consent*.

### Step 4. The cookie banner
- **Looks for the Accept button but never clicks it**: only to measure whether rejecting is harder than accepting.
- **Checks for pre-ticked toggles** (marketing/analytics switched on by default).
- **Finds and clicks the reject option** using reject-type wording ("Reject all", "Necessary only", "Disable all"…) and only inside a cookie banner, including consent iframes and modern web-component banners (shadow DOM).
- Never clicks "Reject & Pay"/"subscribe" options: those are recorded as **pay-or-consent**.
- If nothing matches, it digs into "Manage preferences" and switches categories off, and as a last resort asks a small AI model to pick the reject button from the visible labels (the AI can only choose among buttons Clype already found).

### Step 5. Browse after rejecting
- Everything from now on is tagged *after reject*. Clype visits up to 3 more pages (one per section, skipping login pages) and scrolls like a person, because many trackers only fire on scroll or navigation.

### Step 6. Read the policies
- Finds the **privacy policy** and **cookie policy** by scoring links (follows "hub" pages one level deeper, reads PDFs too).
- A small AI model extracts the **companies the policy names** and the **data protection contact email** (only emails that really appear in the text are kept).

### Step 7. Fresh-browser ID check
- Loads the homepage once more in a *second* fresh browser. Cookie values that differ between the two browsers are **per-person IDs**; values that match are the same for everyone. (Standard method from privacy research, e.g. OpenWPM.)

### Step 8. Plain-code checks (no AI)
- **Who is it?** Each request/cookie is matched to a company using DuckDuckGo's Tracker Radar data plus a curated category list (Advertising, Session replay, Analytics, Monitoring, Tag manager). Big companies only count on their *tracking* domains (Google Fonts or AWS hosting don't count).
- **What does the cookie hold?** Empty / placeholder / unique ID / plain value. Empty cookies are never counted as tracking.
- **Findings** created by code:
  - Tracking cookies set **before you could choose**
  - Companies still receiving data **after you rejected** (severity by category)
  - **Your ID was sent to** another company (a per-person ID found in their request, raw or encoded/hashed)
  - **Ad companies matched IDs** (cookie syncing: Google cookie matching, Prebid shared IDs)
  - **Fingerprinting** by named scripts
  - **Rejecting took N clicks, accepting takes 1**
  - **Categories switched on by default**
  - **Rejecting requires paying**
  - **Tracking companies not named in the privacy policy**
  - Google Consent Mode "denied" pings explained (sent without cookies, still send page/device data)

### Step 9. AI legal review (the "Wordsmith" part)
- One AI call (`gpt-5.6-luna`) gets a **numbered evidence list** (E1, E2, …) built by code, plus the full privacy and cookie policies.
- Its instructions cover UK law (PECR reg. 6, the Data (Use and Access) Act 2025 exemptions, UK GDPR Arts 4, 5, 6, 7, 13, ICO guidance, CMA choice-architecture guidance).
- **It must cite evidence IDs for every finding**; findings citing nothing are dropped; any quote from the policy is checked word for word against the real text.
- It also fills an **Art. 13 privacy-policy checklist** (8 items: who you are, purposes, legal basis, recipients, retention, rights, withdrawing consent, complaining to the ICO). An item is only "present" with a verified quote, and only "missing" if no keywords appear anywhere in a full-length policy.
- **Safeguard on severity**: the AI can say "high", but code decides what becomes **critical**: only advertising or session-replay tracking with strong evidence (a tracking cookie, activity after reject, or 3+ requests to a real tracking domain; tag loaders like Google Tag Manager alone don't count). Weak "high" claims are lowered to medium, with the reason shown.

### Step 10. EU law
- Every finding also gets its EU equivalent (ePrivacy Directive Art. 5(3), EU GDPR article, EDPB guidance), generated by code, never invented.

### Step 11. Letter and email
- **High or critical** audits get an automatic complaint letter (`gpt-5.4`) written only from the verified findings.
- **Critical** letters are emailed, controlled by `SEND_MODE`: `off`, `outbox` (save .eml), `test` (to our own inbox, the default) or `live` (to the real DPO, max 1 per site and 5 per day). Audits started by the browser extension **never** send.
- Any report has a "Create draft letter" and "Send email" button for manual use.

### Step 12. Save
- The whole audit is saved as one JSON file: requests, cookies, consent result, policy, findings (each tagged *observed* or *AI*), AI review, letter, errors, **tokens, model and time**.

### Typical audit
- **~1 minute**, **2-4 AI calls** (hard cap of 6), about **13k tokens in / 2.5k out**.
- So far: **74 audits, 196 AI calls, about $0.79 in total** (roughly 1p per audit).

## 5. The dashboard

- **Run an audit**: one URL or a file of up to 300; "skip sites already audited"; live queue with progress bar (collapsible), cancel button.
- **Totals**: sites audited, trackers found, stopped by Reject all, still tracking after Reject all, **critical audits**.
- **AI usage panel**: calls, tokens, estimated spend vs budget, per model.
- **Followed across sites**: which companies appear on the most audited sites, plus the **cross-site proof** button.
- **Critical** and **Severe** sections, then all other audits (one card per site, newest audit).
- **Audit page**: red critical banner, timeline of earlier runs of the same site, findings (with AI chip, quotes, reasoning, UK + EU law), banner details (accept vs reject clicks, pre-ticked toggles), policy checklist, cookies (what each holds), fingerprinting, IDs sent to other companies, "Your browser" (from the extension), every request, and the letter with Send.

## 6. Proving cross-site tracking

- Seeing Google on 50 sites only shows *presence*. Proof means the **same ID for your browser** reaching the same company from **different sites**.
- The check opens 2-5 audited sites in **one** browser (rejecting each banner) and looks for that.
- Example found: **Dotmetrics received the same user ID from bbc.co.uk (after "Reject additional cookies") and independent.co.uk**. Currently on the dashboard: Microsoft received the same ID from intertek.com and sse.com.
- **Control experiment**: with Firefox's Total Cookie Protection switched on, the BBC/Independent link **disappears**. That proves the link comes from a cross-site third-party cookie, which is exactly what Firefox blocks and Chrome (still the majority browser) allows by default.

## 7. The Firefox extension

- Sits in the toolbar. When you open a **new site**:
  1. Asks the Clype server to audit it (fast lane; reuses a report from the last 7 days; skips banking, email, NHS, gov.uk, search engines, local pages).
  2. **Clicks reject on the banner in your own tab** (same rules as the agent: reject-only, never Accept, never "Reject & Pay").
  3. **Records what your real browser sends** before and after that click, and sends it to the local server, which runs the same plain-code checks (no AI cost). Shown as **"Your browser"**.
- **Badge** on the icon: `…` auditing, `!` critical, `H` high, `M` medium, `✓` fine, `?` blocked.
- **Popup**: this site's result, what your browser did, every report, auto-audit and reject-in-my-tab switches, "Skip this site", "Reset this site's cookies" (clears the site's cookies and re-audits straight away).
- **Critical**: a red box in the top-left of the page plus a desktop notification.
- Real-browser results differ from the headless audit (e.g. on BBC, real Firefox leaked to 1 company after reject vs 4 headless), which is itself a talking point: browser protections matter, but most users are on Chrome.
- Tested end to end in a real Firefox 159 (remote-controlled, throwaway profile).

## 8. Results so far (live dashboard)

- **71 sites** audited (newest audit per site), mostly large UK companies and retailers. 3 blocked the audit browser.
- The reject option was found and clicked on **59 of 68** sites that loaded.
- **54 sites** still sent data to at least one tracking company after "Reject all" (this includes analytics and monitoring, some of which may be exempt).
- Worst finding per site: **28 critical, 15 high, 22 medium**, 3 with none. *(Critical = Clype's rules; worth spot-checking a few before quoting this on a slide.)*
- Most common: **Google on 56 sites** (47 still receiving data after reject, including Analytics and Tag Manager), Microsoft on 16, Facebook on 11.

## 9. Trust: how Clype avoids false accusations

A wrong accusation in a complaint letter is worse than a missed one, so:
- **Two kinds of findings**: plain-code "observed" facts and AI findings, labelled separately.
- **Evidence IDs required** for every AI finding; quotes verified against the policy text.
- **Code, not the AI, decides "critical"**.
- **Wording states what was sent, never "illegal"**: "X still received data after you rejected", "Your ID was sent to Y".
- Exemptions acknowledged: analytics may be exempt (DUAA 2025), monitoring is usually strictly necessary, bot-protection fingerprinting may be security.
- Short "hub" pages aren't treated as the full policy; empty cookies aren't counted; tag loaders aren't treated as ad tracking.
- Bugs found in testing and fixed: Google Analytics counted as advertising (false critical), privacy hub page treated as policy, ad-fraud detection domain counted as tracking.

## 10. The law it checks against

- **PECR regulation 6** (storing or reading anything on your device needs consent), as amended by the **Data (Use and Access) Act 2025** (new narrow exemptions, in force from 5 Feb 2026). ICO guidance: *"You must get consent for any cross-site or cross-device tracking"* and online advertising *"never"* was exempt.
- **UK GDPR**: Art. 4(11) and 7 (valid consent: freely given, as easy to refuse as to give), Art. 5 (fairness/transparency), Art. 6 (lawful basis), Art. 13 (what a privacy policy must tell you, incl. who receives your data).
- **ICO cookie guidance** (no pre-ticked boxes, reject as easy as accept), **CMA** online choice architecture.
- **EU equivalents**: ePrivacy Directive Art. 5(3), EU GDPR, EDPB Guidelines 2/2023 (tracking pixels and links count as "access").

## 11. Hard rules we kept

- **Passive only**: Clype only observes what its own browser receives. No attacks, no bypassing logins, no getting round bot protection.
- **Sending is switched off by default** and rate-limited when live; browsing with the extension never sends.
- **Secrets stay local** (`.env` never committed); your own browsing captures are git-ignored.
- **Cost tracked** for every audit.

## 12. Tech stack

- **Python 3.14**, **Playwright** (headless Firefox; Chromium for the cross-site proof), **FastAPI** + uvicorn.
- **OpenAI**: `gpt-5.6-luna` (banner fallback, policy reading, legal review), `gpt-5.4` (letters). Max 6 calls per audit.
- **Dashboard**: plain HTML/CSS/JavaScript, no framework.
- **Firefox extension**: Manifest V2 (background script, content script, popup).
- **Data**: DuckDuckGo Tracker Radar (CC BY-NC-SA 4.0). **Email**: Brevo SMTP.
- About **5,500 lines** of code across agent, API, dashboard and extension.

## 13. Suggested slide outline

1. **Title**: Clype. "What websites still send after you click Reject all."
2. **The problem**: everyone clicks Reject all; nobody can check what happens next.
3. **What Clype does**: evidence → findings → AI legal review → complaint letter (one diagram).
4. **The agent's journey** (the flow diagram in section 4): fresh browser, never clicks Accept, rejects, browses, reads the policy.
5. **Evidence, not vibes**: before/after split, company matching, ID leaks, fingerprinting.
6. **The AI lawyer, kept honest**: numbered evidence, verified quotes, code decides "critical", Art. 13 checklist.
7. **Proof of cross-site tracking**: same ID from BBC and the Independent; disappears under Firefox's protection.
8. **In your browser**: the Firefox extension (badge, popup, critical alert, rejects for you).
9. **Results**: 71 UK sites, 54 still sending after Reject all, top companies chart.
10. **Cost**: about 1p and 1 minute per audit; tokens and time logged per audit.
11. **Responsible by design**: passive only, no bot evasion, sending switched off by default, careful wording.
12. **What's next**: signed extension, Chrome version, ICO-ready evidence packs, scheduled re-audits.

## 14. Demo script (about 3 minutes)

1. Dashboard: show totals, Critical section, the "Followed across sites" panel.
2. Open a critical audit: red banner → findings with evidence IDs and quotes → cookies before choice → IDs sent to other companies → the drafted letter.
3. Show the timeline (same site audited twice) and AI usage panel (cost per audit).
4. Firefox: open a new site; the banner disappears by itself; badge goes `…` → result; open the popup ("Your browser" section).
5. Cross-site proof result: the same ID reaching one company from two sites.
6. Close on the numbers and "about 1p per audit".

## 15. Known limits (for Q&A)

- Some sites block automated browsers; Clype reports them as blocked rather than evading.
- Server-side tracking (company servers talking to each other) can't be seen from a browser.
- Exemptions (analytics, security) mean some findings are "may need consent", not certain breaches; the wording reflects that.
- Banner detection is phrase-based with an AI fallback; unusual banners can be missed.
- Critical counts depend on Clype's rules and the tracker list; findings are evidence for a human or regulator to judge, not a legal ruling.
