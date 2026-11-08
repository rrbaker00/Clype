"""
EU equivalents for our UK legal citations. Plain code, no AI.

UK law copied EU law at Brexit, so most rules map 1:1:
  PECR reg. 6         -> ePrivacy Directive 2002/58/EC Art. 5(3) (as implemented in each EU country)
  UK GDPR Art. N      -> EU GDPR (Regulation 2016/679) Art. N (same numbering)
  ICO cookie guidance -> EDPB Guidelines 05/2020 on consent + EDPB Cookie Banner Taskforce report (2023)
Left out on purpose:
  - the Data (Use and Access) Act 2025 analytics exemption: UK only, the EU has no such exemption.
  - CMA choice-architecture guidance: UK competition guidance, no clean EU equivalent for every site.
If we can't map anything, law_eu is None. We never invent a citation.
"""
import re

# "UK GDPR" followed by article/recital numbers, e.g. "Art. 4(11) and 7(4)", "Articles 6, 13(1)(c)",
# "Article 13(2)(b)", "recital 32". We take the text up to the next ";" and clean it below.
_ARTICLES = re.compile(r"UK GDPR\s+((?:Art(?:icles?)?\.?|recitals?)\s[^;]*)", re.I)


def _clean_ref(text):
    """'Art. 4(11) and 7(4) (consent must be freely given). ICO allows...' -> 'Art. 4(11) and 7(4)'."""
    text = re.split(r"\.\s+(?=[A-Z])|\bPECR\b", text)[0]               # stop at the next sentence / law
    text = re.sub(r"\s*\((?=[^)]*[a-z]{3})[^)]*\)", "", text)          # drop worded brackets, keep (11), (e)
    return text.strip(" .,")


def eu_equivalent(law):
    """'PECR reg. 6 (consent needed...)' -> 'ePrivacy Directive 2002/58/EC Art. 5(3)'. None if nothing maps."""
    if not law:
        return None
    parts = []
    if re.search(r"\bPECR\b", law):
        parts.append("ePrivacy Directive 2002/58/EC Art. 5(3) (consent before storing/reading on a device)")
    for m in _ARTICLES.finditer(law):
        ref = _clean_ref(m.group(1))   # article numbers only, UK explanation dropped
        if ref:
            parts.append(f"EU GDPR {ref}")
    if re.search(r"\bICO\b", law):
        parts.append("EDPB Guidelines 05/2020 on consent; EDPB Cookie Banner Taskforce report (2023)")
    return "; ".join(dict.fromkeys(parts)) or None


def add_eu_law(findings):
    """Adds "law_eu" to every finding, in place. Works for plain-code and AI findings alike."""
    for f in findings:
        f["law_eu"] = eu_equivalent(f.get("law"))
    return findings
