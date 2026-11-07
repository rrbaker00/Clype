---
name: demo-check
description: Pre-demo sanity check. Use before judging or when asked if we're ready to demo.
---

Check we're ready to demo. Report as a short pass/fail list.

1. `pip install -r requirements.txt` succeeds and Chromium is installed.
2. API starts: `uvicorn api.main:app` (start it, check it's up, stop it).
3. Run `python -m agent.run_audit` on each demo site listed in
   `demo_sites.txt` (one URL per line). Note pass/fail and time for each.
4. Every audit JSON has `cost`, `duration_s`, `findings` and `letter`.
5. No API keys in tracked files: `git grep -nI -E "(sk-|AIza|api_key\s*=)"`.
6. README explains what it is, how to run it, and lists open-source
   projects and tracker lists we used.

End with one line: ready / not ready, and the single most important fix if
not ready. Don't fix anything without asking.
