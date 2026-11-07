# Clype: to-do list

**P** = partner (agent), **Y** = Josh (web/API). Times are rough.
Tick items with `[x]` as you go and commit, so we all see the same list.
Deadline: Sunday 8 Nov, around midday. Last 2 hours = no new features.

## 0. Now (5 min)
- [ ] **Y** Restore UI work from stash (Severe section + letter button): `git stash pop`.
      `requirements.txt` will conflict, keep the 6-line version. Then commit.
- [ ] **Both** Agree who edits `api/main.py` (both of us have touched it).
- [ ] **Both** Install deps: `python3 -m pip install -r requirements.txt && python3 -m playwright install chromium`

## 1. Make findings trustworthy (P, about 2.5 h): highest priority
A wrong accusation in front of judges is worse than a missed one.
- [ ] `trackers.py`: exclude static/CDN domains that are wrongly counted as trackers:
      `gstatic.com`, `googleapis.com`, `ytimg.com`, `recaptcha.net`, `fbcdn.net`, `twimg.com`,
      `azureedge.net`, `licdn.com` (20 min)
- [ ] `trackers.py`: data says `"Amazon.com"` but allowlist says `"Amazon"`, so Amazon never matches.
      Add Permutive, The Trade Desk, LiveRamp, ID5, Lotame, Teads (15 min)
- [ ] `compare.py`: one finding per company tracking after reject (even if the policy names it),
      plus a separate "not named in policy" finding (20 min)
- [ ] `compare.py`: alias map: Meta/Facebook, Alphabet/YouTube/Google, X/Twitter,
      TikTok/ByteDance, Amazon Alexa/Amazon (15 min)
- [ ] Severity + legal wording: PECR reg. 6 is about cookies/storage, not requests. Some analytics
      may be exempt under the Data (Use and Access) Act 2025. Advertising / tracker cookies after
      reject = high, analytics = medium. Requests = "sent data to X after you said no" (20 min)
- [ ] `policy.py:32`: 15,000-char cut can hide named companies, which then get reported as
      "not disclosed". Raise to about 60k or send only paragraphs about third parties/partners/sharing (20 min)
- [ ] `policy.py`: phrase `"privacy"` can click the banner's "Privacy settings" instead of the
      policy page. Prefer links whose href contains `privacy` (20 min)
- [ ] `policy.py:67`: `info.get("companies_named") or []` in case the LLM returns null (2 min)
- [ ] `run_audit.py`: when reject failed, leave `cookies.after_reject` empty
      (Guardian currently shows 7 "after reject" cookies with no reject) (5 min)
- [ ] Run the `policy-checker` agent on a fresh BBC audit

## 2. Pipeline reliability (P, about 1.5 h)
- [ ] `run_audit.py:89`: save as `audits/{timestamp}_{domain}.json` (no overwrites, UI sorts by name),
      path based on project root not the current folder (10 min)
- [ ] try/except around each step so a failure still saves a partial audit; timeout on `page.goto` (30 min)
- [ ] Hard cap on LLM calls per audit (protect the €30 budget) (10 min)
- [ ] Check `gpt-5.4` / `gpt-5.4-mini` work on our key (2 min)
- [ ] Don't save cookie `value`s, we don't need them (2 min)
- [ ] API `POST /audit`: only http(s), strip to origin, block localhost; rename to `/api/audit` (10 min)

## 3. Letter (feature 7, about 1.2 h). Request-only, draft only, never sent.
- [ ] **P** `agent/letter.py`: `llm.ask_strong` drafts a SAR / complaint using ONLY facts in `findings`.
      If `dpo_contact` is null (BBC), use a clear placeholder in "To" (30 min)
- [ ] **Y/P** `POST /api/audits/{id}/letter`: draft, save `letter` into the JSON, add tokens to `cost`,
      return the letter (20 min)
- [ ] **Y** Wire the "Create draft letter" button: "Drafting…" state, show letter, show errors (20 min)

## 4. UI (Y, about 1 h)
- [ ] Run an audit from the page: URL box, "running…" (20-60 s), then open the result (30 min)
- [ ] `pay_or_consent` gets its own pill: "Pay-or-consent wall" (it's a finding in itself) (10 min)
- [ ] Show `visited_pages` on the detail page (10 min)
- [ ] Remove or label the 3 fake `.example` test audits before the demo (5 min)

## 5. Demo prep (both, about 2 h, Sunday morning)
- [ ] Pick 2-3 sites with juicy results, list them in `demo_sites.txt`, keep their audit JSON as backup
- [ ] Run `/demo-check`
- [ ] README: what it is, how to run, credit DuckDuckGo Tracker Radar (check its licence, needs attribution)
- [ ] Show tokens / time / model on screen (Wordsmith judges this)
- [ ] Record a backup video
- [ ] Last 2 hours: no new features

## Stretch (only if everything above is done)
- [ ] Auto-audit browser extension (about 1 h)
- [ ] Fingerprinting detection via `add_init_script` (1-2 h)
- [ ] CNAME cloaking (about 1 h)
- [ ] Cross-site tracking across audits (about 30 min)
- [ ] Input-box capture (1-2 h)
