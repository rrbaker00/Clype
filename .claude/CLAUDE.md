# Receipts: consent auditor (HackTheBurgh 2026)

A browser agent that visits a website, clicks "Reject all" on the cookie
banner, and records what the site still sends anyway. It then reads the
privacy policy, compares promises to behaviour, and drafts a complaint /
Subject Access Request letter.

Team of 2, 24-hour hackathon. Submission is Sunday 8 Nov, around midday.

## How to talk to me
- Keep explanations short and simple. We're running on low sleep.
- Give the change, then one line on why. No long essays.
- If something will take more than ~30 mins, say so before starting.

## Who does what
- **Person A, agent and backend:** everything in `agent/` and `api/`.
- **Person B, frontend:** everything in `web/`.
- The audit JSON format in @.claude/docs/audit-format.md is the contract
  between the two. Don't change it without saying so.

## Stack
- Python 3.11+, Playwright (Chromium only), FastAPI, uvicorn.
- LLM is used ONLY for these jobs:
  1. Finding/clicking the cookie banner when plain selectors fail.
  2. Reading the privacy policy.
  3. Drafting the letter.
  4. Legal review: reads the evidence summary + privacy/cookie policies and adds
     findings tagged `"source": "ai"` (agent/legal_review.py). Must cite evidence IDs.
- Everything else is plain code. No LLM calls in the capture loop.

## Core features (in build order)
1. Record every request, cookie and script on page load.
2. Click "Reject all", including digging into "Manage preferences".
3. Browse a few pages after rejecting.
4. Flag trackers using a known list (DuckDuckGo Tracker Radar or EasyPrivacy).
5. Find the privacy policy and extract the companies it says it shares with.
6. Compare what the policy said against what was observed.
7. Draft a complaint letter (auto for critical/high audits, on request otherwise).
   Critical ones are emailed per SEND_MODE.
8. Results page showing what leaked, broken promises, and the letter.

Bonus, only if core is done: session-replay keystroke capture, fingerprinting
detection (canvas / WebGL / AudioContext hooks via `add_init_script`).

## Hard rules
- **Passive only.** We observe what our own browser receives. No attacks,
  no fuzzing, no bypassing auth.
- **Sending is limited and controlled by `SEND_MODE` in `.env`.** Only audits whose worst finding
  is `critical` are emailed automatically (agent/mailer.py, via Brevo SMTP). `test` (default) sends to our own
  Gmail; `live` sends to the real DPO, max one email per site and 5 per day; `off` = drafts only.
  `outbox` saves .eml files instead. `high` audits are drafted, never sent. Never send from tests or debugging runs.
- **Track cost.** Log tokens used and time taken per audit into the audit
  JSON. Wordsmith judges on this.
- Never commit `.env` or API keys.
- Keep it simple. Working beats clever. Don't add features not on the list
  above without asking.

## Layout
```
agent/       capture, consent, browse, trackers, policy, compare, letter
  run_audit.py   CLI: python -m agent.run_audit <url>
api/main.py  FastAPI: POST /audit {url} -> audit JSON
web/         frontend
data/        tracker lists
audits/      saved audit JSON (one file per run)
```

## Commands
- Install: `pip install -r requirements.txt && playwright install chromium`
- Run an audit: `python -m agent.run_audit https://example.com`
- Run API: `uvicorn api.main:app --reload`

## Sponsor tracks we're targeting
Wordsmith (main), G-Research, Metaview (overall), JetBrains (build with Air).
Details: @.claude/docs/tracks.md
