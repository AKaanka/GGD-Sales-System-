// Style audit, evaluated inside the Odoo page. Returns a text report.
// Part A: stylesheet rules for interaction states and pseudo-elements that
//         still set a literal colour and match an element on this page.
// Part B: computed-style scan for foreign colours in dark mode.
(async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  if (window.__ggd_prep) { await window.__ggd_prep(); await sleep(900); }
  const isDark = document.documentElement.dataset.ggdScheme === "dark";
  const out = [];

  // ---------------------------------------------------------------- Part A
  const STATE_RE = /:hover|:focus-visible|:focus-within|:focus|:active|::?before|::?after|::placeholder|\.o_dragged|\.ui-sortable|\.o_kanban_ghost|\.o_row_draggable|\.o_dragging|\.show\b|\.active\b|\.selected\b|\.o_selected|\.o-active|\.o_active|\.dropdown-item|\.o-dropdown-item|\.o_menu_item|\.o_searchview_facet|\.o-navigable/;
  const PROPS = ["background-color", "background", "background-image", "color", "border-color", "border-top-color", "border-bottom-color", "border-left-color", "border-right-color", "outline-color", "outline", "box-shadow", "border", "border-bottom", "border-top", "border-left", "border-right", "fill", "stroke"];
  const LITERAL = /#[0-9a-f]{3,8}\b|rgba?\(|hsla?\(|\b(white|black|silver|gray|grey|red|blue|green|purple)\b/i;
  const strip = (sel) => sel
    .replace(/::?(before|after|placeholder|marker)/g, "")
    .replace(/:(hover|focus-visible|focus-within|focus|active|visited|focus-visible)/g, "")
    .replace(/:not\([^)]*\)/g, "")
    .replace(/:(checked|disabled|enabled|empty|first-child|last-child|nth-child\([^)]*\)|nth-of-type\([^)]*\)|first-of-type|last-of-type|only-child|is\(([^)]*)\)|where\(([^)]*)\))/g, "$2$3");
  const seen = new Map();
  const walk = (rules, sheetName) => {
    for (const r of rules) {
      if (r.cssRules && (r.type === CSSRule.MEDIA_RULE || r.type === CSSRule.SUPPORTS_RULE)) { walk(r.cssRules, sheetName); continue; }
      if (!r.selectorText || !r.style) continue;
      if (!STATE_RE.test(r.selectorText)) continue;
      const hits = [];
      for (const p of PROPS) {
        const v = r.style.getPropertyValue(p);
        if (!v || v.includes("var(--ggd") || v === "transparent" || v === "inherit" || v === "none" || v === "currentcolor") continue;
        if (LITERAL.test(v)) hits.push(`${p}: ${v.slice(0, 60)}${r.style.getPropertyPriority(p) ? " !important" : ""}`);
      }
      if (!hits.length) continue;
      let matched = 0;
      for (const part of r.selectorText.split(",")) {
        const base = strip(part.trim()).trim();
        if (!base) continue;
        try { matched += document.querySelectorAll(base).length; } catch (e) { try { matched += document.querySelectorAll(base.split(/\s+/)[0]).length ? 0.5 : 0; } catch (e2) {} }
      }
      if (!matched) continue;
      const key = r.selectorText + "|" + hits.join(";");
      if (seen.has(key)) continue;
      seen.set(key, true);
      out.push(`A ${matched}x  ${r.selectorText.slice(0, 110)}\n      ${hits.join(" | ")}`);
    }
  };
  for (const sh of document.styleSheets) { try { walk(sh.cssRules, sh.href || "inline"); } catch (e) {} }

  // ---------------------------------------------------------------- Part B
  const parse = (c) => { const m = c && c.match(/rgba?\((\d+), (\d+), (\d+)(?:, ([\d.]+))?\)/); return m ? { r: +m[1], g: +m[2], b: +m[3], a: m[4] === undefined ? 1 : +m[4] } : null; };
  const lum = (c) => (c.r * 299 + c.g * 587 + c.b * 114) / 255000;
  const near = (c, t, d = 40) => Math.abs(c.r - t[0]) + Math.abs(c.g - t[1]) + Math.abs(c.b - t[2]) < d;
  const ODOO = [[113, 75, 103], [1, 126, 132], [102, 16, 242], [33, 37, 41], [222, 226, 230], [233, 236, 239], [248, 249, 250], [206, 212, 218], [173, 181, 189], [108, 117, 125], [73, 80, 87]];
  const visible = (el) => { const r = el.getBoundingClientRect(); return r.width > 4 && r.height > 4 && r.bottom > 0 && r.top < innerHeight; };
  const effectiveBg = (el) => { let e = el; while (e && e !== document.documentElement) { const c = parse(getComputedStyle(e).backgroundColor); if (c && c.a >= 0.5) return c; e = e.parentElement; } return isDark ? { r: 13, g: 16, b: 23, a: 1 } : { r: 242, g: 244, b: 249, a: 1 }; };
  const label = (el) => el.tagName.toLowerCase() + "." + [...el.classList].filter((c) => !/^(d-|flex|align|justify|position|w-|h-|p[xytblrse]?-|m[xytblrse]?-|text-truncate|o-)/.test(c)).slice(0, 4).join(".");
  const bseen = new Set();
  const report = (kind, el, detail) => { const k = kind + label(el) + detail; if (bseen.has(k)) return; bseen.add(k); out.push(`B ${kind}  ${label(el)}  ${detail}`); };
  const CHECK_PSEUDO = ["::before", "::after"];
  for (const el of document.querySelectorAll("body *")) {
    if (!visible(el)) continue;
    const cs = getComputedStyle(el);
    const styles = [[cs, ""]];
    for (const ps of CHECK_PSEUDO) { const p = getComputedStyle(el, ps); if (p.content && p.content !== "none" && p.content !== "normal") styles.push([p, ps]); }
    for (const [st, ps] of styles) {
      const bg = parse(st.backgroundColor);
      if (bg && bg.a >= 0.5) {
        if (ODOO.some((t) => near(bg, t, 24))) report("odoo-colour-bg", el, `${ps} ${st.backgroundColor}`);
        else if (isDark && lum(bg) > 0.55 && !(bg.g > bg.r + 30 && bg.b > bg.r)) report("light-bg-in-dark", el, `${ps} ${st.backgroundColor}`);
      }
      const fg = parse(st.color);
      if (fg && fg.a >= 0.5 && el.textContent.trim() && !ps) {
        const ebg = effectiveBg(el);
        const contrast = Math.abs(lum(fg) - lum(ebg));
        if (contrast < 0.25) report("low-contrast-text", el, `${st.color} on ${ebg.r},${ebg.g},${ebg.b}`);
        if (ODOO.slice(0, 3).some((t) => near(fg, t, 24))) report("odoo-colour-text", el, st.color);
      }
      for (const side of ["Top", "Bottom", "Left", "Right"]) {
        if (parseFloat(st[`border${side}Width`]) > 0 && st[`border${side}Style`] !== "none") {
          const bc = parse(st[`border${side}Color`]);
          if (bc && bc.a >= 0.5) {
            if (ODOO.some((t) => near(bc, t, 24))) report("odoo-colour-border", el, `${ps} ${side} ${st[`border${side}Color`]}`);
            else if (isDark && lum(bc) > 0.6) report("light-border-in-dark", el, `${ps} ${side} ${st[`border${side}Color`]}`);
          }
          break;
        }
      }
      if (st.boxShadow && st.boxShadow !== "none") { const sc = parse(st.boxShadow); if (sc && sc.a >= 0.5 && (ODOO.some((t) => near(sc, t, 24)) || (isDark && lum(sc) > 0.6))) report("shadow-colour", el, `${ps} ${st.boxShadow.slice(0, 50)}`); }
      if (st.outlineStyle !== "none" && parseFloat(st.outlineWidth) > 0) { const oc = parse(st.outlineColor); if (oc && ODOO.some((t) => near(oc, t, 24))) report("odoo-colour-outline", el, st.outlineColor); }
    }
  }
  return out.join("\n") || "clean";
})()
