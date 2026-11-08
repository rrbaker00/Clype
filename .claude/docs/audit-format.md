# Audit JSON format

This is the contract between the agent (Person A) and the frontend (Person B).
One audit = one JSON file in `audits/`, named `<YYYYMMDDTHHMMSS>_<domain>.json` (one per run, never overwritten). Add fields freely; don't rename or
remove existing ones without telling the other person.

```json
{
  "url": "https://example.com",
  "started_at": "2026-11-07T20:15:00Z",
  "duration_s": 42.1,
  "browser": "firefox 157.0",   // engine that ran the audit (AUDIT_BROWSER, default firefox)
  "cost": { "llm_calls": 3, "input_tokens": 8200, "output_tokens": 1100, "model": "...",
            "by_model": { "gpt-5.4": { "llm_calls": 1, "input_tokens": 2000, "output_tokens": 900 } } },  // by_model: newer audits only, used for the /api/usage spend estimate

  "consent": {
    "banner_found": true,
    "rejected": true,
    "method": "selector",          // "selector" | "llm" | "failed"
    "clicks": ["Manage preferences", "Reject all"]
  },

  "requests": [
    {
      "url": "https://connect.facebook.net/...",
      "domain": "facebook.net",
      "phase": "after_reject",     // "before_consent" | "after_reject"
      "type": "script",            // Playwright resource type
      "tracker": { "is_tracker": true, "company": "Meta", "category": "Advertising" }
    }
  ],

  "cookies": {
    "before_consent": [ { "name": "_fbp", "domain": ".example.com", "tracker_company": "Meta", "value_kind": "id" } ],
    "after_reject":   [ { "name": "_fbp", "domain": ".example.com", "tracker_company": "Meta", "value_kind": "id" } ]
  },

  "policy": {
    "url": "https://example.com/privacy",
    "found": true,
    "companies_named": ["Google", "Stripe"],
    "dpo_contact": "privacy@example.com"
  },

  "findings": [
    {
      "severity": "high",          // "high" | "medium" | "low"
      "title": "Meta tracked you after you rejected cookies",
      "detail": "12 requests to facebook.net after clicking Reject all.",
      "law": "PECR reg. 6",
      "law_eu": "ePrivacy Directive 2002/58/EC Art. 5(3) ..."   // EU equivalent (agent/eu_law.py), or null
    }
  ],

  "summary": {
    "trackers_after_reject": 18,
    "companies_seen": 9,
    "companies_in_policy": 2,
    "companies_not_disclosed": ["Meta", "TikTok"]
  },

  "letter": { "kind": "sar", "to": "privacy@example.com", "subject": "...", "body": "..." }
}
```

Added for the AI legal review (nothing renamed):
- every finding has `"source"`: `"observed"` (plain-code check) or `"ai"` (legal review).
  AI findings also have `"evidence"` (e.g. `["E2", "E5"]`), `"policy_quote"` (exact
  sentence from the policy, or null) and `"reasoning"`.
- `policy.cookie_policy_url`, `policy.text_chars`, `policy.chars_sent`, optional `policy.error`.
- `ai_review`: `{ "model", "summary", "findings_kept", "findings_dropped", "evidence": ["E1: ...", ...], "error"? }`
- `visited_pages`: pages browsed (and scrolled) after reject.
- `fingerprinting`: list of `{technique: "canvas"|"webgl"|"audio"|"fonts", script, detail, phase}`, one per technique per script per phase (agent/fingerprint.py). `summary.fingerprinting_domains` lists the script domains.
- `id_leaks`: our per-browser IDs found in requests to OTHER companies (agent/crosssite.py). Each: `{cookie, cookie_domain, id_preview, to, company, category, phase, in: "address"|"body", encoding: "raw"|"base64"|"base64url"|"md5"|"sha1"|"sha256", confidence: "confirmed"|"likely", example}`. "confirmed" = the value differed in a second, fresh browser; only confirmed leaks to known tracker companies become findings ("Your ID was sent to X ..."). Full IDs are never saved, only `id_preview`.
- `id_syncs`: ad-tech ID matching seen in requests: `{type: "Google cookie matching"|"Prebid shared user IDs", to, phase, example?, sources?}`. Any = a "high" finding.
- `summary.id_leak_companies`: companies that received one of our IDs.
- Captures from the user's own Firefox (extension phase 2) are saved as `sessions/<timestamp>_<site>.json` (git-ignored: real cookies). Same shape as an audit's `consent` (method "extension"), `requests`, `cookies`, `findings` (source "your_browser"), `summary`, `id_leaks`, `id_syncs`, plus `compared_with_audit` (the headless audit used for the policy and as the second browser for the ID check). API: `POST /api/extension/session`, `GET /api/sessions/latest?site=`.
- Cross-site proof results (not part of an audit) are saved as `linkage/<timestamp>.json`: `{started_at, duration_s, sites: [{site, url, loaded, rejected, error?}], requests, links: [{company, category, via, id_preview, sites: {site: {phases, example}}, after_reject_on}], cost}`. A link = the same per-browser ID reached the same company from 2+ sites in one browser. API: `POST /api/cross-site/prove {sites?}` (2-5 audited sites; omitted = auto-picked), `GET /api/cross-site/proof`.
- `cookies.*[].value_kind`: what the cookie holds: `"empty"` (blank, or only `key=` labels), `"placeholder"` (deleted / null / 0 / false), `"id"` (looks like a unique identifier) or `"value"` (anything else). Empty and placeholder tracker cookies are not counted as tracking evidence (compare + AI review).

Added for letters and email:
- `letter` is `null` unless the audit's worst finding is `critical`/`high` (auto) or the user clicked
  "Create draft letter". Shape: `{ "kind": "complaint", "to", "subject", "body", "drafted_at", "model",
  "findings_used": [titles], "auto": {"tier", "reason"}, "delivery": null | {...}, "note"?, "error"? }`
- `letter.delivery` (critical only): `{ "mode": "off"|"test"|"live", "sent", "to", "intended_to", "at", "reason", "message_id", "site" }`
- severities are now `critical` > `high` > `medium` > `low`. `critical` only comes from the AI review
  safeguard; AI findings also carry `ai_severity` and `severity_note`.

Added for reliability:
- `loaded`: false if the site couldn't be opened OR showed a bot-protection / HTTP 4xx-5xx page
  (then no AI review / letter, 0 LLM calls; the reason is in `errors`).
- `policy.format`: `"html"` or `"pdf"` (PDF policies are downloaded and read with pypdf).
- `errors`: `[{"step", "error"}]` for any pipeline step that failed; the rest of the audit still ran.

Added for extra compliance checks:
- `consent.accept_label`: text of the one-click Accept button on the banner's first screen (looked at, never clicked), or null.
- `consent.reject_steps`: how many clicks rejecting took (null if reject failed). Accept 1 click vs reject 2+ = finding.
- `consent.preticked`: labels of non-essential cookie toggles already ON before we touched anything (banner first screen + "Manage preferences" panel; locked "necessary" ones excluded). Non-empty = finding.
- `ai_review.policy_checklist`: UK GDPR Art. 13 items, each `{ "label", "status": "present"|"missing"|"unclear"|"not_checked", "quote" }`.
  "missing" only if the whole policy was checked AND no matching keywords exist anywhere in it.

Bonus fields (only if built):
- `fingerprinting`: list of `{ "api": "canvas.toDataURL", "script": "https://..." }`
- `session_replay`: list of `{ "vendor": "Hotjar", "captured_input": true }`
