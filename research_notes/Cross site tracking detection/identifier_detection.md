# Identifier-based detection of cross-site tracking (passive Playwright auditor)

Source URLs used throughout:
- [Acar et al. 2014, "The Web Never Forgets", CCS'14](https://securehomes.esat.kuleuven.be/~gacar/persistent/the_web_never_forgets.pdf) (cited below as ACAR14)
- [Englehardt et al. 2015, "Cookies that give you away", WWW'15](https://senglehardt.com/papers/www15_cookie_surveil.pdf) (CGYA15)
- [Englehardt & Narayanan 2016, "Online Tracking: A 1-million-site Measurement and Analysis", CCS'16](https://www.cs.princeton.edu/~arvindn/publications/OpenWPM_1_million_site_tracking_measurement.pdf) (OWPM16)
- [Papadopoulos et al. 2019, "Cookie Synchronization: Everything You Always Wanted to Know But Were Afraid to Ask", WWW'19, arXiv:1805.10505](https://arxiv.org/abs/1805.10505) (PAP19)
- [Fouad et al. 2020, "Missed by Filter Lists: Detecting Unknown Third-Party Trackers with Invisible Pixels", PETS'20, arXiv:1812.01514](https://arxiv.org/abs/1812.01514) (FOUAD20)
- [Chen et al. 2021, "Cookie Swap Party: Abusing First-Party Cookies for Web Tracking", WWW'21](https://spt.cut.ac.cy/papers/chen_www21.pdf) (CSP21)
- [Demir et al. 2022, "Towards Understanding First-Party Cookie Tracking in the Field", arXiv:2202.01498](https://arxiv.org/abs/2202.01498) (DEMIR22)
- [Munir et al. 2023, "CookieGraph: Understanding and Detecting First-Party Tracking Cookies", CCS'23, arXiv:2208.12370](https://arxiv.org/abs/2208.12370) (CG23)
- [Meta, fbp and fbc parameters (Conversions API docs)](https://developers.facebook.com/docs/marketing-api/conversions-api/parameters/fbp-and-fbc/)
- [martech.zone, GA4 request parameters (secondary)](https://martech.zone/google-analytics-image-pixel-variables/)

All quotes below come from the full PDF text, extracted with pdftotext.

## Q1. Exact ID-detection heuristics in the literature

### Takeaway
Every paper uses the same four-part test from Acar 2014: (1) the cookie is persistent (expires >1 month, later >90 days); (2) the value is long enough (≥8 chars; Englehardt 2016 caps it at 100); (3) the value stays the same within one crawl; (4) the value differs between two independent crawls (Ratcliff-Obershelp similarity below a cutoff of 33%, 55%, 60% or 66% depending on the paper). The values are first split on non-alphanumeric delimiters. The most-reused version is OWPM16's: >90 days, 8–100 chars, constant, <66% similar.

### Cited Findings
- **ACAR14 §4.1 "Detecting User IDs"** (2014), verbatim rule list: "Eliminate cookies that expire within a month of being placed." / "Parse cookie value strings using common delimiters (e.g. : and &)." / "Eliminate parsed fields which don't remain constant throughout an individual crawl." / "Compare instances of matching parsed cookie fields (for cookies with the same domain and name) between two unrelated crawls on different machines. – Eliminate fields which are not the same length. – Eliminate fields which are more than 33% similar according to the Ratcliff-Obershelp algorithm." The authors call it "strict and conservative" with "a very low false positive rate" (judged by manual inspection; no number given). They say it "applies to other storage locations of a similar format" (i.e. also localStorage / Flash). — [ACAR14](https://securehomes.esat.kuleuven.be/~gacar/persistent/the_web_never_forgets.pdf)
- ACAR14 lists its known false negatives: "ID strings that are obfuscated or embedded in longer strings using nonstandard delimiters or ID strings that happen to have a high similarity", and short-lived IDs that are rotated but mapped on the back end. — [ACAR14](https://securehomes.esat.kuleuven.be/~gacar/persistent/the_web_never_forgets.pdf)
- **CGYA15 §4.5** (2015): an identifier cookie is "(1) long-lived, with expiry times longer than three months … (2) It's value is stable, and remains constant through all page visits. Dynamic value strings may be timestamps or other non-identifiers. (3) Has a constant-length across all our datasets. (4) Is user-specific, so the values are unique across different browser instances … (5) Has a high-entropy value string … we used the Ratcliff-Obershelp algorithm … We filtered out all cookies with value strings that were more than 55% similar". It is "intentionally conservative, since false positives risk exaggerating the severity". "Entropy" here is checked by string dissimilarity, not by Shannon entropy. — [CGYA15](https://senglehardt.com/papers/www15_cookie_surveil.pdf)
- CGYA15 explains why the two crawls run in sync: "cookies with values that depend on time stamps will be easier to detect and ignore if the crawls have nearly the same timestamps for all actions." It then reuses the classified (host, name) pairs to pull IDs out of other crawls. — [CGYA15](https://senglehardt.com/papers/www15_cookie_surveil.pdf)
- **OWPM16 §4 "Detecting ID cookies"** (2016): values are parsed as "(name1 =)value1 |...|(nameN =)valueN where | represents any character except a-zA-Z0-9 -=". A (cookie-name, parameter-name, parameter-value) tuple is an ID cookie if "(1) the cookie has an expiration date over 90 days in the future (2) 8 ≤ length(parameter-value) ≤ 100, (3) the parameter-value remains the same throughout the measurement, (4) the parameter-value is different between machines and has a similarity less than 66% according to the Ratcliff-Obershelp algorithm. For the last step, we run two synchronized measurements … on separate machines". — [OWPM16](https://www.cs.princeton.edu/~arvindn/publications/OpenWPM_1_million_site_tracking_measurement.pdf)
- **CSP21 §3.3** (2021): "(i) The cookie should not be a session cookie … (ii) The length of the cookie's unquoted value is at least 8 characters (unquote converts URL-encoded %xx sequences …) (iii) The cookie is always set when visiting the website using different browser instances. (iv) The values of a cookie differ significantly across different visits to the same website using different browser instances." The refinement: "we compute the similarity scores only after … first removing all timestamps from the cookie values, and then all common subsequences having a length of more than 2 … applying the longest common subsequence (LCS) algorithm and removing the LCS from both values, and repeating until the LCS length is less than or equal to 2. The similarity score of the residual values are then computed using Ratcliff-Obershelp, and we set a cutoff value of 66%". This is needed because values like "{visitor_id: abcd, timestamp: 1234}" share common parts that skew the score. — [CSP21](https://spt.cut.ac.cy/papers/chen_www21.pdf)
- CSP21 §4.2.2 "Similar Value": some cookies failed only because their two-crawl values were >66% similar, e.g. `_ym_d` (a pure timestamp) and `smct_last_ov` (JSON with timestamps). — [CSP21](https://spt.cut.ac.cy/papers/chen_www21.pdf)
- **DEMIR22** (2022), using Koop et al.'s definition: "1. it is not a session cookie and has a lifetime of more than 90 days; 2. has a length of at least eight bytes (to hold enough entropy); 3. is unique in each measurement run, and the length of each value only differs by up to 25%; and 4. The values of the cookie are similar according to the Ratcliff/Obershelp string comparison algorithm (≤60%)." (The PDF says "similar … (≤60%)". Read in context, this means similarity ≤60%, i.e. dissimilar.) Values are URL-decoded and split "at common delimiters (e.g. , =, :, or ;)". — [DEMIR22](https://arxiv.org/abs/2202.01498)
- **FOUAD20 §2.2** (2020) drops the lifetime rule entirely: "we don't put any boundary on the cookie lifetime because domains can continuously update cookies with a short lifetime and do the mapping … on the server side". A cookie instance (host, key, value) that is identical in both crawls is a "safe cookie" (17.83% of instances). (host, name) pairs seen in only one crawl are "unknown" (8.56%) and excluded. 0.87% of cookie instances store the ID in the cookie *key*; these were excluded. — [FOUAD20](https://arxiv.org/abs/1812.01514)
- **CG23** (2023) only considers "cookie values that are at least 8 characters long". — [CG23](https://arxiv.org/abs/2208.12370)

### Inferences
- A good default for us is the OWPM16 rule, plus CSP21's timestamp/LCS stripping before the similarity test, plus FOUAD20's "identical in both runs → safe" shortcut. In Python, `difflib.SequenceMatcher(None, a, b).ratio()` is a Ratcliff/Obershelp implementation.
- Cutoffs got looser over time (33% in 2014 → 55% → 66%). Pick 66% to match OWPM16 and CSP21. Keep the 90-day rule as a "strong ID" flag, not a hard filter, since FOUAD20 says short-lived IDs can still track.

### Gaps
- None of these papers gives a measured precision/recall for the rule-based ID heuristic itself; it is only checked by manual inspection. CG23's numbers are for a different task (see Q6).

## Q2. The two-crawl differential method, and a cheap version

### Takeaway
The original method runs two synchronized crawls of the same sites on separate machines with fresh profiles. A value is a user ID if it stays constant within a crawl and differs between crawls. A cheap version: two fresh Playwright `browser.new_context()` contexts in one run (CSP21 already did two separate Chromium instances back-to-back).

### Cited Findings
- ACAR14: "two simultaneous crawls on separate machines"; parsed fields are matched on "the same domain and name" across the crawls. — [ACAR14](https://securehomes.esat.kuleuven.be/~gacar/persistent/the_web_never_forgets.pdf)
- OWPM16: "two synchronized measurements … on separate machines and compare the resulting cookies, as in previous studies." — [OWPM16](https://www.cs.princeton.edu/~arvindn/publications/OpenWPM_1_million_site_tracking_measurement.pdf)
- CGYA15: synchronized timing makes timestamp-valued cookies look alike in both crawls, so they get filtered out. — [CGYA15](https://senglehardt.com/papers/www15_cookie_surveil.pdf)
- CSP21 §3.5: "since the tracking cookie detection algorithm … requires two separate browser instances", each site was visited by two separate browser instances "immediately after the other", giving a "main" crawl and a second crawl. Each Chromium instance ran in its own Docker container. — [CSP21](https://spt.cut.ac.cy/papers/chen_www21.pdf)
- FOUAD20: two simultaneous stateful crawls from two machines; values identical across both are "safe", and pairs missing from one crawl are "unknown" and dropped. — [FOUAD20](https://arxiv.org/abs/1812.01514)

### Inferences
- Cheap version for our tool: for each site, run context A (main audit, browses several pages) and context B (fresh, incognito-like, landing page only, started right after A). For each (host, cookie name, sub-field) seen in both: identical → constant (drop); length differs by more than ~25% or similarity ≥ 0.66 after stripping timestamps → drop; otherwise → user ID. Within context A, any field that changes between page loads → nonce/session/timestamp (drop). Same machine and IP is fine: IDs are random per client and do not depend on IP. Caveat: server-side fingerprint-derived IDs could match across contexts and be missed (a false negative, which is acceptable).
- The same diff works for localStorage keys (read `page.evaluate("Object.entries(localStorage)")` in both contexts) and for URL/body parameter values, with (receiver host, param name) as the key.

### Gaps
- No paper reports how much error the same machine/IP adds compared with separate machines.

## Q3. Detecting the SAME identifier sent to a third party from different first-party sites

### Takeaway
Build a set of known ID values. Tokenise every request URL, referrer, Location header and body. When an ID value shows up at a receiver domain other than its owner, that domain "knows" the ID. Cross-site linkability is proven when one receiver gets the same ID while the user is on two or more different first-party sites, or when two domains both know one ID (syncing). Check plaintext, URL-decoded, base64 and hashed (MD5/SHA1/SHA256) forms.

### Cited Findings
- ACAR14 §5.1: "a telltale sign of cookie syncing is multiple domains owning cookies containing the same ID. Likewise, if an ID appears anywhere in a domain's URL string (e.g. in the URL parameters), then that domain also knows the ID." "We say that an ID is involved in synchronization if it is known by at least two domains." Direction is often not knowable: "third-party JavaScript executing a sync on a first-party site will cause the first-party to show up as the referrer", so they "focused on which domains knew a given ID". — [ACAR14](https://securehomes.esat.kuleuven.be/~gacar/persistent/the_web_never_forgets.pdf)
- OWPM16 §5.6 / Appendix 13.3: "look for instances of IDs in referer, request, and response URLs, accounting for URL encoding". Rules: "If the ID appears in the request URL: the requested domain is the recipient … If the ID appears in the referrer URL: the referring domain is the sender … and the requested domain is the receiver … If the ID appears in the location URL: the original requested domain is the sender … and the redirected location domain is the receiver." Caveat: this catches "both intentional and accidental ID sharing … should be interpreted only as an upper bound on cookie syncing". — [OWPM16](https://www.cs.princeton.edu/~arvindn/publications/OpenWPM_1_million_site_tracking_measurement.pdf)
- OWPM16 results: doubleclick.net "shares 108 different cookies with 118 other third parties"; 45 of the top 50 third parties sync. — [OWPM16](https://www.cs.princeton.edu/~arvindn/publications/OpenWPM_1_million_site_tracking_measurement.pdf)
- PAP19 §3.1 pipeline: extract Set-Cookie values; drop session cookies; split on "common delimiters (i.e. ':', '&')". Look for ID-looking strings "(i) as parameters in the URL, (ii) in URL path, or (iii) in the referrer field … strings with specific length (> 10 characters)". The first sighting is stored in a hashtable with the receiving domain; "If this ID has already been seen, we consider it as a shared ID". Same-owner domains are filtered (e.g. amazon.com/amazonaws.com) using whois/lists. The match is confirmed only if the ID is in the cookie-ID list. Limitation: "cookie IDs need to be shared in plaintext". — [PAP19](https://arxiv.org/abs/1805.10505)
- FOUAD20 §2.3: "We split cookies and URL parameter values using as delimiters any character not in [a-zA-Z0-9,'-','_','.']". Six techniques: ID as whole param value; as part of a param value; cookie-part sent as a param; GA sharing; Base64 sharing ("by base64 decoding the value of the parameter sent to doubleclick.net"); encrypted DoubleClick sharing. Limitation: "We do not inspect the payload of POST requests … google-analytics.com sends the identifier cookie as part of the URL parameters with GET requests or in the payload of the POST requests". — [FOUAD20](https://arxiv.org/abs/1812.01514)
- CSP21 §3.4 matching heuristics: (1) cookie name/value as a substring of the sink, or matched against extracted URL params; (2) split the value on special characters to catch concatenations "(e.g., value1.value2, value1_value2)"; (3) "applies the base64 encoding, and the MD5, SHA1, and SHA256 hashing algorithms both to the entire cookie value and the substrings". — [CSP21](https://spt.cut.ac.cy/papers/chen_www21.pdf)
- CG23 "monitors Base64-, MD5-, SHA-1-, and SHA-256- encoded cookie values in URLs, headers, request, and response bodies". It misses `_pin_unauth` because that value is "double-base64-encoded". — [CG23](https://arxiv.org/abs/2208.12370)
- CGYA15 builds a graph: URL nodes, and cookie nodes (C, value). URL–Cookie edges are added "whenever a cookie value is observed" in a request; page visits are linked only through shared cookie values. — [CGYA15](https://senglehardt.com/papers/www15_cookie_surveil.pdf)

### Inferences
- Implementation: `tokens(s)` = URL-decode repeatedly (max ~3 times), then `re.split(r'[^A-Za-z0-9_\-.]', s)`. Also keep sub-splits on `.` for GA-style values. Apply this to the query, path segments, fragment, Referer, Location, Cookie header and `postData` (JSON: walk all leaf strings; form-encoded: parse_qsl; text/plain beacons: split lines). For each candidate ID v, precompute {v, base64(v) (with and without padding, plus urlsafe), md5/sha1/sha256 hex of v} and look these up in an index of tokens. Also try base64-decoding tokens that are ≥16 chars and match `[A-Za-z0-9+/=_-]`.
- Cross-site proof in a single profile: run site X then site Y in the same context. Record (receiver eTLD+1, ID value, top-level site). A receiver getting the same third-party cookie value or token from ≥2 distinct top-level sites = proven linkability. Also, the same ID known by ≥2 different owner organisations = syncing. Use the Tracker Radar entity map to merge same-owner domains (PAP19's same-owner filter).

### Gaps
- No paper gives a single standard depth for encoding layers; CG23 shows double-base64 is missed.

## Q4. First-party cookie values sent to third parties (_ga, _fbp), and when that is cross-site

### Takeaway
First-party analytics IDs (GA `_ga`, Meta `_fbp`) are set by third-party scripts in the site's own cookie jar ("external" or "ghostwritten" cookies) and sent to the vendor. On their own they are per-site IDs: a different `_ga` value on each site. They become cross-site when the same request also carries a third-party cookie or a cross-site ID that the vendor can join on, or when the same value turns up at the vendor from several sites.

### Cited Findings
- FOUAD20: GA "first party cookies set by google-analytics.com have the format GAX.Y.Z.C, but the identifier sent to it are of the form Z.C"; earlier delimiter-based methods missed this (the "GA sharing" technique). — [FOUAD20](https://arxiv.org/abs/1812.01514)
- GA4 parameters (secondary source): `cid` = "Client ID, a unique identifier for the browser/device", example "1996059493.1705093317" (random.timestamp); `_p` = "Random number used to prevent caching of the request"; `sid` = "Session ID" (example "1707233357", epoch seconds); `uid` = optional ID for logged-in users across devices; `gcs` = "Google Consent State"; `gcd` = "Google Consent Details". — [martech.zone](https://martech.zone/google-analytics-image-pixel-variables/)
- Meta: "_fbp cookie, sent as the fbp parameter", format "version.subdomainIndex.creationTime.randomnumber", e.g. `fb.1.1596403881668.1116446470`; creation time "in milliseconds since the Unix epoch"; "_fbc … sent as the fbc parameter", format `fb.<idx>.<ms>.<fbclid>`. — [Meta docs](https://developers.facebook.com/docs/marketing-api/conversions-api/parameters/fbp-and-fbc/)
- CSP21: timestamps "are often paired with an additional random number … to form a unique tracking ID (e.g., Google Analytics' _ga cookie)". "57.66% of these websites" (those with external cookies) have at least one cookie with a unique ID that is diffused to multiple third parties. The paper's point is that trackers swap first-party IDs, which gets around third-party-cookie blocking. — [CSP21](https://spt.cut.ac.cy/papers/chen_www21.pdf)
- CG23: "96.61% of these first-party tracking cookies are in fact ghostwritten by third-party scripts embedded in the first-party context"; first-party tracking cookies "are shared with a large number of other domains immediately after being set". — [CG23](https://arxiv.org/abs/2208.12370)
- DEMIR22: first-party cookies "might hold an identifier to implement analytical or similar services, which are essentially a form of local user tracking". Tracking IDs are shared on average with 1.3 third parties, and 0.8% with more than [a larger number] (text truncated in extraction). — [DEMIR22](https://arxiv.org/abs/2202.01498)
- ACAR14: with third-party cookies blocked, "the top shared IDs come from … syncs which share a first party cookie with several third-party sites". — [ACAR14](https://securehomes.esat.kuleuven.be/~gacar/persistent/the_web_never_forgets.pdf)

### Inferences
- Matching rules: `_ga=GA1.<n>.<rand>.<ts>` → look for `<rand>.<ts>` as `cid` at `*.google-analytics.com/g/collect` (also `region1.`, and server-side GTM first-party collect endpoints). Also check `_ga_<container>` for session data. `_fbp` → look for the full `fb.1.<ms>.<rand>` value as `fbp=` at `facebook.com/tr`, or in a POST body.
- Escalate a first-party ID leak to "cross-site linkable" if: (a) the same request to the vendor carries a third-party cookie (e.g. the browser sends a Cookie header for `.facebook.com` or `.doubleclick.net`; use Playwright `request.all_headers()` to see Cookie), or (b) the same request carries a cross-site ID (e.g. a sync param, or a `uid` / hashed email), or (c) in the same profile the vendor gets an identical token from ≥2 top-level sites. Otherwise, report it as "per-site analytics ID sent despite rejection". That is still a consent/ePrivacy issue, but not proof of cross-site tracking.

### Gaps
- No primary Google documentation for the `/g/collect` parameters was fetched; the GA4 parameter meanings above come from a secondary blog. Treat `_p` as per-page random (a cache-buster) and exclude it.

## Q5. False-positive pitfalls and exclusion rules

### Takeaway
Most false positives fall into a few groups. Values that change within a run (nonces, cache-busters, timestamps, `_p`, `_s`, `_z`) are removed by the within-run constancy test. Values that are the same for everyone (locale, A/B buckets, flags, consent strings with no random part) are removed by the cross-context diff. Structured values that mix timestamp and ID are fixed by CSP21's timestamp + LCS stripping. Consent strings and URL hashes need explicit allow/deny rules.

### Cited Findings
- CSP21: excluded categories: "true/false flag", "client's language, geolocation, timezone, and timestamps. These values contain only coarse-grained information and as such they cannot uniquely identify a particular user". — [CSP21](https://spt.cut.ac.cy/papers/chen_www21.pdf)
- CGYA15: "Dynamic value strings may be timestamps or other non-identifiers" (removed by the constant-value rule). — [CGYA15](https://senglehardt.com/papers/www15_cookie_surveil.pdf)
- ACAR14: drop cookies expiring within a month ("too transient"), and fields that differ in length across crawls. — [ACAR14](https://securehomes.esat.kuleuven.be/~gacar/persistent/the_web_never_forgets.pdf)
- OWPM16: an upper length cap of 100 chars removes long blobs. Accidental sharing happens "if a site includes a user's ID within its URL query string, causing the ID to be shared with all third parties in the referring URL". — [OWPM16](https://www.cs.princeton.edu/~arvindn/publications/OpenWPM_1_million_site_tracking_measurement.pdf)
- PAP19: filter same-owner domain pairs (e.g. amazon.com ↔ amazonaws.com) to avoid flagging internal sharing. — [PAP19](https://arxiv.org/abs/1805.10505)
- FOUAD20: identical value in both crawls → "safe cookie"; (host, name) seen in only one crawl → "unknown", excluded. — [FOUAD20](https://arxiv.org/abs/1812.01514)
- GA4 `gcs` encodes consent state, e.g. G100 vs G111 (not an ID); `_p` is a random cache-buster. — [martech.zone](https://martech.zone/google-analytics-image-pixel-variables/); see also [owntag on gcs](https://owntag-website.pages.dev/blog/gsc-parameter)

### Inferences (concrete exclusion rules to implement; derived, not from a single paper)
- Timestamps: drop tokens matching `^1[5-9]\d{8}$` (epoch s, 2017–2033) or `^1[5-9]\d{11}$` (epoch ms), and ISO dates `\d{4}-\d{2}-\d{2}`. Before diffing compound values (`GA1.1.123.1700000000`), strip these sub-tokens (CSP21's approach) and keep the rest.
- Nonces / cache-busters: any (receiver, param) whose value changes between two requests in the same context → not an ID (e.g. GA `_p`, `_s`, `_z`, `_et`, `ord`, `rnd`, `cb`, `t`, `r`). Params that change per session but stay constant within a page set (GA `sid`, `sct`) are session-scoped. Treat them as weak and never as cross-site.
- Session IDs / CSRF: cookie with no expiry (session cookie) → weak. Names matching `(?i)(csrf|xsrf|token|nonce|sess|jsessionid|phpsessid|asp\.net_sessionid)` → exclude from the cross-site claim unless seen at a third-party receiver.
- Consent strings (exclude from ID matching but keep as evidence of what consent was signalled): cookies/params `euconsent-v2`, `addtl_consent`, `gdpr_consent`, `us_privacy`, `gpp`, `OptanonConsent`, `OptanonAlertBoxClosed`, `CookieConsent` (Cookiebot), `didomi_token`, GA `gcs`, `gcd`, `dma`, `npa`. Caveat: OneTrust `OptanonConsent` contains a `consentId=<uuid>` field, and Cookiebot `CookieConsent` contains a `stamp:'…'` that may be unique per user. Treat these as first-party consent-record IDs, not as tracking.
- Locale / flags / buckets: tokens shorter than 8 chars, pure-alpha tokens matching locale patterns `^[a-z]{2}([-_][A-Za-z]{2})?$`, booleans, small integers (<10^6), and values identical across the two contexts.
- URL hashes: hashes of the page URL are constant within a page but differ across pages, and are identical across contexts, so the cross-context diff removes them. Also drop any token equal to the hash of a URL we visited.
- Property / account IDs: `tid=G-XXXX`, `id=<pixel id>`, `UA-…`, `GTM-…` are constant across contexts → removed by the diff. Also add an explicit regex `^(G|UA|GTM|AW|DC)-[A-Z0-9-]+$`.
- Length band: 8 ≤ len ≤ 100 (OWPM16). Also require the lengths in contexts A and B to be within 25% (DEMIR22) and similarity < 0.66 (OWPM16/CSP21).

### Gaps
- No paper gave published exclusion lists specifically for TCF / OneTrust / Consent Mode strings; the list above is engineering judgement.

## Q6. Entropy vs length vs cross-run comparison

### Takeaway
The literature relies on cross-run comparison (constant within a run, different across runs). "Entropy" in these papers means dissimilarity across runs, not Shannon entropy. Length (≥8) is only a pre-filter. I found no published precision figure for a Shannon-entropy threshold on cookie values.

### Cited Findings
- CGYA15 operationalises "high-entropy value string" as Ratcliff-Obershelp dissimilarity (>55% similar → filtered). — [CGYA15](https://senglehardt.com/papers/www15_cookie_surveil.pdf)
- ACAR14: fields >33% similar "are unlikely to contain sufficient entropy"; low FP rate "through manual inspection". — [ACAR14](https://securehomes.esat.kuleuven.be/~gacar/persistent/the_web_never_forgets.pdf)
- DEMIR22: length ≥8 bytes "to hold enough entropy". — [DEMIR22](https://arxiv.org/abs/2202.01498)
- CG23 (ML classifier for first-party ATS cookies, which is a different task from per-value ID detection): "90.07% precision and 92.09% recall, with an overall accuracy of 90.18%", restricted to cookies ≥8 chars. — [CG23](https://arxiv.org/abs/2208.12370)
- PAP19 deliberately uses a loose length test (>10 chars, "false positives do not matter at this point"), then confirms by matching against the cookie-ID list. — [PAP19](https://arxiv.org/abs/1805.10505)

### Inferences
- Reliability ranking: cross-context diff (best) > within-run constancy > length band > Shannon entropy (weak; use only as a tiebreak when context B never saw the cookie). A reasonable single-context fallback, which is my own heuristic and not from the papers: len ≥ 16, character-class diversity, and Shannon entropy ≥ ~3.0 bits/char for hex/base64-like tokens. Label these results "likely ID (unverified)".

### Gaps
- No source found with Shannon-entropy thresholds or precision numbers for web ID detection.
