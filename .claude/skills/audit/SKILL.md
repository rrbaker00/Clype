---
name: audit
description: Run a full consent audit on a URL and summarise what it found. Use when asked to audit, test or check a site.
---

Run an audit on the URL given in $ARGUMENTS.

1. Run `python -m agent.run_audit $ARGUMENTS`.
2. If it fails, show the error and the most likely cause in one line. Don't
   start rewriting code unless asked.
3. If it works, open the newest file in `audits/` and report, briefly:
   - Did it find and reject the banner? Which method?
   - Trackers after reject, and the top 3 companies.
   - Companies not named in the policy.
   - Time taken and tokens used.
   - Anything that looks wrong (e.g. 0 requests means capture is broken).
4. Say whether this site is a good demo candidate (yes/no + one reason).

Keep the whole report under 10 lines.
