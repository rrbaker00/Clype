# Clype for Firefox

Sits in the toolbar. Every time you open a **new site**, it asks your local Clype server to audit
it in the background (the server's own browser rejects all cookies, browses, reads the privacy
policy and runs the AI review). Your own browsing isn't touched.

- **Badge on the icon:** `…` auditing, `!` critical, `H` high, `M` medium, `✓` no/low issues,
  `?` the site blocked the audit browser, `×` audit failed, `off` server not running.
- **Click the icon:** this site's result + every report (newest per site), auto-audit on/off,
  "Skip this site", "Audit now".
- **Critical:** a box in the top-left of the page + a system notification (click it to open the report).
- Sites audited in the last 7 days reuse that report. Banking, email, NHS, gov.uk, login pages
  and local addresses are never audited.
- Audits started by the extension **never send emails**, whatever `SEND_MODE` says (letters are
  drafted only; use "Send email" on the report if you want to send one).

## Your own browser (phase 2, "Reject in my tab")

When you open a new site, the extension also clicks the cookie banner's **reject** option in your
tab (reject-type wording only, inside a cookie banner; never Accept, never "Reject & Pay"), records
what your tab sends before and after, and ~25 s later sends that capture to the local server. The
server runs the same plain-code checks as an audit (no AI) and saves it in `sessions/` (git-ignored:
it contains your real cookies). Results: "Your browser" in the popup and on the audit page.

If you accepted a site's cookies before, its banner won't show again: use **Reset this site's
cookies** in the popup. It clears that site's cookies + saved choice, reloads the page (the extension
rejects the banner again and records a fresh "your browser" capture) and queues a fresh server audit
straight away, even if the site was audited in the last 7 days. (Firefox's padlock → *Clear cookies
and site data…* clears cookies too, but doesn't restart the audit.)

## Run it

1. Start the server in the project folder: `uvicorn api.main:app` (must be on port 8000).
2. Firefox: open `about:debugging#/runtime/this-firefox` → **Load Temporary Add-on…** →
   choose `extension/manifest.json`.
3. The Clype shield appears in the toolbar. (If it's in the puzzle-piece menu instead, click the
   puzzle piece → ⚙ next to Clype → **Pin to Toolbar**.)

Temporary add-ons are removed when Firefox closes; load it again next time.
