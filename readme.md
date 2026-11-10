# Overveiw 
A browser agent that visits a site, clicks “Reject all” on the cookie banner, and watches what still gets sent anyway. It then reads the privacy policy, points out where the site broke its own promises, and drafts a complaint letter.

Core Features 
1. Record everything: open the site and log every request, cookie and script it loads.
2. Reject cookies: the agent finds the cookie banner and clicks “Reject all”, including digging through “Manage preferences” if needed.
3. Browse after rejecting: the agent clicks around a few pages so trackers have a chance to fire.
4. Flag trackers: label which requests are trackers, using a known list like DuckDuckGo’s Tracker Radar or EasyPrivacy.
5. Read the policy: the agent finds the privacy policy and pulls out which companies it says it shares data with.
6. Compare: what they said against what actually happened, for example “Policy names 5 companies, we saw 18” or “Meta tracked you after you said no”.
7. Draft the letter: a complaint or data request (Subject Access Request) addressed to their data protection contact. It’s a draft only and never sent automatically.
8. Results page: a clear visual of what leaked, the broken promises, and the letter.
9. Check for crossite tracking. 

Additonal features 
- Fuck this site (send random data)
- Block ads 
- look for data collection in input boxes, eg typing a email into a   box w out submiting it 
- cnamw clokeing  


## Credits and licences
- **Tracker data:** `data/trackers.json` is derived from [DuckDuckGo Tracker Radar](https://github.com/duckduckgo/tracker-radar)
  (© 2020 Duck Duck Go, Inc.), licensed [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).
  We reduced it to a domain → company-name map; that file is shared under the same licence. Details: `data/README.md`.
- **Open-source libraries** (all MIT / BSD-3-Clause / Apache-2.0 / PSF / ISC): Playwright, FastAPI, Starlette,
  uvicorn, Pydantic, httpx, anyio, greenlet, OpenAI Python SDK, tldextract (with the Public Suffix List, MPL-2.0),
  python-dotenv, pypdf (PDF policies).
- **Browsers** (downloaded by Playwright, not included in this repo): Firefox (MPL-2.0) for audits, Chromium (BSD)
  for the cross-site proof.
- **Firefox extension and dashboard:** our own code and icons; nothing is loaded from third-party sites.
- **Research notes and reports** (`research_notes/`, `reports/`, `docs/`): contain public sector information licensed
  under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)
  (UK legislation, ICO guidance), short quotations from EDPB guidelines and academic papers, each cited where used.
  Detection methods follow published research (OpenWPM, Englehardt & Narayanan; Acar et al.; Chen et al.;
  Privacy Badger's heuristics); no code from those projects is included.
- **Services:** OpenAI API (AI review, policy reading, letters), Brevo (email sending).
