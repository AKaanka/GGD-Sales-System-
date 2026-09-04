// Drive the local Odoo through headless Chrome over the DevTools protocol.
// No dependencies beyond Node 22 (for the built-in WebSocket) and a Chrome.
//
// usage: node odoo-shot.mjs <session_id> <light|dark> <tone|-> <outdir> <name=path[@@step]> ...
//
// Each page argument navigates to http://<ODOO_HOST>:<port><path> (default
// localhost:8069), optionally runs a step, then writes <outdir>/<name>.png,
// <name>.dom.txt (an outline of the o_* classes) and <name>.errors.txt (the
// console errors seen while on that page). A step is one of:
//
//   @@<js>                          evaluate the expression; a string result goes to <name>.js.txt
//   @@@file:<path>|<prep js>        evaluate a file after setting window.__ggd_prep to the prep body
//   @@@hover:<selector>|<js>        move the mouse onto the element, then run js
//   @@@drag:<from sel>|<to sel>|<js> press on one element, move onto the other, run js, release
//   @@@force:<sel>;<sel>;...        force :hover/:focus/:focus-visible/:active on the first two
//                                   matches of each selector and report Odoo-coloured results
//
// Environment: CHROME (binary path), ODOO_HOST (default localhost:8069),
// VW and VH (viewport, default 1440x900). See README.md for the session id.
import { spawn } from "node:child_process";
import { writeFileSync, mkdirSync, readFileSync } from "node:fs";

const [sid, scheme, tone, outdir, ...pages] = process.argv.slice(2);
const VW = +(process.env.VW || 1440), VH = +(process.env.VH || 900);
const CHROME = process.env.CHROME || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const HOST = process.env.ODOO_HOST || "localhost:8069";
const PORT = 9333;
mkdirSync(outdir, { recursive: true });

const chrome = spawn(CHROME, [
  "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
  `--remote-debugging-port=${PORT}`, `--window-size=${VW},${VH}`,
  `--user-data-dir=${outdir}/profile`, "about:blank",
], { stdio: "ignore" });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function wsUrl() {
  for (let i = 0; i < 40; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json`);
      const list = await r.json();
      const p = list.find((t) => t.type === "page");
      if (p) return p.webSocketDebuggerUrl;
    } catch {}
    await sleep(250);
  }
  throw new Error("chrome did not answer");
}

const ws = new WebSocket(await wsUrl());
await new Promise((r) => (ws.onopen = r));
let id = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const send = (method, params = {}) => new Promise((res) => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });

await send("Page.enable");
await send("Network.enable");
await send("Emulation.setDeviceMetricsOverride", { width: VW, height: VH, deviceScaleFactor: 1, mobile: false });
await send("Runtime.enable");
await send("Log.enable");
const errors = [];
ws.addEventListener("message", (ev) => { const m = JSON.parse(ev.data); if (m.method === "Runtime.exceptionThrown") errors.push("EXC " + (m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text).split("\n")[0]); if (m.method === "Runtime.consoleAPICalled" && (m.params.type === "error" || m.params.type === "warning")) errors.push(m.params.type.toUpperCase() + " " + m.params.args.map(a => a.value || a.description || "").join(" ").slice(0, 200)); if (m.method === "Log.entryAdded" && m.params.entry.level === "error") errors.push("LOG " + m.params.entry.text.slice(0, 200)); });
await send("Network.setCookie", { name: "session_id", value: sid, domain: HOST.split(":")[0], path: "/" });
await send("Network.setCookie", { name: "color_scheme", value: scheme, domain: HOST.split(":")[0], path: "/" });
if (tone && tone !== "-") {
  await send("Page.addScriptToEvaluateOnNewDocument", { source: `try{localStorage.setItem("ggd_tone", ${JSON.stringify(tone)})}catch(e){}` });
}

const OUTLINE = `(() => {
  const seen = new Set(); const out = [];
  const walk = (el, depth) => {
    if (depth > 9 || out.length > 400) return;
    const cls = [...el.classList].filter(c => /^o[-_]/.test(c) || /^btn|^dropdown|^nav|^table|^badge|^card|^modal|^form-|^input/.test(c)).slice(0, 5).join(".");
    if (cls && !seen.has(cls + depth)) { seen.add(cls + depth); out.push("  ".repeat(depth) + el.tagName.toLowerCase() + "." + cls); }
    for (const c of el.children) walk(c, cls ? depth + 1 : depth);
  };
  walk(document.body, 0);
  return out.join("\\n");
})()`;

var dragRelease = null;
for (const spec of pages) {
  const eq = spec.indexOf("=");
  const name = spec.slice(0, eq), rest = spec.slice(eq + 1);
  let [path, js] = rest.split("@@");
  if (js && js.startsWith("@file:")) {
    // "@file:<path>|<prep js>": the file is evaluated after window.__ggd_prep is set to the prep body
    const [file, prep = ""] = js.slice(6).split("|");
    js = `window.__ggd_prep = async () => { ${prep} };\n` + readFileSync(file, "utf8");
  }
  await send("Page.navigate", { url: `http://${HOST}${path}` });
  await sleep(6000);
  if (js && js.startsWith("@force:")) {
    // "@force:sel1;sel2;...": force :hover / :focus / :focus-visible / :active on the first two matches of each
    // selector and report computed colours that are Odoo's, not the theme's.
    await send("DOM.enable"); await send("CSS.enable");
    const doc = await send("DOM.getDocument", { depth: 0 });
    const root = doc.result.root.nodeId;
    const lines = [];
    const SNAP = `function() { const cs = getComputedStyle(this); return JSON.stringify({bg: cs.backgroundColor, color: cs.color, border: cs.borderTopColor + "/" + cs.borderBottomColor, shadow: cs.boxShadow, outline: cs.outlineColor + " " + cs.outlineStyle + " " + cs.outlineWidth, bgi: cs.backgroundImage.slice(0, 40), label: this.tagName.toLowerCase() + "." + [...this.classList].slice(0, 4).join(".")}); }`;
    const ODOO = [[113,75,103],[113,99,158],[125,114,160],[1,126,132],[102,16,242],[33,37,41],[222,226,230],[233,236,239],[248,249,250],[206,212,218],[173,181,189],[108,117,125],[73,80,87],[221,219,232],[241,243,245],[241,239,245],[71,62,100],[79,69,111]];
    const near = (str) => { const m = str && str.match(/rgba?\((\d+), (\d+), (\d+)(?:, ([\d.]+))?\)/); if (!m) return false; if (m[4] !== undefined && +m[4] < 0.2) return false; return ODOO.some(t => Math.abs(+m[1]-t[0]) + Math.abs(+m[2]-t[1]) + Math.abs(+m[3]-t[2]) < 18); };
    for (const sel of js.slice(7).split(";")) {
      let nodes; try { nodes = (await send("DOM.querySelectorAll", { nodeId: root, selector: sel })).result.nodeIds.slice(0, 2); } catch { continue; }
      for (const nodeId of nodes) {
        const obj = await send("DOM.resolveNode", { nodeId });
        const objectId = obj.result?.object?.objectId; if (!objectId) continue;
        const snap = async () => JSON.parse((await send("Runtime.callFunctionOn", { objectId, functionDeclaration: SNAP, returnByValue: true })).result.result.value);
        const base = await snap();
        for (const state of ["hover", "focus", "focus-visible", "active"]) {
          await send("CSS.forcePseudoState", { nodeId, forcedPseudoClasses: [state] });
          await sleep(30);
          const st = await snap();
          const bad = Object.entries(st).filter(([k, v]) => k !== "label" && v !== base[k] && near(v)).map(([k, v]) => `${k}=${v.slice(0, 60)}`);
          if (bad.length) lines.push(`${sel}  [${state}]  ${st.label}  ${bad.join(" | ")}`);
        }
        await send("CSS.forcePseudoState", { nodeId, forcedPseudoClasses: [] });
      }
    }
    writeFileSync(`${outdir}/${name}.js.txt`, lines.join("\n") || "clean");
    js = "";
  }
  if (js && js.startsWith("@hover:")) {
    // "@hover:<selector>|<js after>": move the mouse onto the element, then screenshot with it there
    const [sel, after = ""] = js.slice(7).split("|");
    const r = JSON.parse((await send("Runtime.evaluate", { expression: `(() => { const r = document.querySelector(${JSON.stringify(sel)}).getBoundingClientRect(); return JSON.stringify({x: r.x + r.width / 2, y: r.y + r.height / 2}); })()`, returnByValue: true })).result.result.value);
    await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: r.x, y: r.y });
    await sleep(500);
    js = after;
  }
  if (js && js.startsWith("@drag:")) {
    // "@drag:<from selector>|<to selector>|<js after>": press on the first, move to the second, hold, then screenshot
    const [fromSel, toSel, after = ""] = js.slice(6).split("|");
    const rect = async (sel) => (await send("Runtime.evaluate", { expression: `(() => { const r = document.querySelector(${JSON.stringify(sel)}).getBoundingClientRect(); return JSON.stringify({x: r.x + r.width / 2, y: r.y + r.height / 2}); })()`, returnByValue: true })).result.result.value;
    const a = JSON.parse(await rect(fromSel)), b = JSON.parse(await rect(toSel));
    await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: a.x, y: a.y });
    await send("Input.dispatchMouseEvent", { type: "mousePressed", x: a.x, y: a.y, button: "left", clickCount: 1 });
    for (let i = 1; i <= 12; i++) { await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: a.x + (b.x - a.x) * i / 12, y: a.y + (b.y - a.y) * i / 12, button: "left" }); await sleep(60); }
    await sleep(500);
    js = after;
    var dragRelease = { x: a.x, y: a.y };
  }
  if (js) {
    const r = await send("Runtime.evaluate", { expression: js, awaitPromise: true, returnByValue: true });
    if (typeof r.result?.result?.value === "string") writeFileSync(`${outdir}/${name}.js.txt`, r.result.result.value);
    else writeFileSync(`${outdir}/${name}.js.txt`, "EVAL-ERROR " + JSON.stringify(r.result?.exceptionDetails?.exception?.description || r.result?.exceptionDetails?.text || r.result?.result || r).slice(0, 400));
    await sleep(1500);
  }
  const shot = await send("Page.captureScreenshot", { format: "png" });
  writeFileSync(`${outdir}/${name}.png`, Buffer.from(shot.result.data, "base64"));
  if (typeof dragRelease !== "undefined" && dragRelease) { await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: dragRelease.x, y: dragRelease.y, button: "left" }); await sleep(200); await send("Input.dispatchMouseEvent", { type: "mouseReleased", x: dragRelease.x, y: dragRelease.y, button: "left", clickCount: 1 }); dragRelease = null; await sleep(800); }
  const dom = await send("Runtime.evaluate", { expression: OUTLINE, returnByValue: true });
  writeFileSync(`${outdir}/${name}.dom.txt`, dom.result.result.value || "");
  writeFileSync(`${outdir}/${name}.errors.txt`, errors.join("\n")); const n = errors.length; errors.length = 0;
  console.log(`${name}: png + dom, ${n} console errors`);
}
ws.close(); chrome.kill();
