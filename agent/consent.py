"""
Consent step: find the cookie banner and click "Reject all" using plain
text-matching selectors, searching every frame (banners often live in a
CMP iframe, e.g. Sourcepoint). No AI yet — that's a separate fallback for
when these selectors don't find anything.

Also guards against "pay or consent" walls: some sites only offer reject
options that actually mean "reject and subscribe" / "reject and pay". We
must never click through into a real payment/signup flow, so a reject
button whose own label mentions paying is treated as a finding, not a
click target.

If plain selectors find nothing, fall back to the fast LLM: hand it every
visible clickable label on the page and ask which one (if any) rejects
cookies. The AI only ever picks an index into elements we already located
— it can't click anything we didn't already find ourselves — and the
same paywall guard applies to whatever it picks.

If that still finds nothing, dig into a "Manage preferences"-style panel
(see dig_into_preferences). Some panels have their own direct reject
button; others are a list of per-category Accept/Reject toggles with no
single "reject all" at all — that case is plain code (click every
per-category Reject, then Apply/Save), not an AI decision.
"""
import re

from . import llm

REJECT_PHRASES = [
    "reject all",
    "reject all cookies",
    "necessary only",          # e.g. just-eat.co.uk: "Necessary only" is its reject option
    "only necessary",
    "essential only",
    "decline",
    "disagree",
    "reject",
]

# "Accept" options on the banner's first screen. Only used to MEASURE how easy accepting
# is compared to rejecting; we never click these.
ACCEPT_PHRASES = [
    "accept all",
    "accept all cookies",
    "allow all",
    "accept",
    "i agree",
    "agree",
    "allow",
    "got it",
    "ok",
]

MANAGE_PHRASES = [
    "manage preferences",
    "manage cookies",
    "cookie settings",
    "preferences",
    "settings",
    "customize",
    "more options",
]

APPLY_PHRASES = [
    "apply settings",
    "save settings",
    "confirm choices",
    "confirm",
    "save",
]

PAYWALL_KEYWORDS = ["subscribe", "pay", "premium"]

def find_by_phrases(page, phrases):
    """Return the first visible button/link in any frame matching any phrase, or None."""
    for phrase in phrases:
        for role in ("button", "link"):
            for frame in page.frames:
                try:
                    locator = frame.get_by_role(role, name=phrase)
                    if locator.count() > 0 and locator.first.is_visible():
                        return locator.first
                except Exception:
                    continue
    return None

# Text that tells us a button belongs to a cookie / consent banner.
COOKIE_CONTEXT_JS = """el => {
    // Walk up a few parent elements; if a SMALL one (a banner, not the whole page)
    // mentions cookies / consent / privacy in its text, id or class, it's a cookie control.
    const re = /cookie|consent|privacy|gdpr|tracking|personal data/i;
    // n.getRootNode().host: step OUT of a shadow DOM (web-component banners, e.g. just-eat.co.uk's
    // <pie-cookie-banner>), otherwise the walk would stop at the component's edge.
    let n = el;
    for (let i = 0; i < 8 && n && n !== document.body; i++, n = n.parentElement || n.getRootNode().host) {
        const text = n.innerText || "";
        if (text.length > 4000) break;          // reached the main page: stop, too broad
        if (re.test(text) || re.test(n.id || "") || re.test(String(n.className || ""))) return true;
    }
    return false;
}"""

# Consent-banner iframes (OneTrust, Sourcepoint, ...) usually say so in their address.
CMP_FRAME = re.compile(r"consent|cmp|cookie|privacy|sourcepoint|onetrust|didomi|trustarc|quantcast|usercentrics", re.I)


def in_cookie_context(frame, el):
    """True if this button sits inside something about cookies/consent (or a consent iframe).
    Stops us clicking e.g. a shop's "Customize" product button (talldwarfhosting.com) and
    calling it a cookie banner."""
    if frame != frame.page.main_frame and CMP_FRAME.search(frame.url or ""):
        return True
    try:
        return bool(el.evaluate(COOKIE_CONTEXT_JS))
    except Exception:
        return False


# Pre-ticked toggles (ICO: consent needs a clear positive action, so non-essential
# categories must start OFF). Runs inside each frame; returns the labels of toggles that are
# visible, inside a cookie banner, switched ON, NOT locked (locked = strictly necessary,
# that's allowed) and about a non-essential purpose. Read-only: we never click these.
PRETICKED_JS = """() => {
    const cookieRe = /cookie|consent|privacy|gdpr|tracking|personal data/i;
    const optionalRe = /marketing|advertis|targeting|analytic|statistic|performance|measurement|personali[sz]|social media|tracking|profil/i;
    const essentialRe = /strictly|necessary|essential|required|always active/i;
    const inCookieBox = (el) => {
        for (let n = el, i = 0; i < 8 && n && n !== document.body; i++, n = n.parentElement) {
            const t = n.innerText || "";
            if (t.length > 4000) break;
            if (cookieRe.test(t) || cookieRe.test(n.id || "") || cookieRe.test(String(n.className || ""))) return true;
        }
        return false;
    };
    const labelOf = (el) => {
        // The toggle's own label, else the text of the nearest small container (its category row).
        let t = el.getAttribute("aria-label") || (el.labels && el.labels[0] && el.labels[0].innerText) || "";
        for (let n = el.parentElement, i = 0; !t.trim() && n && i < 4; i++, n = n.parentElement) {
            if ((n.innerText || "").length < 200) t = n.innerText || "";
        }
        return t.replace(/\\s+/g, " ").trim().slice(0, 80);
    };
    const visible = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    const found = [];
    for (const el of document.querySelectorAll('input[type=checkbox], [role=switch], [role=checkbox]')) {
        const on = el.checked === true || el.getAttribute("aria-checked") === "true";
        const locked = el.disabled || el.getAttribute("aria-disabled") === "true";
        // Custom switches often hide the real <input>; check its label's size instead.
        const shown = visible(el) || (el.labels && el.labels[0] && visible(el.labels[0]));
        if (!on || locked || !shown || !inCookieBox(el)) continue;
        const label = labelOf(el);
        if (optionalRe.test(label) && !essentialRe.test(label)) found.push(label);
    }
    return found;
}"""


def find_preticked(page):
    """Labels of non-essential cookie toggles that are already ON, across all frames (deduped)."""
    labels = []
    for frame in page.frames:
        try:
            for label in frame.evaluate(PRETICKED_JS):
                if label not in labels:
                    labels.append(label)
        except Exception:
            continue
    return labels


def label_of(el):
    """Visible text of a button. Web-component buttons (<pie-button>Necessary only</pie-button>) keep their
    text on the component, outside the inner <button>'s shadow DOM, so inner_text() is empty there."""
    try:
        text = el.inner_text().strip()
        if text:
            return text
        return (el.evaluate("e => (e.getRootNode().host || e).textContent || e.getAttribute('aria-label') || ''")
                or "").strip()
    except Exception:
        return ""


def find_cookie_button(page, phrases):
    """Like find_by_phrases, but only returns buttons/links that are in a cookie context."""
    for phrase in phrases:
        for role in ("button", "link"):
            for frame in page.frames:
                try:
                    for el in frame.get_by_role(role, name=phrase).all()[:5]:
                        if el.is_visible() and in_cookie_context(frame, el):
                            return el
                except Exception:
                    continue
    return None


def find_reject_button(page):
    """Return the first visible reject-cookies button/link (in a cookie banner), or None."""
    return find_cookie_button(page, REJECT_PHRASES)

def find_manage_button(page):
    """Return the first visible 'manage preferences'-style button/link (in a cookie banner), or None."""
    return find_cookie_button(page, MANAGE_PHRASES)

def find_apply_button(page):
    """Return the first visible 'apply/save/confirm settings' button/link, or None."""
    return find_by_phrases(page, APPLY_PHRASES)

def is_paywalled(label):
    """True if a 'reject' button's label actually gates rejection behind payment."""
    label_lower = label.lower()
    return any(word in label_lower for word in PAYWALL_KEYWORDS)

def gather_candidates(page, limit=30):
    """Collect (label, locator) pairs for visible buttons/links in every frame."""
    candidates = []
    for frame in page.frames:
        for role in ("button", "link"):
            try:
                for el in frame.get_by_role(role).all():
                    try:
                        if not el.is_visible():
                            continue
                        text = el.inner_text().strip()
                    except Exception:
                        continue
                    if not text:
                        continue
                    candidates.append((text, el))
                    if len(candidates) >= limit:
                        return candidates
            except Exception:
                continue
    return candidates

BANNER_SCHEMA = {
    "type": "object",
    "properties": {"index": {"type": ["integer", "null"]}},
    "required": ["index"],
}

def count_exact_reject_buttons(page):
    """Count visible elements whose text is exactly 'Reject', across all frames."""
    total = 0
    for frame in page.frames:
        for role in ("button", "link"):
            try:
                total += frame.get_by_role(role, name="Reject", exact=True).count()
            except Exception:
                continue
    return total

def click_all_reject_toggles(page):
    """Click every exact 'Reject' button/link across all frames — the
    per-category toggles some preference panels use instead of a single
    reject-all button. Returns True if anything was clicked."""
    clicked_any = False
    for frame in page.frames:
        for role in ("button", "link"):
            try:
                locator = frame.get_by_role(role, name="Reject", exact=True)
                count = locator.count()
            except Exception:
                continue
            for i in range(count):
                try:
                    el = locator.nth(i)
                    if el.is_visible():
                        el.click()
                        clicked_any = True
                except Exception:
                    continue
    return clicked_any

def dig_into_preferences(page, cost=None):
    """Click into a 'manage preferences'-style panel and try to reject there.
    Tries, in order: per-category reject toggles + apply (when there are 2+
    exact 'Reject' buttons — ambiguous otherwise, since our generic "reject"
    phrase could otherwise grab just one toggle and wrongly report success),
    a direct single reject button, then the AI fallback as a last resort.
    Returns a consent dict, or None if there was no preferences panel at all."""
    manage_button = find_manage_button(page)
    if manage_button is None:
        return None
    manage_label = label_of(manage_button)
    manage_button.click()
    page.wait_for_timeout(1000)
    preticked = find_preticked(page)   # before we touch anything in the panel
    result = _dig(page, manage_label, cost)
    result["preticked"] = preticked
    return result


def _dig(page, manage_label, cost=None):
    """The rest of dig_into_preferences, once the panel is open."""
    if count_exact_reject_buttons(page) >= 2:
        click_all_reject_toggles(page)
        apply_button = find_apply_button(page)
        clicks = [manage_label, "reject toggles"]
        if apply_button is None:
            return {"banner_found": True, "rejected": True, "method": "selector", "clicks": clicks}
        clicks.append(label_of(apply_button))
        if not apply_button.is_enabled():
            # Apply stays locked — usually because some categories are
            # marked "consent required" with no reject option at all, i.e.
            # a pay-or-consent wall hiding inside the preferences panel.
            return {"banner_found": True, "rejected": False, "method": "pay_or_consent", "clicks": clicks}
        apply_button.click()
        return {"banner_found": True, "rejected": True, "method": "selector", "clicks": clicks}

    direct = find_reject_button(page)
    if direct is not None:
        label = label_of(direct)
        if is_paywalled(label):
            return {"banner_found": True, "rejected": False, "method": "pay_or_consent", "clicks": [manage_label, label]}
        direct.click()
        return {"banner_found": True, "rejected": True, "method": "selector", "clicks": [manage_label, label]}

    candidates = gather_candidates(page)
    if candidates:
        index = ask_ai_for_reject_index(candidates, cost=cost)
        if index is not None and 0 <= index < len(candidates):
            label, el = candidates[index]
            if not is_paywalled(label):
                el.click()
                return {"banner_found": True, "rejected": True, "method": "llm", "clicks": [manage_label, label]}

    return {"banner_found": True, "rejected": False, "method": "failed", "clicks": [manage_label]}

def ask_ai_for_reject_index(candidates, cost=None):
    """Ask the fast model which candidate index rejects cookies, if any."""
    numbered = "\n".join(f"{i}: {text}" for i, (text, _) in enumerate(candidates))
    prompt = (
        "These are clickable button/link labels on a webpage, possibly from a "
        "cookie-consent banner. Find the single button that REJECTS or DECLINES "
        "non-essential cookies/tracking, with no payment involved. "
        "Respond with JSON only, exactly one key \"index\": either the integer "
        "index of that button, or null if none of them reject cookies.\n\n"
        + numbered
    )
    result = llm.ask_fast(prompt, json_schema=BANNER_SCHEMA, cost=cost)
    return result.get("index")

def reject_cookies(page, cost=None):
    """Try to click a reject-cookies button. Returns the audit-format 'consent' dict, plus:
      accept_label     the one-click "Accept" button on the banner's first screen (None if none)
      reject_steps     how many clicks rejecting took (None if rejecting didn't work)
    ICO guidance: refusing must be as easy as accepting. compare.py turns "accept = 1 click,
    reject = 2+ clicks" into a finding. We only LOOK for the accept button; we never click it."""
    accept = find_cookie_button(page, ACCEPT_PHRASES)   # must look before rejecting: the banner closes after
    try:
        accept_label = label_of(accept)[:60] if accept is not None else None
    except Exception:
        accept_label = None
    first_screen = find_preticked(page)                  # toggles shown on the banner itself
    result = _reject_cookies(page, cost=cost)
    result["accept_label"] = accept_label
    # Non-essential toggles that were already ON before we touched anything (banner + prefs panel).
    result["preticked"] = list(dict.fromkeys(first_screen + result.get("preticked", [])))
    # Each entry in "clicks" is one step the user would take ("reject toggles" = one panel of toggles).
    result["reject_steps"] = len(result["clicks"]) if result["rejected"] else None
    return result


def _reject_cookies(page, cost=None):
    """The actual reject logic (see reject_cookies)."""
    button = find_reject_button(page)
    if button is not None:
        label = label_of(button)
        if is_paywalled(label):
            return {"banner_found": True, "rejected": False, "method": "pay_or_consent", "clicks": [label]}
        button.click()
        return {"banner_found": True, "rejected": True, "method": "selector", "clicks": [label]}

    candidates = gather_candidates(page)
    if not candidates:
        return {"banner_found": False, "rejected": False, "method": "failed", "clicks": []}

    index = ask_ai_for_reject_index(candidates, cost=cost)
    if index is not None and 0 <= index < len(candidates):
        label, el = candidates[index]
        if is_paywalled(label):
            return {"banner_found": True, "rejected": False, "method": "pay_or_consent", "clicks": [label]}
        el.click()
        return {"banner_found": True, "rejected": True, "method": "llm", "clicks": [label]}

    dug = dig_into_preferences(page, cost=cost)
    if dug is not None:
        return dug

    return {"banner_found": False, "rejected": False, "method": "failed", "clicks": []}
