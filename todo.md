# Clype: to-do list

Solo now (partner left), so the **P** / **Y** / **Both** labels are just history. Times are rough.
Tick items with `[x]` as you go.
Deadline: Sunday 8 Nov, around midday. Last 2 hours = no new features.

## 0. Now (5 min)
- [x] **Y** Restore UI work from stash (Severe section + letter button): `git stash pop`.
      `requirements.txt` will conflict, keep the 6-line version. Then commit.
- [x] **Both** Agree who edits `api/main.py` (both of us have touched it).
- [x] **Both** Install deps: `python3 -m pip install -r requirements.txt && python3 -m playwright install chromium`

## 1. Make findings trustworthy (P, about 2.5 h): highest priority
A wrong accusation in front of judges is worse than a missed one.
- [x] `trackers.py`: exclude static/CDN domains that are wrongly counted as trackers:
      `gstatic.com`, `googleapis.com`, `ytimg.com`, `recaptcha.net`, `fbcdn.net`, `twimg.com`,
      `azureedge.net`, `licdn.com` (20 min)
- [x] `trackers.py`: data says `"Amazon.com"` but allowlist says `"Amazon"`, so Amazon never matches.
      Add Permutive, The Trade Desk, LiveRamp, ID5, Lotame, Teads (15 min)
- [x] `compare.py`: one finding per company tracking after reject (even if the policy names it),
      plus a separate "not named in policy" finding (20 min)
- [x] `compare.py`: alias map: Meta/Facebook, Alphabet/YouTube/Google, X/Twitter,
      TikTok/ByteDance, Amazon Alexa/Amazon (15 min)
- [x] Severity + legal wording: PECR reg. 6 is about cookies/storage, not requests. Some analytics
      may be exempt under the Data (Use and Access) Act 2025. Advertising / tracker cookies after
      reject = high, analytics = medium. Requests = "sent data to X after you said no" (20 min)
- [x] `policy.py:32`: 15,000-char cut can hide named companies, which then get reported as
      "not disclosed". Raise to about 60k or send only paragraphs about third parties/partners/sharing (20 min)
- [x] `policy.py`: phrase `"privacy"` can click the banner's "Privacy settings" instead of the
      policy page. Prefer links whose href contains `privacy` (20 min)
- [x] `policy.py:67`: `info.get("companies_named") or []` in case the LLM returns null (2 min)
- [x] `run_audit.py`: when reject failed, leave `cookies.after_reject` empty
      (Guardian currently shows 7 "after reject" cookies with no reject) (5 min)
- [ ] Run the `policy-checker` agent on a fresh BBC audit

## 1b. Done since: AI legal review + better browsing
- [x] `browse.py`: skip current page / sign-in redirects, spread across sections, scroll each page
- [x] `policy.py`: also find + read the cookie policy (combined policies read once)
- [x] `legal_review.py`: AI legal review, findings merged with `"source": "ai"`, evidence-checked
- [x] Add `OPENAI_API_KEY=...` to `.env` (none on this machine now). Optional `REVIEW_MODEL=<luna id>`
- [ ] Live audit with the real model + run `policy-checker`; read the AI findings for overreach

## 1c. Done since: critical tier + letters + email
- [x] Safeguard: AI "high" -> critical (ads/session-replay evidence) or medium (otherwise)
- [x] `letter.py`: auto-draft for critical/high, "Create draft letter" button for the rest
- [x] `mailer.py`: SMTP sending (Brevo) for critical audits, SEND_MODE off/outbox/test/live, 1 per site, 5/day
- [x] Add Brevo SMTP_USER / SMTP_PASSWORD + FROM_ADDRESS (and SEND_MODE, SENDER_NAME) to `.env`, send one test email
- [ ] Find a site with ad trackers after reject to demo a critical audit end to end

## 1d. Done since: cross-site, cancel, PDF policies, block detection
- [x] Cross-site tracking panel ("Followed across sites"), newest audit per site
- [x] Cancel waiting audits button; up to 300 URLs per file, 4 audits in parallel (AUDIT_WORKERS)
- [x] PDF privacy policies (pypdf); cookie banner buttons must be inside a cookie/consent area
- [x] Bot-protection / HTTP 4xx pages count as "not loaded" (no AI calls, reason shown)
- [x] Licences checked; Tracker Radar credit in data/README.md + readme.md

## 1e. Extra compliance checks (aim: all automated)
- [x] #1 Reject harder than accept (ICO cookie guidance, UK GDPR Art. 7, CMA choice architecture)
- [x] #2 Privacy policy Art. 13 checklist (8 items, quotes verified, keyword safety net)
- [x] #3 Pre-ticked non-essential toggles (banner + "Manage preferences"; consent.preticked → medium finding)
- [x] #4 Fingerprinting detection (agent/fingerprint.py: canvas / WebGL / audio / fonts hooks; per-script finding, bot-protection = low)
- [x] #5 EU GDPR + ePrivacy Art. 5(3) equivalents (agent/eu_law.py → finding.law_eu; filled in on the fly for old audits)
- [x] Cookie contents check: cookies.value_kind (empty / placeholder / id / value); empty + placeholder tracker cookies are not evidence
- [x] AI usage panel on the dashboard (GET /api/usage; cost.by_model; US$ estimate from LLM_PRICES, optional LLM_BUDGET bar)
- [x] Sky fixes: tag loaders (GTM, adobedtm, tealiumiq) alone never back "critical"; policy pages < 3000 chars (hub pages) never produce "missing" checklist items or "not named in policy" findings
- [x] Per-site timeline on the audit page (GET /api/audits/{id}/history) + fixed stray "null" text under the cookie tables
- [x] Dashboard: one card per site (newest audit, "N runs" chip)
- [x] Cross-site A: ID leaks in every audit (agent/crosssite.py; fresh-browser ID check; id_leaks / id_syncs; findings for confirmed IDs to known trackers)
- [x] Cross-site B: "Proof of cross-site tracking" button (linkage pass in one browser; linkage/*.json)
- [x] Firefox extension phase 1 (extension/): auto-audit new sites via the server, badge, popup with all reports, critical in-page box + notification; extension audits never send
- [x] Audits run in headless Firefox by default (AUDIT_BROWSER); agent + extension handle web-component (shadow DOM) banners and "Necessary only"
- [x] Layout: long cookie names/URLs/site names no longer push panels off screen (grid minmax(0,1fr), fixed cookie-table columns, text wraps); checked on every audit at 400/1280/1920 px
- [x] Hung audits: banner search skips hidden/1x1 iframes (ocado.com hung forever); watchdog kills an audit's own browser after AUDIT_TIMEOUT_S (default 6 min) -> failed "Timed out", worker moves on; ✕ cancel kills the browser instantly
- [x] ✕ on running/waiting audits: cancels (running ones stop at the next step, nothing saved), removes from the queue, extension won't re-queue for 15 min
- [x] Batch upload: "Skip sites that already have an audit" tick box; duplicates detected by site; never re-queue sites already waiting
- [x] Critical audits: own top section, red stat tile, CRITICAL cards with top finding, red banner on the audit page
- [x] Extension tested in real Firefox 159 (Marionette, temp profile): reject in tab (BBC, Just Eat web components, sse "Disable all"), Guardian pay-or-consent not clicked, Google skipped, critical alert + notification, hop between sites, reset -> forced fast-lane audit. Fixed: lost first requests, reject race, unload beacons in next site, www/subdomain splitting, server-restart polling, Audit now after failure, PNG notification icon; server: shutdown stops workers (reload no longer hangs), batch job promoted to fast lane / recent report shown
- [x] Extension: Reset this site's cookies forces a fresh audit + new your-browser capture; extension audits use a fast lane in the job queue
- [x] Google Analytics / Clarity / Tag Manager get their own categories (GA isn't advertising; GTM is "Tag manager", low); Consent Mode gcs=G100 pings explained
- [x] Firefox extension phase 2: rejects in your own tab, records your tab's traffic, server analyses it (sessions/, git-ignored); "Your browser" in popup + audit page; Reset this site's cookies
- [ ] #6 Children's Code: flag ad trackers on sites aimed at children (low confidence) (~1 h)

## 2. Pipeline reliability (P, about 1.5 h)
- [x] `run_audit.py:89`: save as `audits/{timestamp}_{domain}.json` (no overwrites, UI sorts by name),
      path based on project root not the current folder (10 min)
- [x] try/except around each step so a failure still saves a partial audit; timeout on `page.goto` (30 min)
- [x] Hard cap on LLM calls per audit (protect the €30 budget) (10 min)
- [x] Check `gpt-5.4` / `gpt-5.4-mini` work on our key (2 min)
- [ ] Don't save cookie `value`s, we don't need them (2 min)
- [x] API `POST /audit`: only http(s), strip to origin, block localhost; rename to `/api/audit` (10 min)

## 3. Letter (feature 7, about 1.2 h). Request-only, draft only, never sent.
- [x] **P** `agent/letter.py`: `llm.ask_strong` drafts a SAR / complaint using ONLY facts in `findings`.
      If `dpo_contact` is null (BBC), use a clear placeholder in "To" (30 min)
- [x] **Y/P** `POST /api/audits/{id}/letter`: draft, save `letter` into the JSON, add tokens to `cost`,
      return the letter (20 min)
- [x] **Y** Wire the "Create draft letter" button: "Drafting…" state, show letter, show errors (20 min)

## 4. UI (Y, about 1 h)
- [x] Run an audit from the page: URL box + file upload (up to 25), live queue, one at a time
- [ ] `pay_or_consent` gets its own pill: "Pay-or-consent wall" (it's a finding in itself) (10 min)
- [ ] Show `visited_pages` on the detail page (10 min)
- [x] Remove or label the 3 fake `.example` test audits before the demo (5 min)

## 5. Demo prep (both, about 2 h, Sunday morning)
- [ ] Pick 2-3 sites with juicy results, list them in `demo_sites.txt`, keep their audit JSON as backup
- [ ] Run `/demo-check`
- [x] README: what it is, how to run, credit DuckDuckGo Tracker Radar (check its licence, needs attribution)
- [x] Show tokens / time / model on screen (Wordsmith judges this)
- [ ] Record a backup video
- [ ] Last 2 hours: no new features

## Stretch (only if everything above is done)
- [x] Auto-audit browser extension (see 1e: Firefox extension phase 1)
- [ ] Fingerprinting detection via `add_init_script` (1-2 h)
- [ ] CNAME cloaking (about 1 h)
- [x] Cross-site tracking across audits (about 30 min)
- [ ] Input-box capture (1-2 h)
