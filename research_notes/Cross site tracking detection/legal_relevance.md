# Legal relevance of cross-site tracking evidence (UK primary, EU secondary), status as of Nov 2026

Scope: how a consent auditor should word and cite findings for (1) cross-site linking of one identifier, (2) ID/cookie syncing, (3) first-party cookie values (_ga, _fbp) sent to third parties, (4) CNAME cloaking, (5) link decoration / UID smuggling, (6) any of these before consent or after "Reject all".

## PECR reg. 6 and DUAA 2025 changes (exemptions, commencement, fines)

### Takeaway
New PECR reg. 6 and Schedule A1 (DUAA s.112 and Sch. 12) have been **in force since 5 Feb 2026** (SI 2026/82). The new "statistical purposes" and "appearance/functionality" exceptions are narrow and **cannot** cover cross-site tracking, ID syncing, advertising, or analytics data that a third party uses for its own purposes. Max PECR fines are now at UK GDPR level (reported in force 5 Feb 2026).

### Cited Findings
- New reg. 6(1): "Subject to Schedule A1, a person must not store information, or gain access to information stored, in the terminal equipment of a subscriber or user." New reg. 6A lets the Secretary of State add, vary or remove exceptions by affirmative SI after consulting the ICO. s.112 was in force at Royal Assent for some purposes and fully from **5 Feb 2026, SI 2026/82 reg. 2(w)**. — [legislation.gov.uk DUAA s.112](https://www.legislation.gov.uk/ukpga/2025/18/section/112)
- Schedule 12 inserts Schedule A1 into PECR, **in force 5 Feb 2026 (SI 2026/82 reg. 2(z13))**. — [legislation.gov.uk DUAA Sch. 12](https://www.legislation.gov.uk/ukpga/2025/18/schedule/12)
  - Para 4, strictly necessary: storage or access "strictly necessary for the provision of an information society service" requested by the user. Examples include security, fraud and fault prevention, authentication, and remembering choices.
  - Para 5, statistical purposes. **All** of these must hold: (b) "the sole purpose of the storage or access is to enable the person" to collect statistics about use of the service/website with a view to improving it; (c) the information "is not shared with any other person except for the purpose of enabling that other person to assist" in improving the service/website; (d) clear and comprehensive information is given; (e) the user gets a simple, free means of objecting and does not object.
  - Para 6, appearance/functionality: sole purpose is to adapt how the website appears or functions in line with the user's preference, with information and a free objection mechanism.
  - Para 7, emergency assistance: location for emergency help only.
- ICO final guidance, "What are the exceptions?" (Guidance on the use of storage and access technologies):
  - Statistical exception: a third-party provider "must be a processor, not a joint controller". It cannot use the data for its own purposes and must not "link it with other information from any other information it works with". Output must be "aggregate data that is not personal data". Monitoring or tracking individuals, profiling, and advertising are outside the exception.
  - "You must get consent for any cross-site or cross-device tracking."
  - "Online advertising purposes are not exempt from PECR's consent requirements and never have been." This includes measurement, frequency capping and ad-fraud detection.
  - Appearance exception does not cover adapting content to known or inferred interests or browsing history.
  - Strictly necessary for security/fraud: "If you use it for any other purpose as well, the exception does not apply."
  - Exceptions apply only where use matches each exception's purposes and requirements. Otherwise consent is needed.
  — [ICO: What are the exceptions?](https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/guidance-on-the-use-of-storage-and-access-technologies/what-are-the-exceptions/)
- ICO final storage and access technologies guidance published around 29 Apr / 1 May 2026, after two consultation rounds. It covers cookies, tracking pixels, device fingerprinting and similar technologies. The ICO's review of reg. 6 for online advertising (e.g. "consent or pay", possible low-risk ad exceptions) "sits separately" and is ongoing. — [SCL](https://www.scl.org/ico-publishes-final-storage-and-access-technologies-guidance/); [Stevens & Bolton](https://www.stevens-bolton.com/insights/102mrve/the-data-use-and-access-act-2025-ico-guidance-on-cookies-and-the-use-of-storag/); [Osborne Clarke](https://marketinglaw.osborneclarke.com/advertising-regulation/new-exceptions-explained-in-ico-final-guidance-on-storage-and-access-technologies-could-online-advertising-be-next/)
- ICO: DUAA changes phased in between June 2025 and June 2026. As of 19 June 2026, "all data protection provisions in the Data (Use and Access) Act 2025 are now in force". — [ICO DUAA page](https://ico.org.uk/about-the-ico/what-we-do/legislation-we-cover/data-use-and-access-act-2025/the-data-use-and-access-act-2025-what-does-it-mean-for-organisations/)
- PECR maximum penalty raised from £500,000 to the higher of £17.5m or 4% of global annual turnover. Reported in force 5 Feb 2026 (Commencement No. 6, delayed from Dec 2025). The old "seriousness / substantial damage or distress" threshold was reportedly removed at the same time. — [Bratby Law](https://bratby.law/duaa-takes-effect-ico-enforcement/); [Lewis Silkin](https://www.lewissilkin.com/insights/2026/02/09/uk-data-reform-becomes-reality-what-this-means-for-you-and-what-you-need-to-do-n-102mh5x); [MFMac (pre-commencement explainer)](https://www.mfmac.com/insights/data-protection/data-use-and-access-act-2025-increased-maximum-fines-for-cookies-and-direct-marketing-practices/)
- Conflict: one secondary source said the statistical exception requires that collection "does not significantly affect users". That wording is **not** in the Sch. A1 text as summarised from legislation.gov.uk, so treat it as unreliable. — [Bratby Law commencement note](https://bratby.law/data-use-and-access-act-2025-commencement/) vs [legislation.gov.uk Sch. 12](https://www.legislation.gov.uk/ukpga/2025/18/schedule/12)

### Inferences
- **Answer to the key question:** the DUAA analytics exemption does **not** apply in these cases:
  - analytics data shared with a third party that uses it for its own purposes (e.g. advertising): this fails para 5(1)(c) and the ICO's processor-only requirement;
  - IDs linked across sites: this fails the ICO's no-linking and no-tracking-individuals rules and "consent for any cross-site tracking".
- So any finding of types (1), (2), (3) where the recipient is an ad-tech firm, or (5), is outside every exception. If it happens without consent, or after "Reject all", it is a likely reg. 6 breach.
- A _ga value sent only to Google Analytics *could* in principle fall under the statistical exception. That needs Google acting as processor only, no ad features or Signals, a free objection route, and no objection. After "Reject all", the user has arguably objected, so para 5(1)(e) fails. Wording: "Analytics continued after you rejected cookies. The new statistics exemption only applies if you have not objected."
- Pre-5 Feb 2026 conduct falls under the old reg. 6 (strictly necessary or communication only). There was no analytics exemption then.

### Gaps
- Exact SI number for the PECR penalty commencement was not confirmed from legislation.gov.uk (secondary sources only).
- The full verbatim text of the ICO guidance chapters on pixels, link decoration, server-side tracking and CNAME was not retrieved. The ICO pages confirm pixels and fingerprinting are in scope. I found no ICO quote on CNAME cloaking or link decoration specifically.

## ICO guidance, statements and enforcement (fingerprinting, top 1000 sites, RTB)

### Takeaway
The ICO treats pixels, fingerprinting and other non-cookie techniques as in scope of reg. 6. In Dec 2024 it publicly called Google's fingerprinting policy change "irresponsible". Its top-1,000-websites programme produced high compliance figures and reprimands, but I found no confirmed fines from it.

### Cited Findings
- Dec 2024: Google said it would stop prohibiting fingerprinting for advertisers from 16 Feb 2025. Stephen Almond, ICO Executive Director of Regulatory Risk, called it "irresponsible". He said businesses do not have free rein to use fingerprinting, that it is harder for users to detect and control, and that the ICO would intervene if it is not deployed lawfully. He also quoted Google's 2019 view that fingerprinting "subverts user choice and is wrong". The ICO published draft fingerprinting guidance alongside the statement. — [ICO statement](https://ico.org.uk/about-the-ico/media-centre/news-and-blogs/2024/12/our-response-to-google-s-policy-change-on-fingerprinting); [The Register](https://www.theregister.com/2024/12/23/uk_ico_not_happy_with/)
- Dec 2025 ICO update: 979 of the UK's top 1,000 websites met its cookie checks at the latest test, with 564 having fixed their practices after ICO engagement. — [ICO news Dec 2025](https://ico.org.uk/about-the-ico/media-centre/news-and-blogs/2025/12/ico-action-secures-increased-cookie-compliance/)
- The earlier top-200 sweep led to reprimands. One reported example is Sky Betting and Gaming, for advertising cookies set without consent. Fines were not confirmed. — [GDPR Local](https://gdprlocal.com/ico-targets-top-1000-uk-websites-for-cookie-compliance/) (secondary)
- The ICO online tracking strategy update aims to "Investigate compliance concerns in the wider adtech ecosystem" and to settle "consent or pay". — [SCL](https://www.scl.org/ico-issues-online-tracking-strategy-update/)

### Inferences
- The ICO's top-1,000 checks focus on whether non-essential cookies are set before consent and whether rejecting is as easy as accepting. Our "after Reject all" evidence maps directly onto the ICO's stated enforcement focus.

### Gaps
- ICO June 2019 "Update report into adtech and real time bidding": not retrieved this session. From prior knowledge, it found RTB bid requests broadcast personal data, including special category data, to many parties without a lawful basis, and that legitimate interests could not be relied on for placing or reading cookies. Verify at ico.org.uk before citing.
- I found no ICO-specific text on CNAME cloaking, link decoration or server-side tracking. The ICO guidance's general principle (reg. 6 is technology-neutral and covers "similar technologies") is the safest citation.

## UK GDPR: are cross-site IDs personal data, and which articles apply

### Takeaway
A cookie ID or persistent identifier that lets a recipient single out and link one browser across sites is very likely personal data: it is an "online identifier" (Art. 4(1), Recital 30). CJEU SRB (Sept 2025) adds nuance only where the recipient genuinely has no reasonable means to re-identify, which is weak for ad-tech firms that link IDs across sites. TC strings were held to be personal data (CJEU C-604/22, then the Belgian Market Court 2025).

### Cited Findings
- CJEU EDPS v SRB (C-413/23 P), 4 Sept 2025:
  - Personal-data status is assessed relative to the holder. For a recipient with no key and no reasonable means of re-identification, pseudonymised data may not be personal data. For the controller holding the key it remains personal.
  - The Court rejected the EDPS/EDPB absolute position.
  - Onward disclosure to a party able to re-identify brings the data back within scope.
  — [Bird & Bird](https://cm.twobirds.com/en/insights/2025/eu-the-srb-decision-a-new-era-for-personal-data-and-data-processing-agreements); [A&O Shearman](https://www.aoshearman.com/en/insights/ao-shearman-on-data/cjeu-clarifies-concept-of-personal-data-for-a-transfer-of-pseudonymised-data-to-third-parties); [Clifford Chance](https://www.cliffordchance.com/insights/resources/blogs/talking-tech/en/articles/2025/09/pseudonymized-data-after-edps-v-srb.html)
- Belgian Market Court, 14 May 2025 (after CJEU C-604/22, March 2024):
  - The TC String is personal data where it can be linked by reasonable means to an identifiable person.
  - IAB Europe is a joint controller for TCF processing but **not** for downstream advertising or OpenRTB processing.
  - There was an Art. 26 breach because no joint controller arrangement existed.
  - Sources conflict on whether the €250k fine was "upheld" or the decision annulled and replaced with the same sanction.
  — [Belgian DPA](https://www.dataprotectionauthority.be/the-market-court-rules-in-the-iab-europe-case); [Lewis Silkin](https://www.lewissilkin.com/insights/2025/05/27/iab-tcf-belgian-market-court-upholds-250-000-fine-against-iab-for-gdpr-violatio-102kyon); [IAB UK](https://www.iabuk.com/news-article/belgian-market-court-annuls-apds-decision-regarding-tcf); [Harbottle & Lewis](https://www.harbottle.com/joint-controllers-tc-strings-and-openrtb-unpacking-the-belgian-market-courts-appeal-decision-on-iab-europes-tcf/)
- Even where PECR consent is not needed, any personal data processing still needs a UK GDPR lawful basis. — [ICO exceptions guidance](https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/guidance-on-the-use-of-storage-and-access-technologies/what-are-the-exceptions/)

### Inferences
- Post-Brexit CJEU judgments (SRB 2025, C-604/22 2024) are not binding in the UK but can be persuasive (EU (Withdrawal) Act 2018 s.6(2)). Cite them as "EU courts have held…".
- SRB does not help a tracker that receives the same ID from many sites. The whole point of that ID is to single out and link one browser, which is the "means reasonably likely" to identify. That holds especially when it is combined with IP, user agent and logged-in data.
- Article mapping for wording:
  - Art. 5(1)(a), lawfulness, fairness and transparency: covers undisclosed sharing and tracking after rejection.
  - Art. 5(1)(b), purpose limitation: covers analytics IDs reused for advertising.
  - Art. 6, lawful basis: consent is withdrawn or refused after "Reject all".
  - Art. 7, conditions for consent: withdrawal must be as easy as giving consent.
  - Art. 13(1)(e), recipients: a policy that does not name observed recipients.
  - Art. 26, joint controllers: a site embedding a third-party pixel shares responsibility for the collection and transmission (Fashion ID, see Gaps).
  - Art. 4(4), profiling: cross-site linking for ad targeting.
  - Art. 22 is rarely engaged by ad targeting. Avoid citing it unless there is a significant-effect decision.

### Gaps
- CJEU Fashion ID (C-40/17, 29 July 2019) and Breyer (C-582/14, 19 Oct 2016) were not re-fetched this session. Summary from prior knowledge, to verify on curia.europa.eu:
  - Fashion ID: a site embedding a Like button is a joint controller with Facebook for the collection and transmission of visitor data, but not for Facebook's later processing.
  - Breyer: a dynamic IP address can be personal data where the site operator has legal means to identify the user with additional data.
- CJEU C-604/22 (IAB Europe, 7 Mar 2024) text was not fetched directly. Its holding here is cited only through the Market Court commentary.
- I found no UK court decision directly holding that a cross-site cookie ID is personal data. The UK position rests on Art. 4(1) and Recital 30 wording and ICO guidance.

## EU ePrivacy Art. 5(3): EDPB Guidelines 2/2023, Cookie Banner Taskforce, CNIL on CNAME

### Takeaway
EDPB Guidelines 2/2023 (v2 adopted 7 Oct 2024) say that tracking pixels, tracking links (URL decoration), unique identifiers collected by client-side code, local processing sent back to a server, and in many cases IP-only tracking all engage Art. 5(3). So consent is needed unless an exemption applies. CNIL says CNAME cloaking is not illegal in itself but discourages it. It does not change consent requirements.

### Cited Findings (EDPB Guidelines 2/2023 v2, adopted 7 October 2024) — [EDPB PDF](https://www.edpb.europa.eu/system/files/2024-10/edpb_guidelines_202302_technical_scope_art_53_eprivacydirective_v2_en_0.pdf)
- Para 34 (end), citing WP29 Opinion 9/2014: proactive sending of information by terminal equipment triggers Art. 5(3). For example, "when a website instructs the terminal equipment to send information to third-party advertising services through the inclusion of a tracking pixel".
- Para 36: storage done by instructing software (e.g. browser cookie storage) "is considered to be initiated directly by the other party", "regardless of who created or installed the protocols or software".
- Para 37: there is no minimum duration or amount of stored information.
- Para 47: a tracking pixel "usually fulfils no purpose related to the requested content itself; its sole purpose is to automatically establish a communication by the client to the host of the pixel".
- Para 48: "Tracking pixels on websites may link to an entity collecting many such requests and thus being able to track users' behaviour. Such tracking pixels may also contain additional identifiers, metadata or content as part of the link."
- Para 49: "Tracking links can function in the same way, but the identifier is appended to the website address. When the Uniform Resource Locator ('URL') is visited by the user, the targeted website loads the requested resource but also collects an identifier which is not relevant in terms of resource identification."
- Para 50: distributing tracking links or pixels "does constitute storage, at the very least through the caching mechanism", so "Article 5(3) ePD is applicable, even if this storage is not permanent."
- Para 51: "The addition of tracking information to URLs or images (pixels) sent to the user constitutes an instruction to the terminal equipment to send back the targeted information (the specified identifier)… the collection of identifiers provided through such tracking mechanisms constitutes a 'gaining of access'".
- Para 53: locally processed information sent back to a server "would constitute a 'gaining of access to information already stored'".
- Paras 54–55: IP-only tracking "in some case across multiple domains" can trigger Art. 5(3) "even though the instruction to make the IP available has been made by a different entity than the receiving one". It does so unless the entity can ensure the IP does not originate from the user's equipment (CGNAT is the exception).
- Paras 61 and 63: unique or persistent identifiers (e.g. hashed email) "shared amongst several controllers to uniquely identify a person over different datasets". When collected by client-side code, "a 'gaining of access' is taking place and Article 5(3) ePD applies."
- Paras 40 and 56: the guidelines do not analyse the exemptions. Art. 5(3) applying does not automatically mean consent is required.

### Cited Findings (CNIL)
- CNIL definition page: CNAME cloaking ("délégation de sous-domaine") "n'est pas illégale", but can cause major security flaws, e.g. third parties reading authentication cookies. It advises separating third-party-delegated subdomains from those handling sensitive data. — [CNIL définition](https://cnil.fr/fr/definition/cname-cloaking-ou-delegation-de-sous-domaine)
- The final CNIL cookie recommendation urges controllers not to use techniques that mask the identity of the entity using trackers, such as subdomain delegation. — [Journal du Net](https://www.journaldunet.com/adtech/1494321-cookies-pub-la-cnil-met-un-peu-d-eau-dans-son-vin/) (secondary); per [Hogan Lovells](https://engage.hoganlovells.com/knowledgeservices/news/cnil-publishes-faq-clarifying-cookie-use), CNIL "would therefore certainly look for websites practicing CNAME cloaking" in audits.

### Inferences
- For UK findings, the EDPB text is persuasive only, not binding. The ICO's technology-neutral reading of reg. 6 reaches the same result for pixels and decorated links. Cite the EDPB as "EU regulators say…".
- CNAME cloaking is not a separate offence. The legal hook is that the tracker is still a third party (controller) receiving IDs. This undermines transparency (Art. 5(1)(a), 13(1)(e)), and consent is still needed under reg. 6 / Art. 5(3). Disguising the tracker as first-party is an aggravating transparency point plus a security risk (CNIL).

### Gaps
- EDPB Cookie Banner Taskforce report (17 Jan 2023) was not retrieved. From prior knowledge: there must be a reject option at the first layer, pre-ticked boxes are invalid, and deceptive colours or contrast are not allowed. Verify on edpb.europa.eu.
- I found no specific DPA enforcement decision on cookie syncing as such. The RTB / TCF cases are the closest.

## Wording findings without overclaiming

### Takeaway
Our evidence shows what our browser sent and to whom. It does not show what the recipient did with it. Word findings as "sent X to Y, which allows Y to link…", cite the rule that applies to the sending, and keep "unlawful" for the regulator.

### Cited Findings
- EDPB para 48 itself uses capability language ("may link to an entity collecting many such requests and thus being able to track users' behaviour"). — [EDPB 2/2023](https://www.edpb.europa.eu/system/files/2024-10/edpb_guidelines_202302_technical_scope_art_53_eprivacydirective_v2_en_0.pdf)
- The storage or access step, and the sending of the identifier, is itself the regulated act under Art. 5(3) / reg. 6 (EDPB para 51). So the observed request is enough for the PECR or ePrivacy point, without proving downstream profiling. — [EDPB 2/2023](https://www.edpb.europa.eu/system/files/2024-10/edpb_guidelines_202302_technical_scope_art_53_eprivacydirective_v2_en_0.pdf)
- The ICO's cross-site tracking rule ("consent for any cross-site or cross-device tracking") is about the purpose or capability. — [ICO exceptions](https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/guidance-on-the-use-of-storage-and-access-technologies/what-are-the-exceptions/)

### Inferences (suggested templates)
- (1) Cross-site linking: "The same identifier (ID …) was sent to [tracker] from [site A] and [site B]. That lets [tracker] link your visits across these sites." Cite PECR reg. 6 and Sch. A1 (no exception covers cross-site tracking, per ICO), and UK GDPR Art. 4(1) (online identifier) and Art. 6. Do not say "[tracker] built a profile of you."
- (2) ID syncing: "[Company A] passed its ID for your browser to [Company B] (cookie match). This lets both firms join up what they know about this browser." Cite reg. 6, Art. 5(1)(a), Art. 13(1)(e) if B is not named in the policy, and Art. 26 / Fashion ID for the site's shared responsibility for the transmission.
- (3) _ga / _fbp sent to a third party: "Your first-party analytics ID (_ga = …) was sent to [domain]." If the recipient is ad-tech, or the event happened after rejection: "The new UK statistics exemption does not cover this, because the data went to a third party for its own purposes, or because you objected." Cite Sch. A1 para 5(1)(c) and (e), and the ICO processor-only rule.
- (4) CNAME: "[sub.site.com] is a DNS alias for [tracker]. Requests that look first-party actually go to [tracker]." Frame it as a transparency issue (Art. 5(1)(a), 13). Avoid "illegal technique" (CNIL: not illegal per se).
- (5) Link decoration: "A tracking ID was added to the link you followed ([param]=…)." Cite EDPB paras 49–51 (EU, persuasive) and ICO technology-neutral reg. 6.
- (6) After "Reject all": "This was sent **after** you clicked 'Reject all'." Cite reg. 6 (no consent), the ICO's "advertising never exempt" statement, and UK GDPR Art. 7(3). Before any choice was made: "sent before you made any choice."
- Severity: an ad-tech recipient plus a post-reject event is the strongest case. Pure first-party analytics before 5 Feb 2026 had no exemption. After that date, flag it as "may be covered by the statistics exemption if…" rather than as a breach.
- Use "appears to", "allows", "is consistent with". Never "proves" or "is illegal". Always give evidence IDs, timestamps and the request URL.

### Gaps
- I found no regulator guidance on evidential standards for third-party automated audits. The templates above are inference from the legal tests, not sourced guidance.
