# Cross-site tracking mechanisms: cookie syncing, link decoration / UID smuggling / bounce tracking, CNAME cloaking (detection notes for a passive Playwright auditor)

Note: notes gathered 2026-11-08. About 20 tool calls. Primary papers were read where possible: the OpenWPM full PDF, the CNAME of the Game full PDF, the UID smuggling paper via ar5iv, and the Papadopoulos et al. HTML. Facts tagged "(general knowledge, unverified this session)" come from background knowledge and were not confirmed against a source during this research.

## A. Cookie syncing / ID syncing: how it works and how to detect it

### Takeaway
Cookie syncing is detectable with plain code. Build a set of "ID-like" cookie values (long-lived, 8-100 chars, ideally different between two runs). Then flag any request whose URL, Referer or redirect `Location` contains one of those values and goes to a different eTLD+1 (registrable domain) than the one that set it. On top of that, match known cookie-match endpoints and params (Google `google_nid`/`google_cm`/`google_gid`/`google_push`, `/usersync`, `/setuid`, etc.) and Prebid `eids` in POST bodies. Of the three mechanisms, this one gives the strongest evidence that third parties can link the same user across sites.

### Cited Findings

**Exact OpenWPM rules (Englehardt & Narayanan, CCS 2016, "Online Tracking: A 1-million-site Measurement and Analysis")**
- ID-cookie parsing: each cookie value is parsed as `(name1=)value1|...|(nameN=)valueN`, "where | represents any character except a-zA-Z0-9 -=". — [OpenWPM paper PDF](https://www.cs.princeton.edu/~arvindn/publications/OpenWPM_1_million_site_tracking_measurement.pdf)
- A (cookie-name, parameter-name, parameter-value) tuple is an ID cookie if: "(1) the cookie has an expiration date over 90 days in the future (2) 8 ≤ length(parameter-value) ≤ 100, (3) the parameter-value remains the same throughout the measurement, (4) the parameter-value is different between machines and has a similarity less than 66% according to the Ratcliff-Obershelp algorithm". Two synchronized measurements are run on separate machines to support rule (4). — [OpenWPM paper](https://www.cs.princeton.edu/~arvindn/publications/OpenWPM_1_million_site_tracking_measurement.pdf)
- Sync detection (Appendix 13.3): "We consider two parties to have cookie synced if a cookie ID appears in specific locations within the referrer, request, and location URLs." The direction rules are:
  - "If the ID appears in the location URL: the original requested domain is the sender of the ID, and the redirected location domain is the receiver."
  - "If the ID appears in the request URL: the requested domain is the recipient of a synced ID."
  - "If the ID appears in the referrer URL: the referring domain is the sender of the ID, and the requested domain is the receiver."
  
  They account "for URL encoding and other subtleties." — [OpenWPM paper](https://www.cs.princeton.edu/~arvindn/publications/OpenWPM_1_million_site_tracking_measurement.pdf)
- Caveat from the authors: the method "captures both intentional and accidental ID sharing" (e.g. a site putting a user ID in its own query string, which then leaks via Referer). The results are "an upper bound on cookie syncing as the practice is defined in the online advertising industry." — [OpenWPM paper](https://www.cs.princeton.edu/~arvindn/publications/OpenWPM_1_million_site_tracking_measurement.pdf)
- Findings (top-100K stateful crawl, 2016): doubleclick.net was the most prolific, sharing 108 different cookies with 118 other third parties. The share of top third parties that sync with at least one other party was 45 of the top 50, 85 of 100, 157 of 200 and 460 of 1,000. Among the top 50 syncing third parties, a random pair shares at least one cookie with 85% probability (66% for the top 100). — [OpenWPM paper](https://www.cs.princeton.edu/~arvindn/publications/OpenWPM_1_million_site_tracking_measurement.pdf)
- OpenWPM's ID rules "build on the methods used in previous studies [1, 14]", where [1] is Acar et al. 2014 ("The Web Never Forgets"). The 2-machine / Ratcliff-Obershelp approach follows that lineage. — [OpenWPM paper](https://www.cs.princeton.edu/~arvindn/publications/OpenWPM_1_million_site_tracking_measurement.pdf)

**Papadopoulos et al., WWW 2019 ("Cookie Synchronization: Everything You Always Wanted to Know But Were Afraid to Ask"), CONRAD method**
- Step 1: parse all `Set-Cookie` headers, drop session cookies (no expiry), and split values on ":" and "&" to get candidate userIDs. — [arXiv HTML 1805.10505](https://arxiv.org/html/1805.10505v3)
- Step 2: look for ID-looking strings (more than 10 characters) in URL parameters, URL paths or the Referer. Store the first domain seen with each ID in a hashtable. The same ID seen at a different domain is an "ID-sharing" request. — [arXiv HTML](https://arxiv.org/html/1805.10505v3)
- Step 3: remove same-owner pairs (e.g. amazon.com and amazonaws.com) using WHOIS and lists. Step 4: if the shared string matches a cookie ID from step 1, the request is a CSync event. — [arXiv HTML](https://arxiv.org/html/1805.10505v3)
- Hashed or encrypted IDs: a decision-tree classifier trained on the plaintext results. Features: recipient entity, parameter name, ID location, status code, browser, parameter count. Accuracy is about 84-90% and AUC up to 0.978 with an ID-string pre-filter. The authors say it is not validated against ground truth for encrypted IDs. — [arXiv HTML](https://arxiv.org/html/1805.10505v3)
- Stats (850 real mobile users, 12 months, 179M HTTP requests; HTTP only):
  - 263,635 CSync requests; 97% of regular users exposed.
  - About 1 CSync per 68 requests.
  - The median userID is synced to 3.5 domains, and CSync multiplies the domains tracking a user by 6.75.
  - rubiconproject.com, 360yield.com and openx.net each learned over 30% of userIDs.
  - Ad-related domains took part in over 75% of CSyncs.
  
  — [arXiv HTML](https://arxiv.org/html/1805.10505v3); abstract at [arXiv 1805.10505](https://arxiv.org/abs/1805.10505)
- CONRAD reportedly detects 3.771% more CSync cases than earlier methods (Olejnik 2014, Acar 2014, Englehardt 2016). It extends detection to IDs placed in URL paths, not just query params. — [arXiv HTML](https://arxiv.org/html/1805.10505v3)

**Bashir et al., USENIX Security 2016 ("Tracing Information Flows Between Ad Exchanges Using Retargeted Ads")**
- Uses retargeted ads as a ground-truth signal for information flow between ad exchanges. Based on 35,448 crawled ad impressions, it categorises 4 kinds of sharing (cookie matching is one) and finds cases "where existing heuristic methods fail" (i.e. server-side flows invisible to URL/ID matching). — [arXiv 1811.00920](https://arxiv.org/abs/1811.00920); [USENIX page](https://usenix.org/conference/usenixsecurity16/technical-sessions/presentation/bashir)
- A secondary slide deck claims 31% of cookie-matching partners cannot be identified by heuristics. This is unverified against the paper. — [SJTU slides](https://nsec.sjtu.edu.cn/teaching/assets/2017spring/presentation/big-data-privacy/slides/Youjing-Lu.pdf)

**Google cookie matching (exact URL formats, official docs)**
- Bidder-initiated: `https://cm.g.doubleclick.net/pixel?google_nid=BIDDER_ACCOUNT_NID&google_cm`. Google then redirects to the bidder's URL with `google_gid=<web-safe base64 Google user ID>&google_cver=1`. On failure it sends `google_error=<n>` (e.g. `google_error=3` = user has no Google cookie). — [Google Authorized Buyers cookie guide](https://developers.google.com/authorized-buyers/rtb/cookie-guide)
- Google-initiated: `https://ad.network.com/pixel?google_gid=GOOGLE_GID&google_cver=1&google_push=PUSH_DATA`. The bidder redirects back to `cm.g.doubleclick.net/pixel?google_nid=...&google_push=PUSH_DATA`. — [Google cookie guide](https://developers.google.com/authorized-buyers/rtb/cookie-guide)
- Other params: `google_hm` (bidder's own ID as web-safe base64, ≤40 bytes decoded, stored in a Google-hosted match table) and `google_ula` (add user to a list). `google_cm` and `google_push` never appear in the same request. — [Google cookie guide](https://developers.google.com/authorized-buyers/rtb/cookie-guide)

**Prebid.js user sync and userId module**
- `userSync` config defaults:
  - `syncEnabled: true`
  - image syncs on, iframe syncs off unless `filterSettings.iframe` is set
  - `syncsPerBidder: 5`
  - `syncDelay: 3000` ms after the auction
  - `auctionDelay: 500` ms (0 before Prebid 9.0) to wait for userId modules
  - `enableOverride` lets the page call `pbjs.triggerUserSyncs()`
  
  — [Prebid setConfig docs](https://docs.prebid.org/dev-docs/publisher-api-reference/setConfig.html)
- Prebid docs say syncs do not fire in Safari, in Firefox/Chrome on iOS (since 11.9), "or when cookies are disabled or denied". So syncs that fire after "Reject all" mean the CMP-to-Prebid consent wiring did not stop them. — [Prebid setConfig docs](https://docs.prebid.org/dev-docs/publisher-api-reference/setConfig.html)
- userId module: each submodule stores its ID via `storage: {type: "cookie"|"html5"|"cookie&html5", name, expires}`. Opt-out keys are `_pbjs_id_optout` and `_pubcid_optout`. IDs reach bidders as `bidRequest.userIdAsEids` (ORTB EIDS format) and as `user.ext.eids` in Prebid Server / OpenRTB requests. — [Prebid userId docs](https://docs.prebid.org/dev-docs/modules/userId.html)
- EID `source` values in the docs include id5-sync.com, pubcid.org, sharedid.org, liveramp.com, uidapi.com (UID2), criteo.com, liveintent.com, adserver.org, neustar.biz, yahoo.com, 33across.com, esp.pubmatic.com. Example shape: `{"source":"id5-sync.com","uids":[{"id":"ID5-12345","atype":1,...}]}`. — [Prebid userId docs](https://docs.prebid.org/dev-docs/modules/userId.html)

### Inferences
- **Feasible rule (A1, generic):**
  1. Collect candidate IDs from every cookie (Playwright `context.cookies()` plus `Set-Cookie` response headers) and from localStorage.
  2. Split values on non-`[A-Za-z0-9_\-=]` chars (OpenWPM) and also on `:`/`&` (CONRAD).
  3. Keep tokens with 8 ≤ len ≤ 100, expiry > 90 days, not purely numeric timestamps (10/13-digit epoch near now), not URLs, not common words.
  4. For every request, search URL path+query (raw and percent-decoded, plus base64-decoded params), the Referer header, the response `Location` header and the postData for each candidate.
  5. A hit counts when the request's eTLD+1 differs from the cookie's owner domain and from the site under audit (after an entity map such as Tracker Radar's `entities`).
  6. Apply OpenWPM's direction rules above.
- **Optional rule (A2, 2-run uniqueness):** OpenWPM's rule (4) needs two runs. A cheaper option for a hackathon is two fresh Playwright contexts in sequence. Keep only values that differ between contexts (Ratcliff-Obershelp via Python `difflib.SequenceMatcher(None,a,b).ratio() < 0.66`, the same algorithm family). This removes constants like `"true"` or site version strings.
- **Rule A3 (endpoint signatures), for higher confidence and less noise:** treat as cookie-sync evidence any request to:
  - `cm.g.doubleclick.net/pixel` with `google_nid`, `google_cm`, `google_push` or `google_hm` (cited above)
  - any URL containing `google_gid=` (Google-initiated push to a partner, cited above)
  - URL paths matching `/(usersync|user-sync|user_sync|setuid|getuid|cookiesync|cookie_sync|cm|match|sync|pixel_sync|cksync)\b`, plus query keys like `uid`, `buyeruid`, `partner_uid`, `puid`, `external_user_id`, `redir`, `gdpr`, `gdpr_consent`, `us_privacy` (general knowledge, unverified this session)
  - examples (general knowledge, unverified): `pixel.rubiconproject.com/exchange/sync.php`, `ib.adnxs.com/getuid?<redirect with $UID>`, `image2.pubmatic.com/AdServer/Pug?...`, `ups.analytics.yahoo.com`, `sync.1rx.io`, `ssum-sec.casalemedia.com`, `match.adsrvr.org`, `x.bidswitch.net/sync`, `eb2.3lift.com/getuid`.
- **Rule A4 (Prebid eids):**
  - Parse JSON postData of bid requests (OpenRTB to `/openrtb2/auction` or adapter endpoints).
  - Look for `user.ext.eids[].source` / `.uids[].id`, or `userIdAsEids`. Any non-empty eids after "Reject all" is strong evidence that cross-site identity graph IDs (ID5, UID2, RampID, SharedID) were sent.
  - Also check the `gdpr_consent` TCF string (if present) vs the reject choice.
  - Cookie/localStorage names such as `_pubcid`, `id5id`, `__uid2_advertising_token`, `idl_env`, `_sharedid` are common defaults (general knowledge, unverified; the Prebid doc page only showed publisher-chosen names).
- **Redirect chains:** Playwright gives `request.redirected_from`/`redirected_to` and `response.headers['location']`. Record each 30x hop. A sync chain is A → 302 → B?uid=<A's id> (→ 302 → A?partner=B&uid=<B's id>). Following the chain lets you report both directions.
- **False-positive pitfalls:**
  - Same-owner domains (google-analytics/doubleclick/googlesyndication; facebook/fbcdn). Use an entity map.
  - The site's own session IDs or CSRF tokens leaking via Referer. These are "accidental ID sharing" (OpenWPM caveat). Still a leak, but label it "ID leaked via Referer", not "cookie sync".
  - Consent strings (TCF `euconsent-v2`, `gdpr_consent`) are long and identical across users with the same choices. Exclude these names, or rely on the 2-run test.
  - Timestamps, cache-busters (`cb=`, `rnd=`), hashes of the page URL, and A/B bucket IDs.
  - Hashed or encrypted IDs (CONRAD) are missed by string matching. Endpoint signatures (A3) partly cover this.
  - Server-side syncs and RTB bid-stream sharing (Bashir) are invisible to a browser. Say so in the report as a limitation.
- **Cross-site linkage:** cookie syncing directly lets the receiving third party map its own long-lived ID to the sender's ID, and those IDs are the same across every site where either party is embedded. Evidence is strongest when the same third-party ID value is seen on two different audited sites (possible only if third-party cookies persist across sites within one Playwright context). Chromium in Playwright still allows third-party cookies by default unless configured otherwise (general knowledge, unverified).

### Gaps
- Could not fetch the Acar et al. 2014 full text this session. Its exact rules are only known indirectly (OpenWPM says it builds on them).
- Bashir et al.'s exact share of flows missed by heuristics was not confirmed (the 31% figure comes only from secondary slides).
- No primary source verified this session for vendor-specific sync URLs (Rubicon, AppNexus, PubMatic, Casale, Trade Desk). They are general knowledge.
- Exact default storage key names for each Prebid ID submodule were not confirmed (they are in per-submodule doc pages, not fetched).

## B. Link decoration, navigational tracking, bounce tracking and UID smuggling

### Takeaway
UID smuggling (a user ID in a navigation URL's query string, often via redirectors such as adclick.g.doubleclick.net) was found on about 8% of navigations in Randall et al. (IMC 2022). Bounce tracking (a redirect through a tracker that sets storage, with no UID in the URL) was found on 2.7% of paths. A passive auditor can detect both by (1) parsing outbound `<a href>`s for known click-ID/decoration params and redirector URLs, and (2) clicking a few links and recording the full navigation redirect chain (30x and JS redirects), plus which hops set cookies. Proving a value is a *user* ID (not a session ID or constant) needs a 2-profile comparison like CrumbCruncher's.

### Cited Findings

**Randall et al., "Measuring UID Smuggling in the Wild", IMC 2022 (UCSD + Brave), CrumbCruncher**
- Definition: UID smuggling "modifies a user's navigation requests by adding information to the navigation URLs in the form of query parameters." This lets trackers link users across sites despite partitioned storage. — [Brave research page](https://brave.com/research/measuring-uid-smuggling-in-the-wild/); [UCSD PDF](https://www.sysnet.ucsd.edu/~voelker/pubs/uid-smuggle-imc22.pdf)
- Crawler setup:
  - Puppeteer + a Chrome extension recording requests, headful under XVFB, third-party cookies disabled.
  - 4 crawlers: Safari-1, Safari-2 and Chrome-3 are 3 different "users"; Safari-1R repeats Safari-1 as the same user.
  - 10-step random walks from Tranco top-10K seeders, 10 s dwell per page.
  - A central controller makes all crawlers click the same element, matched by href ignoring the query string, by property names plus bounding box, or by x-path.
  
  — [ar5iv 2203.10188](https://ar5iv.labs.arxiv.org/html/2203.10188)
- Token = any value in a name-value pair (cookie, localStorage, query param), recursively parsed as JSON or URL-encoded. Only tokens passed across at least one different registered domain as a query parameter are kept. — [ar5iv](https://ar5iv.labs.arxiv.org/html/2203.10188)
- UID classification:
  - Discard tokens identical across different-user crawlers (constants).
  - Discard tokens that differ between Safari-1 and Safari-1R (session IDs).
  - In the dynamic case, also drop dates/timestamps, URLs and tokens shorter than 7 characters (the paper elsewhere says 8, which is inconsistent).
  - Manually remove natural-language strings, coordinates, domains and acronyms (577 of 1,581 tokens removed).
  
  The authors did not use a lifetime filter, noting a 90-day rule would have dropped 16% of UIDs. — [ar5iv](https://ar5iv.labs.arxiv.org/html/2203.10188)
- Results:
  - 10,814 unique URL paths; UID smuggling on 850 (reported 8.11%; "more than eight percent of all navigations"). Note 850/10,814 ≈ 7.9%, so the denominator may differ.
  - 214 unique redirectors (27 dedicated, 187 multi-purpose). 11 of 27 dedicated smugglers (41%) were missing from the Disconnect list.
  - Bounce tracking without a UID in the URL appeared on 2.7% of paths.
  
  — [ar5iv](https://ar5iv.labs.arxiv.org/html/2203.10188)
- Top redirectors in smuggling paths: adclick.g.doubleclick.net (11.2%), googleads.g.doubleclick.net (6.2%), advance.lexis.com (3.1%), d.agkn.com (2.8%), btds.zog.link (2.8%), ad.doubleclick.net (2.5%), gm.demdex.net (2.5%, Adobe). DoubleClick appears in over 20% of cases. — [ar5iv](https://ar5iv.labs.arxiv.org/html/2203.10188)
- "Dedicated smuggler" definition: a redirector seen in paths with multiple originators and multiple destinations, whose FQDN is never itself an originator or destination. — [ar5iv](https://ar5iv.labs.arxiv.org/html/2203.10188)
- Defences surveyed:
  - Safari deletes storage set by redirectors without user interaction.
  - Firefox clears storage of Disconnect-listed sites after 24 h unless visited first-party within 45 days.
  - Brave skips redirectors by jumping to the destination found in the query, strips a list of known smuggling params, and clears storage on tab close.
  - Privacy Badger unwraps redirector links; uBlock Origin shows an interstitial.
  
  — [ar5iv](https://ar5iv.labs.arxiv.org/html/2203.10188)

**Browser mitigations (current state)**
- Chrome bounce tracking mitigations: Chrome "will monitor navigations and internally flag sites that are part of a 'bounce'" (server and client/JS redirects). If the flagged site has had no user interaction in the last 45 days and third-party cookies are blocked, "the site storage will be deleted shortly after the next redirection flow is triggered through this site." Launched by default in October 2023, but only for users who opted in to blocking third-party cookies. It is "not a goal to enable these mitigations when third-party cookies are enabled." SSO, payments and Privacy Sandbox storage are out of scope. — [Google Privacy Sandbox: bounce tracking mitigations](https://privacysandbox.google.com/protections/bounce-tracking-mitigations)
- Firefox Query Parameter Stripping: enabled in release under ETP Strict and in private browsing, with a short list that includes fbclid. Nightly uses an extended list delivered via Remote Settings, and there is an allow-list of exempt sites. Whether gclid is stripped in release could not be confirmed. — [Firefox source docs: Query Stripping](https://firefox-source-docs.mozilla.org/toolkit/components/antitracking/anti-tracking/query-stripping/index.html)
- Safari Link Tracking Protection (Safari 17 / iOS 17, 2023): strips known click IDs in Private Browsing, Mail and Messages. A secondary source says the list includes gclid, dclid, fbclid, msclkid, mc_eid and igshid, and UTM params are left alone. — [MacRumors 2023](https://www.macrumors.com/2023/06/17/safari-link-tracking-protection/); [Medium post](https://medium.com/@auignatenko/safari-vs-utm-do-we-really-need-to-panic-96e2e2c7ed78). A single 2026 secondary source claims Safari 27 adds xmt, si, twclid, cn, cxt (unverified). — [Taggrs](https://taggrs.io/safari-27-tracking-protection/)

### Inferences
- **Parameter list for a detector** (general knowledge of vendor docs, unverified this session):
  - `gclid`, `gbraid`, `wbraid`, `gclsrc`, `dclid`: Google Ads / Campaign Manager
  - `_gl`: Google cross-domain linker. It carries the GA client ID and `_gcl_*` values, so it is a direct first-party-ID smuggle between the site's own domains
  - `fbclid`: Meta
  - `msclkid`: Microsoft Ads
  - `ttclid`: TikTok
  - `twclid`: X
  - `li_fat_id`: LinkedIn
  - `mc_eid`: Mailchimp per-subscriber ID, effectively an email-linked ID
  - `mc_cid`: campaign
  - `_hsenc`, `_hsmi`, `__hssc`, `__hstc`, `__hsfp`: HubSpot
  - `igshid`: Instagram share
  - `yclid`: Yandex
  - `epik`: Pinterest
  - `s_kwcid`, `ef_id`: Adobe
  - `mkt_tok`: Marketo
  - `oly_enc_id`, `oly_anon_id`: Omeda
  - `vero_id`, `wickedid`, `rb_clickid`
  - `irclickid`: Impact
  - `cjevent`: CJ affiliate
  - `ranMID`, `ranSiteID`: Rakuten
  
  `utm_*` are campaign labels, not user IDs. Do not flag them as UIDs.
- **Feasible rule B1 (static, no clicking):**
  1. After "Reject all", run `page.eval_on_selector_all('a[href]', 'els => els.map(e => e.href)')`.
  2. Parse each href. If it points to another eTLD+1 and carries a param from the list above, or any param whose value is ID-like (len ≥ 8, high entropy, not a URL or date) and matches a cookie/localStorage value on this site, flag "link decoration: <param> appended to outbound link to <domain>".
  3. Also flag hrefs whose host is a known redirector (adclick.g.doubleclick.net, googleads.g.doubleclick.net, ad.doubleclick.net, gm.demdex.net, d.agkn.com, click trackers like `*.awin1.com`, `go.redirectingat.com`, `t.co`, `l.facebook.com/l.php`, `out.reddit.com`) and contain an encoded destination URL (`url=`, `adurl=`, `u=`, `dest=`, `redirect=`).
  4. JS decorates links at click time (the GA4 linker adds `_gl` on mousedown). So also hook `mousedown`/`click`, or simply click and read the navigation request URL.
- **Feasible rule B2 (dynamic, clicking a few links):**
  1. For each clicked outbound link, record the request chain of the main-frame navigation: `request.redirected_from` chain plus `response.status` 30x plus `Location`, plus client-side redirects (consecutive main-frame `framenavigated` events within ~5 s without user action).
  2. Flag **bounce tracking** when an intermediate hop's eTLD+1 differs from both the origin and the destination AND (it sets a cookie via `Set-Cookie`, or JS storage while on that page) AND the user never interacted with it. This mirrors the Chrome/Safari definitions.
  3. Flag **UID smuggling** when any query value in the navigation chain equals (or contains, URL- or base64-decoded) an ID-like cookie/localStorage value from the origin site or from an intermediate hop, and crosses eTLD+1.
- **Feasible rule B3 (2-profile check, optional):** repeat the same click in a second fresh context. Values that differ across contexts but stay stable when the same context repeats the click are UIDs (the CrumbCruncher logic). Values that change every time are session or nonce values.
- **Pitfalls:**
  - Session IDs, CSRF tokens, search query strings, product SKUs and pagination tokens.
  - Affiliate IDs, which are publisher IDs, not user IDs. The paper notes affiliate attribution as a legitimate use.
  - SSO/OAuth redirects (`state`, `code`, `nonce`), payment flows and consent-sync redirects.
  - Same-entity redirects (google.com → google.co.uk).
  - Sites behind Cloudflare challenges cause redirects that are not tracking.
  - Clicking ads may count as an ad interaction/fraud. Prefer non-ad outbound links, or only inspect ad hrefs statically (keep it passive).
- **Cross-site linkage:** UID smuggling and `_gl`/click IDs carry an identifier from site X into site Y's first-party context. So the destination (and the redirector) can join X-side and Y-side profiles. This is cross-site evidence even when third-party cookies are blocked. Bounce tracking gives the redirector a first-party cookie on its own domain each time the user passes through, from any origin site, so it can link sites too. A single-site audit can show the capability (the ID leaves site X, or the redirector sets a long-lived cookie). Proving the same ID turns up on site Y requires following the click.

### Gaps
- The full list of smuggling parameter names from the IMC paper was not obtained (the paper says it publishes them in its dataset).
- Current exact contents of the Firefox (Remote Settings) and Safari strip lists were not verified. PrivacyTests.org is suggested as a checking source.
- Chrome's later changes (2024-2025: e.g. whether bounce tracking mitigations broadened after Google kept third-party cookies by default) were not found in the fetched page. The page gave no version numbers.

## C. CNAME cloaking

### Takeaway
CNAME cloaking is fully detectable from Python:
1. Take every request host that shares the audited site's eTLD+1 but is not the page origin.
2. Resolve its CNAME chain (dnspython).
3. Flag it if any chain member's eTLD+1 differs from the site and matches a CNAME-tracker list (AdGuard cname-trackers, NextDNS cname-cloaking-blocklist) or known vendor suffixes (omtrdc.net, data.adobedc.net, eulerian.net, pardot/salesforce, eloqua, at-o.net, wt-eu02.net, etc.).

This matters legally because cookies scoped to the first-party domain (including other vendors' IDs and sometimes auth cookies) are sent automatically to the tracker. Dimova et al. found cookie leaks on 95% of sites using CNAME trackers. Server-side tagging and first-party proxies that use A/AAAA records (no CNAME) cannot be reliably detected from DNS alone.

### Cited Findings

**Dimova, Acar, Olejnik, Joosen, Van Goethem, "The CNAME of the Game", PETS 2021**
- Discovery method:
  1. From HTTP Archive, take requests that are same-site but not same-origin (same eTLD+1, different origin) and whose hostname has a CNAME record pointing, directly or via a chain, to a different eTLD+1 (DNS resolved with zdns).
  2. Aggregate by the CNAME target eTLD+1 and keep targets seen on 100 or more websites: 46,767 → 120 candidates.
  3. Manually vet each one (rule out CDNs; e.g. Cloudflare's `__cfduid` is not tracking). Confirm tracking only when "a uniquely identifying parameter is stored in the browser and sent along with subsequent requests".
  
  This gave 5 trackers, plus 8 more from the NextDNS CNAME list, for 13 in total. — [CNAME of the Game PDF](https://arxiv.org/pdf/2102.09301) / [arXiv abstract](https://arxiv.org/abs/2102.09301)
- They built per-tracker request signatures (DNS plus the same JS resource or URL pattern) to avoid false positives from vendors' non-tracking services. Relying solely on DNS data "leads to an overestimation". — [CNAME of the Game PDF](https://arxiv.org/pdf/2102.09301)
- Prevalence: "9.98% of the top 10,000 websites employ at least one CNAME-based tracker". 10,474 eTLD+1s had a subdomain pointing to a CNAME tracker (HTTP Archive, Oct 2020). Usage is heavily biased towards popular sites and growing. — [CNAME of the Game PDF](https://arxiv.org/pdf/2102.09301)
- Table 1 (detected publishers, Oct 2020):

  | Vendor | Detected publishers |
  |---|---|
  | Pardot | 5,993 |
  | Adobe Experience Cloud | 2,612 |
  | Act-On | 1,041 |
  | Oracle Eloqua | 304 |
  | Eulerian | 253 |
  | Webtrekk | 101 |
  | TraceDock | 49 |
  | Ingenious Technologies | 41 |
  | AT Internet | 31 |
  | Criteo | 16 |
  | <intent> | 14 |
  | Keyade | 12 |
  | Wizaly | 12 |

  Some (Oracle Eloqua, Eulerian, Criteo, Keyade) are blocked by uBlock Origin on Firefox but not Chrome. Firefox uBO can resolve CNAMEs; Chrome extensions cannot. — [CNAME of the Game PDF](https://arxiv.org/pdf/2102.09301)
- Criteo used first-party CNAME tracking only for Safari users (UA-dependent). An auditor running Chromium may therefore miss Criteo cloaking. — [CNAME of the Game PDF](https://arxiv.org/pdf/2102.09301)
- Domain drift: Eulerian moved from `.ca-eulerian.net` to `.eulerian.net`, and Adobe added `data.adobedc.net` (Oct 2020). Some publishers left dangling CNAMEs. Eulerian uses the IP range 109.232.192.0/21, so IP-range matching is a backup when CNAMEs are flattened. — [CNAME of the Game PDF](https://arxiv.org/pdf/2102.09301)
- Cookie leaks: on 7,377 of 7,797 sites (95%) with a CNAME tracker, cookies set by other parties were sent to the CNAME subdomain. 31K of 35K leaks came from third-party analytics scripts' first-party cookies.
  - Their exclusions: cookies set by the CNAME tracker itself, session cookies, short cookies, and cookies seen on multiple sites.
  - They also found leaks in POST bodies (cookie values sent by the tracker's script) and 1,899 cookie leaks in request URLs (searched in URL-decoded URLs excluding scheme and host).
  - On 13 sites sensitive data leaked, including full name, email and authentication cookies (10 sites).
  
  — [CNAME of the Game PDF](https://arxiv.org/pdf/2102.09301)
- Security: two vendor vulnerabilities (session fixation via a cookie-lifetime-extension feature, and persistent XSS) affected all publishers using them ("several hundreds of websites"). Cookies set with the parent `Domain` attribute are attached to all subdomains, so a tracker bug becomes a site-wide bug. — [CNAME of the Game PDF](https://arxiv.org/pdf/2102.09301)
- Dao et al. (TMA 2020, with ANSSI):
  - Method: crawled the Alexa top 300K with OpenWPM, resolved CNAME chains for each subdomain, and matched every chain node against EasyPrivacy/AdGuard with wildcard/regex. "If any node in a chain was flagged, the chain was classed as tracking."
  - Results: 1,762 sites and 56 providers.
  - Protection tests: Brave blocked about 50% of cases; uBlock Origin about 70% (Firefox CNAME-aware version best).
  
  — [APNIC blog, 2020](https://blog.apnic.net/2020/08/04/characterizing-cname-cloaking-based-tracking/)
- Ren et al. (NDSS MADWeb 2021) found first-party cookies, including authentication cookies, sent to third parties due to CNAME redirections on the Alexa top 10K. — [MADWeb 2021 paper](https://www.ndss-symposium.org/wp-content/uploads/madweb2021_23018_paper.pdf)
- AdGuard cname-trackers repo (MIT):
  - Categories: ads, clickthroughs, microsites, trackers, mail_trackers.
  - Files: `data/combined_original_trackers.txt` (the original tracker domains that CNAMEs point to), `data/combined_disguised_{category}.txt` (adblock syntax), `..._justdomains.txt`, `..._rpz.txt`. Auto-updated "on a regular basis".
  
  — [AdGuard cname-trackers](https://github.com/AdguardTeam/cname-trackers)

### Inferences
- **Feasible rule C1:**
  1. `site = tldextract(top_url).registered_domain`.
  2. `hosts = {h for req in requests if registered_domain(h)==site and h != page_host}`.
  3. For each host, follow CNAMEs with `dns.resolver.resolve(h, 'CNAME')`, iterating (max ~10 hops). Or call `resolve(h,'A')` and read `answer.response.answer` for the CNAME RRsets.
  4. If any target's registered domain ≠ site, check it against (a) AdGuard `combined_original_trackers.txt` (suffix match), (b) the NextDNS cname-cloaking-blocklist, (c) Tracker Radar domain/entity data (Tracker Radar includes CNAME info per domain; general knowledge, unverified this session), (d) the hardcoded suffixes below.
  5. On a match, record `{subdomain, cname_chain, vendor, cookies_sent: [names from the request's Cookie header], set_cookies}`.
- **Hardcoded vendor suffixes** (beyond the Table 1 vendors; general knowledge, unverified this session, check against the AdGuard list):

  | Vendor | Suffixes |
  |---|---|
  | Adobe | `omtrdc.net`, `sc.omtrdc.net`, `data.adobedc.net`, `2o7.net` |
  | Eulerian | `eulerian.net` |
  | AT Internet / Piano | `at-o.net`, `xiti.com` |
  | Webtrekk / Mapp | `wt-eu02.net`, `webtrekk.net` |
  | Oracle Eloqua | `eloqua.com` |
  | Pardot | `pardot.com`, `go.pardot.com` (via `pi.pardot.com`) |
  | Act-On | `actonsoftware.com` |
  | Criteo | `dnsdelegation.io`, `storetail.io` |
  | Commanders Act | `tagcommander.com` |
  | Keyade | `k.keyade.com` |
  | TraceDock | `tracedock.com` |
  | Wizaly | `wizaly.com` |
  | Ingenious | `affex.org` |
  | Others | `actonservice.com`, `mktoweb.com` (Marketo landing pages: borderline, often clickthrough/microsite) |
- **Severity signal:** list which cookies were sent to the cloaked host that were *not* set by it, e.g. `_ga`, `_fbp`, session or auth cookies. That is the Dimova "cookie leak" definition. Also check whether those cookies lack `HttpOnly` (the tracker JS can read them too).
- **Server-side GTM / first-party proxies:**
  - sGTM on `metrics.example.com` usually uses A records to Google Cloud Run/App Engine or a custom IP (sometimes a CNAME to `*.run.app`, `ghs.googlehosted.com`, or Stape `*.stape.io`), so CNAME-list matching often fails.
  - Partial detection is still possible from request signatures: paths like `/g/collect?v=2&tid=G-...` (GA4 Measurement Protocol) or `/gtm.js?id=GTM-...` served from a first-party subdomain, `/gtag/js` on a non-Google host, Meta CAPI gateways, `_fbp` sent to a first-party collector, or Adobe `/b/ss/` (AppMeasurement) and `/ee/v1/interact` (Web SDK edge) paths on first-party hosts.
  - Data forwarded server-to-server from there is invisible. Report it as "first-party collector forwarding to Google (likely)", not as proof.
  
  (General knowledge, unverified this session.)
- **Pitfalls:**
  - CDNs (Cloudflare, Akamai `edgekey.net`, Fastly, CloudFront) and SaaS hosting (Shopify, HubSpot CMS, Zendesk) are normal CNAME targets. Only flag list matches.
  - Marketing landing-page hosts (`go.` → Pardot/Marketo) may be "microsites/clickthroughs", not trackers. Use AdGuard's category.
  - Dangling CNAMEs and NXDOMAIN.
  - DNS answers vary by resolver or geography. Record the resolver used.
  - CNAME flattening at the apex hides the chain; fall back to an IP-range check, e.g. Eulerian 109.232.192.0/21.
  - UA-dependent deployment (Criteo with Safari) means Chromium can miss it.
- **Legal angle:** cookies on the cloaked subdomain count as "first-party" to browsers (they escape ITP and third-party-cookie blocking). But the recipient is a separate controller or processor. Sending them after "Reject all" is the same consent problem as a third-party tracker (ePrivacy Art. 5(3)), and it may hide the recipient from the policy's list. Auth cookie leaks are a GDPR Art. 32 security issue (supported by the Dimova vulnerabilities).
- **Cross-site linkage:** a CNAME tracker's cookie is scoped per publisher, so on its own it links within one site. But vendors receive the leaked cookies of other parties (e.g. `_fbp`, `_ga`). Some vendors also sync between their third-party domain and the CNAME subdomain: Dimova found 378 cases where the leaked cookie was set by the tracker's own third-party domain (cookie-syncing-like behaviour). Treat that as cross-site evidence only when the same ID value is seen at both the vendor's third-party domain and the cloaked subdomain.

### Gaps
- Could not open the NextDNS cname-cloaking-blocklist repo or Tracker Radar CNAME docs this session. Formats are not verified.
- The specific Dao et al. 2021 follow-up (journal/longitudinal) paper was not located. The APNIC blog does not name all co-authors.
- No 2024-2026 prevalence numbers for CNAME cloaking were found. The 9.98% figure is from Oct 2020 data.
- No authoritative source checked for detecting sGTM/first-party proxies. The sGTM notes above are general knowledge.

## D. Which mechanisms show the SAME user linked across DIFFERENT sites?

### Takeaway
Strongest cross-site evidence, in order:
1. Cookie syncing / ID syncing: an ID mapping between two third parties whose cookies are global across sites, plus Prebid eids with global identity IDs (ID5, UID2, RampID).
2. UID smuggling and link decoration: an ID moved from site X into site Y's URL.
3. Bounce tracking: a redirector gets first-party storage on every pass.

CNAME cloaking alone is mostly per-site, unless leaked cross-site cookies (`_fbp`, synced IDs) or vendor-side syncing are observed.

### Cited Findings
- Cookie syncing "allows different trackers to share user identifiers with each other" and "enables back-end server-to-server data merges hidden from public view". — [OpenWPM paper](https://www.cs.princeton.edu/~arvindn/publications/OpenWPM_1_million_site_tracking_measurement.pdf)
- The median synced userID leaks to 3.5 domains, and CSync multiplies the domains tracking a user by 6.75. — [Papadopoulos et al.](https://arxiv.org/abs/1805.10505)
- UID smuggling links users across sites despite partitioned storage. — [Brave research](https://brave.com/research/measuring-uid-smuggling-in-the-wild/)
- Chrome's bounce mitigation is only meaningful when third-party cookies are blocked, and is not enabled when they are allowed. So in default Chrome (third-party cookies on), classic third-party cookies plus syncing remain the main cross-site linkers. — [Privacy Sandbox](https://privacysandbox.google.com/protections/bounce-tracking-mitigations)
- CNAME trackers set their cookies in a same-site context, so they evade third-party cookie blocking. 378 leaked cookies were set by the tracker's third-party domain, which shows cross-context ID transfer. — [CNAME of the Game PDF](https://arxiv.org/pdf/2102.09301)

### Inferences
- To show cross-site linkage within one audit run:
  1. Audit 2+ sites in the same Playwright context (third-party cookies kept).
  2. Report any third-party ID value (or synced ID) seen on both sites, sent to the same or different trackers.
  3. Within a single-site audit, report the "capability" instead: a long-lived third-party ID, plus a sync to N partners, plus eids sources. Wording: "allows X to link your visit here with visits to other sites using X".
- Keep wording precise for the complaint letter. "Observed: ID `abc…` set by A was sent to B (302 from A to B with uid=…)" is fact. "B can therefore recognise this browser on other sites where B is present" is inference, and should be labelled as such.

### Gaps
- No source quantifies how often a single-site browser observation is enough to prove cross-site linkage (server-side matching is invisible, per Bashir et al.).
