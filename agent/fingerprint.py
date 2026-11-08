"""
Fingerprinting detection (CLAUDE.md bonus feature). Plain code, no AI.

Fingerprinting = identifying your device from how it draws graphics / plays audio / which
fonts it has, instead of a cookie. PECR reg. 6 covers it too ("storing or ACCESSING information
on a device"), so rejecting cookies should stop it, and the ICO says so explicitly.

How: INIT_JS runs in every page and frame BEFORE the site's own scripts (context.add_init_script).
It wraps a few browser functions, and when one is used in a fingerprinting way it tells Python
which script did it (via an exposed function). The wrappers always call the real function and
return its real result, so the site behaves exactly the same. Passive: we only watch.

What counts (strict, to avoid flagging normal sites):
  canvas  a canvas >= 16x16 px with >= 10 characters of real text drawn on it, read back as pixels
          (skips e.g. WordPress's tiny emoji-support check)
  webgl   reading the hidden GPU vendor/model (UNMASKED_VENDOR/RENDERER_WEBGL)
  audio   rendering sound offline with OfflineAudioContext (almost never used for anything else)
  fonts   one script measuring text in 20+ different fonts (checking which fonts you have)
"""
from .capture import base_domain
from . import trackers

INIT_JS = r"""(() => {
  if (window.__clypeHooked) return;  window.__clypeHooked = true;
  const report = window.__clypeFP;   if (typeof report !== "function") return;
  const seen = new Set();
  // Which script called us: the first http(s) URL in the call stack (inline scripts show as the page URL).
  const caller = () => {
    const m = (new Error().stack || "").match(/https?:\/\/[^\s)]+?(?=:\d+:\d+)/);
    return m ? m[0] : location.href;
  };
  const send = (technique, detail) => {
    const script = caller(), key = technique + " " + script;
    if (seen.has(key)) return;  seen.add(key);          // each technique once per script
    try { report(technique, script, String(detail).slice(0, 120)); } catch (e) {}
  };
  const wrap = (proto, name, before) => {
    if (!proto || typeof proto[name] !== "function") return;
    const real = proto[name];
    proto[name] = function (...args) {
      try { before.call(this, args); } catch (e) {}     // our check must never break the site
      return real.apply(this, args);
    };
  };

  // Canvas: remember text drawn on each canvas, flag when it's read back.
  const C2D = window.CanvasRenderingContext2D && CanvasRenderingContext2D.prototype;
  const remember = function (args) { const c = this.canvas; if (c) c.__clypeText = (c.__clypeText || "") + String(args[0] || ""); };
  wrap(C2D, "fillText", remember);
  wrap(C2D, "strokeText", remember);
  const canvasCheck = (c) => {
    const t = (c && c.__clypeText) || "";
    if (c && c.width >= 16 && c.height >= 16 && t.length >= 10 && /[a-z]/i.test(t))
      send("canvas", `${c.width}x${c.height} canvas with text "${t.slice(0, 40)}" read back`);
  };
  const HC = window.HTMLCanvasElement && HTMLCanvasElement.prototype;
  wrap(HC, "toDataURL", function () { canvasCheck(this); });
  wrap(HC, "toBlob", function () { canvasCheck(this); });
  wrap(C2D, "getImageData", function () { canvasCheck(this.canvas); });

  // Fonts: one script measuring text in many different fonts.
  const fontsByScript = {};
  wrap(C2D, "measureText", function () {
    const s = caller(), set = (fontsByScript[s] = fontsByScript[s] || new Set());
    set.add(this.font);
    if (set.size === 20) send("fonts", "measured text in 20+ different fonts");
  });

  // WebGL: asking for the real GPU vendor / model.
  const gl = function (args) {
    if (args[0] === 37445 || args[0] === 37446) send("webgl", "read the GPU vendor/model (UNMASKED_*_WEBGL)");
  };
  wrap(window.WebGLRenderingContext && WebGLRenderingContext.prototype, "getParameter", gl);
  wrap(window.WebGL2RenderingContext && WebGL2RenderingContext.prototype, "getParameter", gl);

  // Audio: rendering a sound offline to read how this device processes it.
  const OAC = window.OfflineAudioContext || window.webkitOfflineAudioContext;
  wrap(OAC && OAC.prototype, "startRendering", function () { send("audio", "rendered audio offline (OfflineAudioContext)"); });
})();"""

TECHNIQUE_NAMES = {"canvas": "canvas", "webgl": "WebGL (GPU model)", "audio": "audio", "fonts": "font probing"}

# Bot / fraud protection vendors. They fingerprint to spot bots, which may count as strictly
# necessary (security), so we flag them as low and say so.
SECURITY_DOMAINS = {
    "akamaihd.net", "akamaized.net", "akstat.io", "cloudflare.com", "hcaptcha.com", "recaptcha.net",
    "perimeterx.net", "px-cdn.net", "px-cloud.net", "datadome.co", "captcha-delivery.com",
    "incapsula.com", "imperva.com", "arkoselabs.com", "funcaptcha.com", "kasada.io", "forter.com",
    "riskified.com", "sift.com", "siftscience.com", "threatmetrix.com", "online-metrix.net",
}
SECURITY_URL_PARTS = ("/recaptcha/", "/cdn-cgi/challenge-platform/", "/turnstile/")


def make_recorder(phase_state):
    """(events_list, handler). Expose handler to the page as window.__clypeFP;
    each call is tagged with the current phase, like requests are."""
    events = []

    def handler(technique, script, detail):
        if technique in TECHNIQUE_NAMES and len(events) < 200:
            events.append({"technique": technique, "script": str(script)[:300],
                           "detail": str(detail)[:120], "phase": phase_state["phase"]})

    return events, handler


def install(context, phase_state):
    """Hook fingerprinting APIs in every page/frame of this browser context. Call before goto.
    Returns the events list (filled in as the site runs)."""
    events, handler = make_recorder(phase_state)
    context.expose_function("__clypeFP", handler)
    context.add_init_script(INIT_JS)
    return events


def is_security(script, domain):
    return domain in SECURITY_DOMAINS or any(p in script for p in SECURITY_URL_PARTS)


def findings(events, site_domain):
    """One finding per script domain that fingerprinted, worded so it stays true if it's
    innocent (e.g. bot protection)."""
    by_domain = {}
    for e in events:
        d = base_domain(e["script"])
        g = by_domain.setdefault(d, {"techniques": set(), "phases": set(), "scripts": set(), "security": False})
        g["techniques"].add(e["technique"])
        g["phases"].add(e["phase"])
        g["scripts"].add(e["script"].split("?")[0])
        g["security"] |= is_security(e["script"], d)

    out = []
    for d, g in sorted(by_domain.items()):
        t = trackers.match(d, site_domain)
        who = t["company"] if t.get("is_tracker") else d
        techniques = ", ".join(TECHNIQUE_NAMES[x] for x in sorted(g["techniques"]))
        when = " and ".join({"before_consent": "before you answered the cookie banner",
                             "after_reject": "after you rejected cookies"}[p] for p in sorted(g["phases"], reverse=True))
        detail = f"Scripts from {d} ({', '.join(sorted(g['scripts']))[:200]}) used {techniques} fingerprinting {when}."
        law = "PECR reg. 6 (consent needed to access information on a device, not just cookies); ICO guidance on fingerprinting"
        if g["security"] or d == site_domain:
            severity = "low"
            detail += (" This may be fraud or bot protection, which can count as strictly necessary."
                       if g["security"] else
                       " It's the site's own script, which may be fraud or bot protection; we can't tell which.")
        elif t.get("category") in ("Advertising", "Session replay"):
            severity = "high"
        else:
            severity = "medium"
        out.append({"severity": severity, "title": f"{who} fingerprinted your device ({techniques})",
                    "detail": detail, "law": law})
    return out
