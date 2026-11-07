// Helpers shared by both pages. Loaded before script.js / audit.js.

// Make an element in one line.
//   el("div", { class: "card" }, "some text", otherElement)
// props: attributes (class, href, ...). Anything starting with "on" becomes an event, e.g. onclick.
// children: strings are added as plain TEXT (never HTML), so data from websites can't inject code.
function el(tag, props = {}, ...children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v === null || v === undefined || v === false) continue;  // skip empty props
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);  // "onclick" -> "click"
    else e.setAttribute(k, v);
  }
  for (const c of children.flat(Infinity)) {  // .flat(Infinity) lets us pass (nested) arrays of children too
    if (c === null || c === undefined || c === false) continue;
    e.append(c instanceof Node ? c : String(c));  // element -> add it; anything else -> add as text
  }
  return e;
}

// "https://www.bbc.co.uk" -> "www.bbc.co.uk". Falls back to the raw text if it isn't a URL.
function host(url) {
  try { return new URL(url).hostname; } catch { return url ?? "unknown site"; }
}

// "2026-11-07T12:00:00Z" -> "7 Nov 2026, 12:00" in the viewer's local time.
function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

// Show a value, or a dash if it's missing.
const show = (v) => (v === null || v === undefined ? "—" : v);
// true/false -> Yes/No (missing -> dash).
const yesNo = (v) => (v === true ? "Yes" : v === false ? "No" : "—");
// Only allow http(s) links. Blocks "javascript:..." links a hostile site could put in its data.
const safeUrl = (u) => (/^https?:\/\//i.test(u ?? "") ? u : null);

// Generic fallback: turns ANY JSON value into HTML (used for the "raw data" section).
//   list of objects -> table, object -> key/value list, plain value -> text.
function render(value) {
  if (value === null || value === undefined) return el("span", {}, "—");
  if (Array.isArray(value)) {
    if (value.length === 0) return el("span", { class: "muted" }, "(none)");
    if (typeof value[0] !== "object") return el("span", {}, value.join(", "));
    const cols = [...new Set(value.flatMap((r) => Object.keys(r)))];  // every key used by any row
    return el("div", { class: "scroll" }, el("table", {},
      el("tr", {}, cols.map((c) => el("th", {}, c))),
      value.map((r) => el("tr", {}, cols.map((c) => el("td", {}, render(r[c])))))));
  }
  if (typeof value === "object") {
    return el("dl", {}, Object.entries(value).map(([k, v]) => [el("dt", {}, k), el("dd", {}, render(v))]));
  }
  return el("span", {}, String(value));
}
