# Browser behaviour (3P cookies / partitioning in Chrome & Playwright Chromium) and existing web-privacy auditing tools

Researched 2026-11-08. Local environment checked: Playwright Python 1.64.1, bundled Chromium 156.0.8078.4 (`chromium-1248`, `chromium_headless_shell-1248`).

## A1. Status of third-party cookies in Google Chrome (2024-2026)

### Takeaway
Chrome never deprecated third-party cookies. They are **allowed by default in normal Chrome** and **blocked by default in Incognito**. As of 17 Oct 2025 Google has also retired most Privacy Sandbox APIs, including Related Website Sets. CHIPS (Partitioned cookies) and FedCM remain.

### Cited Findings
- **Superseded, July 2024:** Google dropped its forced-deprecation plan in favour of "user choice" in Chrome's existing settings. — [MacRumors, 22 Jul 2024](https://www.macrumors.com/2024/07/22/google-keeping-third-party-cookies-chrome/)
- **22 Apr 2025:** Google said it would "maintain our current approach to offering users third-party cookie choice in Chrome" and "will not be rolling out a new standalone prompt for third-party cookies". It also said Incognito already blocks 3P cookies by default, and that IP Protection would launch in Incognito ("plan[s] to launch in Q3 2025"). — [Privacy Sandbox blog, "Next steps for Privacy Sandbox and tracking protections in Chrome"](https://privacysandbox.google.com/blog/privacy-sandbox-next-steps)
- **17 Oct 2025:** Google retired Attribution Reporting, IP Protection, On-Device Personalization, Private Aggregation (incl. Shared Storage), Protected Audience, Protected App Signals, **Related Website Sets (incl. requestStorageAccessFor and Related Website Partition)**, SelectURL, SDK Runtime and Topics. **CHIPS and FedCM stay supported**, and Private State Tokens are maintained. Chrome will keep offering users 3P-cookie choice. — [Privacy Sandbox blog, "Update on plans for Privacy Sandbox technologies"](https://privacysandbox.google.com/blog/update-on-plans-for-privacy-sandbox-technologies)
- Follow-up Chromium intent-to-deprecate threads for the individual APIs reportedly came on 7–8 Nov 2025 (secondary coverage). — [CookieYes KB](https://www.cookieyes.com/knowledge-base/privacy-tech/is-google-ending-privacy-sandbox/); [Engadget](https://engadget.com/cybersecurity/google-has-killed-privacy-sandbox-130029899.html)
- Regular Chrome allows 3P cookies by default, and users can block them in Settings. Incognito blocks them by default. A Canary flag, "Block TPCs in Incognito", tightened this in 2025, with temporary per-site exceptions possible. — [Winaero](https://winaero.com/google-changes-chromes-approach-to-third-party-cookies-and-privacy-sandbox); [Windows Report](https://windowsreport.com/google-tests-stricter-third-party-cookie-blocking-in-chrome-incognito/)
- **Historical, now superseded:** In 2024 Chrome ran "Tracking Protection", which blocked 3P cookies for 1% of users. Since Chrome 121 there is a testing flag, `chrome://flags/#test-third-party-cookie-phaseout` or `--test-third-party-cookie-phaseout`, that "will set Chrome to restrict third-party cookies". Cookies blocked this way show up in NetLog as `EXCLUDE_USER_PREFERENCES`. — [Chromium: third-party-cookie-phaseout](https://www.chromium.org/Home/chromium-privacy/privacy-sandbox/third-party-cookie-phaseout); [AllAboutCookies](https://dcmpx.remotevs.com/org/allaboutcookies/SL/google-chrome-blocks-third-party-cookies)

### Inferences
- Treat Related Website Sets as dead for 2026 work: don't build logic around RWS exemptions.
- "Chrome allows 3P cookies by default" is still the right baseline for a real-user threat model. A tracker cookie the auditor sees being sent cross-site would really reach default-Chrome users (not Incognito, Safari or Firefox ETP users).

### Gaps
- I didn't find primary Google wording on whether Chrome's own 1% Tracking Protection cohort was fully rolled back after Apr 2025. Secondary sources imply it was.

## A2. What Playwright's bundled Chromium actually does (measured locally)

### Takeaway
In Playwright's bundled Chromium (headless shell, v156), **unpartitioned `SameSite=None; Secure` third-party cookies are stored and sent cross-site by default**. **Playwright also disables Chromium's `ThirdPartyStoragePartitioning` feature by default**, so third-party iframe localStorage is shared across top-level sites. Real Chrome 115+ does not share it. Browser contexts are fully isolated from each other.

### Cited Findings
- **Local experiment** (script at `/tmp/claude-1000/-home-Penjinear-Downloads-HTB/6f424c1a-9bb8-44cf-b1d6-f1622905ee76/scratchpad/tpc/t.py`). Setup: one context visits top site `http://127.0.0.1:8765/top`, then `http://127.0.0.2:8765/top`. Each page embeds an iframe from third party `http://localhost:8765/tp`, which sets `uid` (`SameSite=None; Secure`), `puid` (`SameSite=None; Secure; Partitioned`) and `laxid` (no SameSite). Results on Chromium 156.0.8078.4, headless:
  - On site B, the third party received `Cookie: uid=abc123`, i.e. the **unpartitioned cookie set on site A was sent cross-site** (cross-site recognition works by default).
  - `puid` (Partitioned) was stored **twice**, with `partitionKey: 'http://127.0.0.1'` and `'http://127.0.0.2'`, and was never sent across sites.
  - `laxid` (no SameSite) **was not stored at all** from the 3P iframe, because the default is `Lax` and it is rejected in a cross-site context.
  - The iframe's `localStorage` value was **identical on both top-level sites**, i.e. not partitioned.
  - `browser.new_context().cookies()` returned `[]`: **contexts do not share cookies**.
  - Passing `--test-third-party-cookie-phaseout` (both the headless shell and `channel="chromium"` new headless) **did not** block the `uid` cookie in this localhost/IP test. Treat that as **inconclusive**: localhost/IP hosts may be handled specially, and I had no time to test real HTTPS domains.
- Playwright's Chromium launch switches (from installed `playwright/driver/package/lib/coreBundle.js`, `chromiumSwitches.ts`) include `--disable-features=...ThirdPartyStoragePartitioning...` (comment: "See https://github.com/microsoft/playwright/issues/32230"), plus `HttpsUpgrades`, `Translate`, `OptimizationHints` and others, and `--disable-field-trial-config`. — local source, Playwright 1.64.1
- Background to that switch: a user's localStorage, pre-set via `newContext()` for a cross-origin iframe, went missing in Chromium on Playwright 1.45. It was fixed by commit "fix(chromium): disable ThirdPartyStoragePartitioning (#32701)", closed 27 Sep 2024. No official way to re-enable it is given. — [playwright#32230](https://github.com/microsoft/playwright/issues/32230)
- Trying to re-enable it with `ignore_default_args=[<the --disable-features string>]` plus my own list without that feature, or with `--enable-features=ThirdPartyStoragePartitioning`, still gave shared localStorage in my test. **Inconclusive**: I didn't confirm whether the ignore took effect.
- Playwright's own tests expect Chromium to default unset `sameSite` to `Lax`, and expect `SameSite=None` without `Secure` over HTTP to be dropped in Chromium. They skip `requestStorageAccess` on Chromium ("requestStorageAccess API is not available in Chromium"). — [playwright PR #30384 diff](https://patch-diff.githubusercontent.com/raw/microsoft/playwright/pull/30384.diff)
- `partitionKey` was added to `browserContext.cookies()` / `addCookies()` in **Playwright 1.54**: "This property allows to save and restore partitioned cookies… browsers have different support and defaults for cookie partitioning." — [Playwright v1.54.0 release](https://github.com/microsoft/playwright/releases/tag/v1.54.0)
- In Python 1.64.1, `Cookie` TypedDict = `name, value, domain, path, expires, httpOnly, secure, sameSite, partitionKey: Optional[str]` (local `_impl/_api_structures.py`). Actual returned dicts use the camelCase key `partitionKey`, which is present **only** on partitioned cookies, plus an undocumented `_crHasCrossSiteAncestor` (observed locally).

### Inferences
- **How to tell partitioned from not:** `'partitionKey' in cookie`. If present, the cookie is CHIPS-partitioned, cannot be used for cross-site tracking, and should not be reported as a cross-site tracking cookie. If absent and `sameSite == 'None'` on a third-party domain, it **can** follow the user across sites in default Chrome.
- **Pitfall (important):** because Playwright turns storage partitioning off, any "third-party localStorage/IndexedDB ID is shared across sites" finding is an **artefact of Playwright**, not what real Chrome users experience. Only claim cross-site recognition from **unpartitioned cookies** (or first-party IDs synced to third parties via URLs). Don't claim it from 3P iframe storage.
- **Cross-site test design that works:** in the SAME context, visit site A, record each third party's cookie values (`Set-Cookie` plus `context.cookies()`), then visit site B and check request `Cookie` headers to the same third-party eTLD+1 for the same value. Verified mechanically above.
- **Pitfalls for that design:**
  1. It mixes consent states: rejecting on A doesn't stop B's CMP behaviour. Keep per-site evidence separate and tag cross-site observations with both sites' consent state.
  2. It breaks the current "one fresh context per site" rule. Use a dedicated second "linkage" pass, or a small fixed panel of reference sites, rather than polluting the main audit.
  3. Use eTLD+1 grouping (e.g. `doubleclick.net` and `google.com` are different sites but the same owner; use Tracker Radar `owner`).
  4. Values that are shared but identical for everyone (consent strings, `1`, language codes) aren't IDs. See the entropy rules in B4/B5.
  5. Bot detection can change what's served.
- Contexts are isolated, so a fresh context per site is a correct "first visit" baseline.

### Gaps
- No verified way found to make Playwright Chromium behave like real Chrome for storage partitioning. A test on two real HTTPS domains is needed.
- Not verified whether `--test-third-party-cookie-phaseout` or the `BlockThirdPartyCookies` pref has any effect in headless shell on real domains. Playwright exposes no context option to block 3P cookies (none found in the docs I checked).

## A3. SameSite, CHIPS, storage partitioning, Storage Access API

### Takeaway
Cross-site cookies need `SameSite=None; Secure`. `Partitioned` (CHIPS) cookies are keyed by top-level site and are not cross-site. Real Chrome partitions 3P storage (localStorage, IndexedDB, Cache, etc.) since v115, but Playwright switches that off.

### Cited Findings
- Storage partitioning has been "enabled for all users on Chrome 115 and later". It covers IndexedDB, Cache Storage, localStorage, sessionStorage, OPFS, Storage Buckets, Blob URLs (from Chrome 137), BroadcastChannel, SharedWorker, Web Locks, and 3P service workers. The key is origin + top-level site, plus an "ancestor bit" for cross-site frame chains. `postMessage` is unchanged. — [Privacy Sandbox: Storage partitioning](https://privacysandbox.google.com/3pcd/storage-partitioning)
- CHIPS remains supported after the Oct 2025 retirement, and Related Website Sets and `requestStorageAccessFor` are retired. — [Privacy Sandbox blog Oct 2025](https://privacysandbox.google.com/blog/update-on-plans-for-privacy-sandbox-technologies)
- Locally, Chromium's default `SameSite` for cookies with no attribute is `Lax`, so they're rejected in 3P iframe contexts. A `Partitioned` cookie gets one entry per top-level site with a distinct `partitionKey`. — local experiment (A2); consistent with [playwright PR #30384](https://patch-diff.githubusercontent.com/raw/microsoft/playwright/pull/30384.diff)

### Inferences
- Classification rule for the auditor:
  - **cross-site capable** = third-party domain, `sameSite == 'None'`, `secure`, no `partitionKey`, long expiry.
  - **partitioned** = has `partitionKey`.
  - **first-party only** = everything else.
- An HTTP cache isn't a useful auditor signal (Chrome has partitioned it since ~v86). That is background knowledge, not verified here.

### Gaps
- I didn't fetch MDN's CHIPS page for the exact attribute rules. From memory, CHIPS requires `Secure` and the `Partitioned` attribute; this is unverified in this session.

## B1. OpenWPM

### Takeaway
OpenWPM is a Firefox + Selenium research crawler, GPLv3, still actively maintained (releases track Firefox about every 4 weeks). It stores rich tables, which are a good schema model for "requests / cookies / JS calls with call stacks".

### Cited Findings
- Built on Firefox automated with Selenium. Output goes to SQLite, Parquet or remote storage. It aims to release "roughly once every four weeks" with Firefox. Versions before v0.10.0 are deprecated. 2,231 commits, 147 open issues. **GPLv3**, and it includes FourthParty and Privacy Badger code (GPLv3+). — [openwpm/OpenWPM](https://github.com/openwpm/OpenWPM)
- Main tables:
  - `http_requests`: url, top_level_url, method, referrer, resource_type, `is_third_party_channel`, `is_third_party_to_top_window`, triggering_origin, loading_origin.
  - `http_responses`: status, location, content_hash, is_cached.
  - `http_redirects`.
  - `javascript`: script_url, symbol, operation, value, call_stack.
  - `javascript_cookies`: record_type, change_cause, host, name, value, expiry, is_session, same_site, `first_party_domain`.
  - `callstacks`, `navigations`, `site_visits`, `crawl_history`.

  — [OpenWPM Schema-Documentation.md](https://raw.githubusercontent.com/openwpm/OpenWPM/master/docs/Schema-Documentation.md)
- The schema doc itself doesn't describe a cookie-sync / ID analysis. — same source

### Inferences
- The `javascript` table (symbol + operation + call_stack) is the model for an `add_init_script` fingerprinting hook. `http_redirects` is needed for cookie-sync detection, because IDs often pass through redirect chains.

### Gaps
- OpenWPM-based cookie-sync methodology (Englehardt & Narayanan 2016, "Online Tracking: A 1-million-site Measurement"). From memory and unverified this session: an ID cookie is long-lived (more than about 3 months), has a value of at least 8 characters that stays constant within a crawl, and differs between two independent crawls/profiles. Cookie syncing is an ID value appearing in a request URL to a different third party. Check the paper before quoting.

## B2. Blacklight (The Markup)

### Takeaway
Blacklight is Puppeteer/headless Chromium with a fresh profile. It visits the homepage plus one random internal page and runs about 9 tests with concrete, reusable heuristics. Its canvas fingerprinting thresholds are the ones to copy.

### Cited Findings
- Setup: Node + Puppeteer headless Chromium, fresh profile per scan, homepage plus one randomly chosen deeper page. It wraps fingerprintable Window APIs and attributes calls with Stacktrace-js. Results are cached 24 hours. Party boundaries use PSL+1. It uses DuckDuckGo Tracker Radar (owner and category), EasyList + EasyPrivacy (third-party matches only, filtered to "Ad Motivated Tracking"), and Tranco top 100k for benchmarks. — [The Markup, "How We Built a Real-Time Privacy Inspector"](https://themarkup.org/blacklight/2020/09/22/how-we-built-a-real-time-privacy-inspector)
- Tests, all from the same source:
  - **3P cookies**: Set-Cookie headers plus `document.cookie` writes by 3P domains.
  - **Ad trackers**: EasyList/EasyPrivacy.
  - **Key logging**: types preset values (email, password, name, address, card) into inputs without submitting, then searches requests for plain, base64, MD5, SHA-256 and SHA-512 forms.
  - **Session recording**: URL substrings of known session-replay vendors (Princeton 2017 list).
  - **Canvas fingerprinting**: width and height of at least 16px, at least 10 distinct characters drawn, no `save`/`restore`/`addEventListener` on the context, and extraction by `toDataURL` or a single `getImageData` of at least 16×16.
  - **Facebook pixel**: requests to Facebook with standard/custom event and advanced-matching params.
  - **GA remarketing audiences**: `stats.g.doubleclick` requests carrying `UA-`/`G-`/`AW-` IDs.
  - **X and TikTok pixels**: added Feb 2026.
- Limitations The Markup lists: bot detection (AWS vs local canvas 10% vs 8%), sampling by session recorders, attribution errors (e.g. jQuery), and that it doesn't judge intent or policy disclosure. — same source
- Open source as `blacklight-collector` on GitHub and npm `@themarkup/blacklight-collector`. The article doesn't state the licence. — same source

### Inferences
- The canvas heuristic and the hash-variant search (base64/MD5/SHA-x of known values) port directly to Python, using `hashlib` + `base64` over request URLs and post bodies. The key-logging test types data into forms; that's borderline for a "passive only" rule, so skip it or fill fields without sending.

### Gaps
- blacklight-collector licence not verified (believed MIT, unconfirmed). Check its LICENSE before copying code.

## B3. EDPS Website Evidence Collector (WEC) and EDPB Website Auditing Tool (WAT)

### Takeaway
Both are EU-official, open source under **EUPL-1.2**. WEC (EDPS) is a headless crawler that collects evidence. WAT (EDPB, Jan 2024) is a GUI audit tool that can import WEC results.

### Cited Findings
- WEC "automates the website evidence collection of storage and transfer of personal data". It is EUPL 1.2, hosted at code.europa.eu (project created 6 Jun 2024 after moving off GitHub), with 1,537 commits and 33 releases. — [code.europa.eu/EDPS/website-evidence-collector](https://code.europa.eu/EDPS/website-evidence-collector)
- The old GitHub URL `github.com/EU-EDPS/website-evidence-collector` returns 404. — observed this session
- EDPB WAT: launched Jan 2024, free and open source under EUPL 1.2 via code.europa.eu. It lets auditors prepare, run and evaluate audits by visiting the site, and can import and evaluate WEC results. A later version added analysis import/export, multi-database management with trust levels, full-page screenshots and five languages. — [EDPB: website auditing tool](https://www.edpb.europa.eu/documents/514_en); [EDPB launch news](https://www.edpb.europa.eu/node/7174_en)

### Inferences
- Since WAT can import WEC results, matching the WEC evidence categories (cookies, local storage, beacons, traffic hosts) in the audit JSON lets the project say "aligned with EDPS/EDPB methodology", which is useful for the legal framing.

### Gaps
- I couldn't retrieve WEC's README (GitLab pages returned only headers or 404). From memory and unverified: WEC is Node/Puppeteer. It records cookies (HTTP and JS), localStorage, web beacons matched with EasyPrivacy, hosts contacted, and links found. It browses a configurable number of first-party links (`--browse-link`, `--max`). It outputs YAML/JSON/HTML/DOCX/PDF reports. Verify before citing.

## B4. DuckDuckGo Tracker Radar and Privacy Badger heuristics

### Takeaway
Tracker Radar gives per-domain `prevalence`, `cookies`, `fingerprinting` 0–3, `cnames` and `owner`. Privacy Badger's heuristic has exact, small constants worth copying: 3 sites, cookie entropy of 12 bits or less allowed, pixel cookie-share entropy above 33 bits.

### Cited Findings
- Tracker Radar per-domain fields:
  - `prevalence`: share of top sites requesting the domain, 0–1.
  - `cookies`: share of top sites where it sets cookies, 0–1.
  - `fingerprinting` 0–3: 0 no API use, 1 some (not obviously tracking), 2 many APIs (possibly tracking), 3 excessive (almost certainly tracking).
  - `resources[]`: regex rule, apis, cnames, `firstPartyCookies`, `firstPartyCookiesSent`, exampleSites.
  - `cnames`, `owner{name,displayName,privacyPolicy,url}`, `categories`, `performance`, `types`, `nameservers`.

  — [tracker-radar DATA_MODEL.md](https://github.com/duckduckgo/tracker-radar/blob/main/docs/DATA_MODEL.md)
- Privacy Badger constants: `TRACKING_THRESHOLD: 3` ("The number of 1st parties a 3rd party can be seen on") and `MAX_COOKIE_ENTROPY: 12`. — [privacybadger src/js/constants.js](https://raw.githubusercontent.com/EFForg/privacybadger/master/src/js/constants.js)
- How Privacy Badger decides a cookie is tracking (`hasCookieTracking`): it parses Cookie and Set-Cookie headers on third-party requests and ignores `__cf_bm`. **Any value not in `lowEntropyCookieValues` is immediately tracking.** Known low-entropy values carry fixed bit estimates: empty/yes/no/true/false/optout = 3 bits, single digit = 4, ISO-639-1 language code = 8. The bits are summed, and over `MAX_COOKIE_ENTROPY` (12) counts as tracking. — [privacybadger heuristicblocking.js](https://raw.githubusercontent.com/EFForg/privacybadger/master/src/js/heuristicblocking.js)
- Pixel cookie sharing (first-party cookie value leaked to a 3P image URL): runs on top-frame `image` requests with `?`. It reads non-HttpOnly first-party cookies, finds common substrings between cookie values and query param values (`MIN_STR_LEN = 8`), and discards substrings present in the page URL or user agent and values in `lowEntropyQueryValues`. If `estimateMaxEntropy` exceeds `TRACKER_ENTROPY_THRESHOLD = 33`, it records it as tracking. — same source
- Third-party `beacon`/`ping` requests count as tracking directly. Sites are counted by eTLD+1 (`getBaseDomain`), only for third-party requests. CNAME-cloaked hosts are resolved through `cnameDomains`. `snitch_map` holds the list of distinct first-party sites per tracker base domain. The domain is blocked when that list reaches the threshold (a stored `blockThreshold` setting, default 3). `consensu.org` is excluded. — same source
- Privacy Badger also looks for localStorage "supercookies" and canvas fingerprinting ("can detect canvas-based fingerprinting"). It "observes the same third-party host tracking on three separate sites". — [privacybadger.org FAQ](https://privacybadger.org/)
- **Since Oct 2020, local learning is OFF by default** after Google Security Team disclosures that local learning could itself enable fingerprinting. EFF removed the first-to-third-party cookie heuristic. Users now get pre-trained lists from the Badger Sett crawler, and local learning is opt-in. — [EFF Deeplinks Oct 2020](https://www.eff.org/deeplinks/2020/10/privacy-badger-changing-protect-you-better); [privacybadger.org](https://privacybadger.org/)

### Inferences
- **Copyable rules for the auditor** (plain code, no LLM):
  1. 3P cookie value not in a small low-entropy allowlist means a likely identifier.
  2. Third-party `navigator.sendBeacon`/ping counts as tracking. Playwright exposes `resource_type == "beacon"` or `"ping"` in Chromium.
  3. A first-party cookie value substring of 8+ characters with high entropy appearing in a 3P request URL is ID leakage / cookie sharing.
  4. Accumulate a cross-audit `snitch_map` over the `audits/` folder. A third-party eTLD+1 seen setting ID cookies on 3+ audited sites is flagged as a "cross-site tracker" (Privacy Badger's threshold).
- The Privacy Badger heuristic code is **GPLv3+** (as noted in OpenWPM's README). Re-implement the idea rather than copying code, or keep the project GPL-compatible.

### Gaps
- Tracker Radar licence not confirmed this session. I believe it's **CC BY-NC-SA 4.0** (non-commercial, which is fine for a hackathon but must be attributed). Check the LICENSE file.
- Tracker Radar Collector crawler methodology (Puppeteer-based, collects requests, cookies, API calls, CNAMEs) wasn't fetched this session.
- `estimateMaxEntropy` internals weren't fetched (it's in utils.js).

## B5. WhoTracks.me / "Tracking the Trackers" k-anonymity idea

### Takeaway
I couldn't fetch the methodology page (404 after redirect). The idea, from prior knowledge and **unverified this session**: a value counts as "unsafe" (a user ID) only if few distinct users send it to a given third party. Values many users share are safe.

### Cited Findings
- whotracks.me/blog/methodology.html now 301-redirects to ghostery.com/whotracksme/blog/methodology.html, which returned 404. — observed this session

### Inferences
- Adaptation without real users: run two (or three) fresh contexts against the same site, which act as different "users". A third-party cookie or query value that's **identical across contexts** is not a user ID (config, consent string, version). A value that **differs per context but stays constant within a context across pages/sites** is a user ID. Combine with the A2 cross-site test: the same value reaching a third party on site A and site B within one context, but different in another context, is strong evidence of cross-site recognition.

### Gaps
- Yu et al., WWW 2016 ("Tracking the Trackers") details (exact k, minimum value length, server-side counting) weren't verified this session. Don't quote numbers without checking the paper.

## B6. Filter-list matching in Python, and other 2022-2026 tools

### Takeaway
For EasyPrivacy matching in Python, use a binding to Brave's adblock-rust (`braveblock`, or the `adblock` package). `adblockparser` is pure Python and slower.

### Cited Findings
- `braveblock` on PyPI: "fast and easy adblockplus parser and matcher based on adblock-rust", via pyo3 (Intsights). Usage is `Adblocker(rules=...)` plus a check for whether a URL should be blocked. Version 0.5.1. Upstream adblock-rust is **MPL-2.0**. — [pypi braveblock](https://pypi.org/project/braveblock); [Intsights/braveblock](https://github.com/Intsights/braveblock)

### Inferences
- Match with request context (source URL, request type, third-party flag), not URL alone, otherwise `$third-party` and `$script` options are ignored.

### Gaps
- Not verified this session (from prior knowledge, check before relying on any of it):
  - EasyPrivacy licence: dual GPLv3 / CC BY-SA 3.0.
  - `adblockparser`: MIT, largely unmaintained.
  - PyPI `adblock` (ArniDagur/python-adblock): MIT/Apache-2.0, maintenance status.
  - Consent-O-Matic: Aarhus University, MIT, CMP click rules (reusable as selector rules for "Reject all").
  - BannerClick: banner detection/interaction crawler (2023).
  - CookieBlock: ETH Zürich, USENIX Security 2022, classifies cookie purpose.
  - CookieGraph: USENIX Security 2023, first-party tracking cookies.
  - None of these were researched in this session.
