# Audit JSON format

This is the contract between the agent (Person A) and the frontend (Person B).
One audit = one JSON file in `audits/`. Add fields freely; don't rename or
remove existing ones without telling the other person.

```json
{
  "url": "https://example.com",
  "started_at": "2026-11-07T20:15:00Z",
  "duration_s": 42.1,
  "cost": { "llm_calls": 3, "input_tokens": 8200, "output_tokens": 1100, "model": "..." },

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
    "before_consent": [ { "name": "_fbp", "domain": ".example.com", "tracker_company": "Meta" } ],
    "after_reject":   [ { "name": "_fbp", "domain": ".example.com", "tracker_company": "Meta" } ]
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
      "law": "PECR reg. 6"
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

Bonus fields (only if built):
- `fingerprinting`: list of `{ "api": "canvas.toDataURL", "script": "https://..." }`
- `session_replay`: list of `{ "vendor": "Hotjar", "captured_input": true }`
