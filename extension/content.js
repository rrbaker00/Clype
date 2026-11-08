// Clype extension, content script. Runs in every page, but only to SHOW the critical-issue box in
// the top-left corner. It reads nothing from the page and changes nothing else.

(() => {
  let box = null;

  function show(alert) {
    if (box || !alert) return;                          // one box per page
    box = document.createElement("div");
    const root = box.attachShadow({ mode: "closed" });  // shadow DOM: the site's CSS can't restyle it
    const style = document.createElement("style");
    style.textContent = `
      .card { position: fixed; top: 16px; left: 16px; z-index: 2147483647; width: 340px; max-width: calc(100vw - 32px);
              font: 14px/1.4 system-ui, sans-serif; color: #fff; background: #1f1029; border: 2px solid #e11d48;
              border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,.4); padding: 14px 16px; }
      .top { display: flex; align-items: center; gap: 8px; font-weight: 700; }
      .pill { background: #e11d48; border-radius: 99px; padding: 1px 8px; font-size: 12px; }
      .x { margin-left: auto; background: none; border: 0; color: #fff; font-size: 18px; cursor: pointer; }
      ul { margin: 8px 0; padding-left: 18px; color: #f5d0dc; }
      a { display: inline-block; margin-top: 4px; color: #fff; background: #7c3aed; padding: 6px 12px;
          border-radius: 8px; text-decoration: none; font-weight: 600; }`;
    const card = document.createElement("div");
    card.className = "card";
    card.setAttribute("role", "alert");
    const top = document.createElement("div");
    top.className = "top";
    const pill = document.createElement("span");
    pill.className = "pill";
    pill.textContent = "CRITICAL";
    const title = document.createElement("span");
    title.textContent = `Clype: ${alert.site}`;           // textContent everywhere: no HTML injection
    const close = document.createElement("button");
    close.className = "x";
    close.title = "Dismiss";
    close.textContent = "×";
    close.onclick = () => {
      box.remove();
      browser.runtime.sendMessage({ type: "clype-dismiss", auditId: alert.auditId });
    };
    top.append(pill, title, close);
    const list = document.createElement("ul");
    for (const f of alert.findings.slice(0, 3)) {
      const li = document.createElement("li");
      li.textContent = f.title;
      list.append(li);
    }
    const link = document.createElement("a");
    link.href = alert.reportUrl;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "View report";
    card.append(top, list, link);
    root.append(style, card);
    document.documentElement.append(box);
  }

  // ---------- Phase 2: click "reject" on the cookie banner in YOUR tab ----------
  // Same rules as the agent (agent/consent.py): reject-type phrases only, the button must be inside
  // a cookie/consent banner (or a consent iframe), and anything mentioning accept/pay is never clicked.
  const REJECT_PHRASES = ["reject all", "reject all cookies", "reject additional cookies", "reject optional cookies",
    "reject non-essential cookies", "decline all", "refuse all", "use necessary cookies only", "necessary cookies only",
    "only necessary cookies", "essential cookies only", "necessary only", "only necessary", "essential only",
    "strictly necessary only", "decline optional", "decline", "disagree", "reject", "refuse"];
  const NEVER = /accept|agree|allow|ok\b|got it|subscribe|pay|premium|continue with/i;
  const COOKIE = /cookie|consent|privacy|gdpr|tracking|personal data/i;
  const CMP_FRAME = /consent|cmp|cookie|privacy|sourcepoint|onetrust|didomi|trustarc|quantcast|usercentrics/i;
  const inConsentFrame = window !== window.top && CMP_FRAME.test(location.href);

  function inCookieContext(el) {
    if (inConsentFrame) return true;
    for (let n = el, i = 0; i < 6 && n && n !== document.body; i++, n = n.parentElement || n.getRootNode()?.host) {
      const t = n.innerText || "";
      if (t.length > 4000) break;                         // reached the whole page: too broad
      if (COOKIE.test(t) || COOKIE.test(n.id || "") || COOKIE.test(String(n.className || ""))) return true;
    }
    return false;
  }

  // Buttons/links, including inside open shadow DOMs and design-system web components such as
  // <pie-button>/<pie-link> (just-eat.co.uk): their text sits on the custom element, not the inner <button>.
  const CUSTOM_CLICKABLE = /-(button|link)$/i;
  function candidates(root, out = []) {
    for (const el of root.querySelectorAll("button, a, [role=button], input[type=button], input[type=submit]")) out.push(el);
    for (const el of root.querySelectorAll("*")) {
      if (CUSTOM_CLICKABLE.test(el.tagName)) out.push(el);
      if (el.shadowRoot) candidates(el.shadowRoot, out);
    }
    return out;
  }
  const isLink = (el) => el.tagName === "A" || /-LINK$/i.test(el.tagName);

  const labelOf = (el) => ((el.innerText || "").trim() || el.textContent || el.value || el.getAttribute("aria-label") || "")
    .replace(/\s+/g, " ").trim().toLowerCase();
  const visible = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== "hidden"; };

  function findReject() {
    // Real buttons before links: an inline "Necessary only" link in the banner text may just open a page.
    const els = candidates(document).filter(visible).sort((x, y) => isLink(x) - isLink(y));
    for (const phrase of REJECT_PHRASES) {
      for (const el of els) {
        const label = labelOf(el);
        if (!label || label.length > phrase.length + 25 || NEVER.test(label)) continue;
        if ((label === phrase || label.startsWith(phrase)) && inCookieContext(el)) return el;
      }
    }
    return null;
  }

  function autoReject() {
    let tries = 0;
    const timer = setInterval(() => {
      const el = findReject();
      if (el) {
        clearInterval(timer);
        const label = labelOf(el);
        el.click();
        browser.runtime.sendMessage({ type: "clype-rejected", label });
      } else if (++tries >= 15) {
        clearInterval(timer);                               // no banner (or already answered)
      }
    }, 1000);
  }

  // The background script pushes the alert when an audit finishes...
  browser.runtime.onMessage.addListener((msg) => { if (msg.type === "clype-alert" && window === window.top) show(msg); });
  // ...and on load we ask: show the critical box? click reject on the banner?
  browser.runtime.sendMessage({ type: "clype-hello" }).then((r) => {
    if (r?.alert && window === window.top) show(r.alert);
    if (r?.autoReject) autoReject();
  }).catch(() => {});
})();
