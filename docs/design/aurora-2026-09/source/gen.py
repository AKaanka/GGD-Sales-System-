#!/usr/bin/env python3
"""Generate the GGD Aurora design artboards (.dc.html) from one shared system."""
import json, pathlib

OUT = pathlib.Path(__file__).parent

# ------------------------------------------------------------------ themes
ACCENT_D = "#4fd6c8"; AMBER_D = "#f0b45c"; ACCENT2_D = "#a08cff"; ROSE_D = "#f27b8e"
DARK = dict(
    bg="#0d1017", g1="rgba(66, 214, 198, 0.16)", g2="rgba(148, 118, 255, 0.15)",
    glass="rgba(255,255,255,0.055)", glass2="rgba(255,255,255,0.085)",
    border="rgba(255,255,255,0.10)", border2="rgba(255,255,255,0.16)",
    nav="rgba(16,19,28,0.62)", text="#e9edf4", muted="#9aa4b8", faint="#6b7488",
    shadow="0 10px 32px rgba(0,0,0,0.38)", input="rgba(255,255,255,0.05)",
    scheme="dark", p_ok=ACCENT_D, p_wait=AMBER_D, p_rev=ACCENT2_D, p_stop=ROSE_D,
)
LIGHT = dict(
    bg="#f2f4f9", g1="rgba(66, 214, 198, 0.26)", g2="rgba(148, 118, 255, 0.20)",
    glass="rgba(255,255,255,0.58)", glass2="rgba(255,255,255,0.78)",
    border="rgba(20,24,34,0.08)", border2="rgba(20,24,34,0.14)",
    nav="rgba(255,255,255,0.62)", text="#141826", muted="#5b6478", faint="#8a93a6",
    shadow="0 10px 32px rgba(20,24,34,0.10)", input="rgba(255,255,255,0.7)",
    scheme="light", p_ok="#0f8f83", p_wait="#a9640a", p_rev="#5f48d6", p_stop="#c2374f",
)
ACCENT_D = "#4fd6c8"; AMBER_D = "#f0b45c"; ACCENT2_D = "#a08cff"; ROSE_D = "#f27b8e"
ACCENT = "#4fd6c8"     # oklch(0.80 0.11 185)
ACCENT2 = "#a08cff"    # oklch(0.72 0.14 290)
AMBER = "#f0b45c"
ROSE = "#f27b8e"

def css(t):
    on_dark = t["scheme"] == "dark"
    acc_text = "#0b1512" if on_dark else "#0b1512"
    return f"""
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500&display=swap');
* {{ box-sizing: border-box; }}
body {{ margin: 0; width: 1440px; height: 900px; overflow: hidden; color-scheme: {t['scheme']};
  font-family: Manrope, "Segoe UI", "Helvetica Neue", Arial, sans-serif; font-size: 13px; line-height: 1.45;
  color: {t['text']}; background: {t['bg']};
  background-image:
    radial-gradient(900px 620px at -6% -10%, {t['g1']}, transparent 60%),
    radial-gradient(1000px 700px at 108% 108%, {t['g2']}, transparent 62%),
    radial-gradient(600px 400px at 60% 40%, rgba(79,214,200,0.05), transparent 70%);
  -webkit-font-smoothing: antialiased; }}
a {{ color: {ACCENT}; text-decoration: none; }} a:hover {{ color: {ACCENT2}; }}
.mono {{ font-family: "IBM Plex Mono", "SF Mono", Menlo, monospace; font-size: 11.5px; letter-spacing: 0; }}
.glass {{ background: {t['glass']}; border: 1px solid {t['border']}; border-radius: 18px;
  backdrop-filter: blur(22px) saturate(150%); -webkit-backdrop-filter: blur(22px) saturate(150%); }}
.nav {{ height: 54px; margin: 12px 18px 0; padding: 0 10px 0 16px; border-radius: 16px;
  background: {t['nav']}; border: 1px solid {t['border2']}; box-shadow: {t['shadow']};
  backdrop-filter: blur(24px) saturate(160%); -webkit-backdrop-filter: blur(24px) saturate(160%);
  display: flex; align-items: center; gap: 6px; }}
.brand {{ display: flex; align-items: center; gap: 10px; margin-right: 18px; font-weight: 800; letter-spacing: .02em; font-size: 14px; }}
.brand .mark {{ width: 26px; height: 26px; border-radius: 8px; background: linear-gradient(135deg, {ACCENT}, {ACCENT2}); display: grid; place-items: center; }}
.navitem {{ padding: 8px 12px; border-radius: 10px; color: {t['muted']}; font-weight: 600; font-size: 13px; }}
.navitem.on {{ color: {t['text']}; background: {t['glass2']}; border: 1px solid {t['border']}; }}
.navright {{ margin-left: auto; display: flex; align-items: center; gap: 6px; }}
.icobtn {{ width: 36px; height: 36px; border-radius: 10px; display: grid; place-items: center; color: {t['muted']}; }}
.icobtn:hover {{ background: {t['glass2']}; color: {t['text']}; }}
.avatar {{ width: 30px; height: 30px; border-radius: 9px; background: linear-gradient(135deg, {ACCENT2}, {ACCENT}); display: grid; place-items: center; font-weight: 800; font-size: 11px; color: {acc_text}; margin-left: 4px; }}
.cp {{ display: flex; align-items: center; gap: 14px; padding: 22px 26px 14px; }}
.cp h1 {{ margin: 0; font-size: 24px; font-weight: 800; letter-spacing: -.02em; }}
.cp .crumb {{ color: {t['faint']}; font-weight: 600; }}
.search {{ margin-left: auto; width: 380px; height: 40px; border-radius: 12px; display: flex; align-items: center; gap: 10px; padding: 0 12px; background: {t['input']}; border: 1px solid {t['border']}; color: {t['faint']}; }}
.search .chip {{ margin-left: 0; }}
.seg {{ display: flex; padding: 3px; border-radius: 12px; background: {t['glass']}; border: 1px solid {t['border']}; }}
.seg > div {{ width: 34px; height: 32px; border-radius: 9px; display: grid; place-items: center; color: {t['faint']}; }}
.seg > div.on {{ background: {t['glass2']}; color: {t['text']}; border: 1px solid {t['border']}; }}
.btn {{ height: 38px; padding: 0 16px; border-radius: 12px; display: inline-flex; align-items: center; gap: 8px; font-weight: 700; font-size: 13px; border: 1px solid {t['border']}; background: {t['glass']}; color: {t['text']}; }}
.btn.primary {{ background: {ACCENT}; color: {acc_text}; border-color: transparent; box-shadow: 0 6px 18px rgba(79,214,200,0.28); }}
.btn.danger {{ color: {t["p_stop"]}; }}
.btn.sm {{ height: 32px; padding: 0 12px; font-size: 12px; border-radius: 10px; }}
.chip {{ display: inline-flex; align-items: center; gap: 6px; height: 28px; padding: 0 10px; border-radius: 999px; font-size: 12px; font-weight: 600; border: 1px solid {t['border']}; background: {t['glass']}; color: {t['muted']}; white-space: nowrap; }}
.chip.on {{ color: {t['text']}; border-color: rgba(79,214,200,0.45); background: rgba(79,214,200,0.12); }}
.chip .n {{ font-size: 11px; padding: 1px 6px; border-radius: 999px; background: {t['glass2']}; color: {t['text']}; }}
.pill {{ display: inline-flex; align-items: center; gap: 5px; height: 22px; padding: 0 9px; border-radius: 999px; font-size: 11px; font-weight: 700; letter-spacing: .01em; white-space: nowrap; }}
.pill i {{ width: 6px; height: 6px; border-radius: 50%; background: currentColor; display: block; }}
.pill.ok {{ color: {t["p_ok"]}; background: rgba(79,214,200,0.13); }}
.pill.wait {{ color: {t["p_wait"]}; background: rgba(240,180,92,0.14); }}
.pill.review {{ color: {t["p_rev"]}; background: rgba(160,140,255,0.15); }}
.pill.stop {{ color: {t["p_stop"]}; background: rgba(242,123,142,0.14); }}
.pill.dim {{ color: {t['muted']}; background: {t['glass2']}; }}
.score {{ display: inline-flex; align-items: center; gap: 6px; font-weight: 700; font-size: 12px; color: {t['text']}; }}
.score .bar {{ width: 46px; height: 5px; border-radius: 999px; background: {t['glass2']}; overflow: hidden; }}
.score .bar > div {{ height: 100%; border-radius: 999px; background: linear-gradient(90deg, {ACCENT2}, {ACCENT}); }}
.muted {{ color: {t['muted']}; }} .faint {{ color: {t['faint']}; }}
.hair {{ border-top: 1px solid {t['border']}; }}
.label {{ font-size: 11px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: {t['faint']}; }}
.field {{ display: flex; flex-direction: column; gap: 4px; }}
.field .v {{ font-size: 13px; font-weight: 500; }}
.input {{ height: 36px; border-radius: 10px; padding: 0 12px; display: flex; align-items: center; background: {t['input']}; border: 1px solid {t['border']}; font-weight: 500; }}
.input.area {{ height: auto; padding: 10px 12px; align-items: flex-start; line-height: 1.5; }}
.tab {{ padding: 10px 2px; font-weight: 700; color: {t['faint']}; border-bottom: 2px solid transparent; }}
.tab.on {{ color: {t['text']}; border-bottom-color: {ACCENT}; }}
.card {{ background: {t['glass2']}; border: 1px solid {t['border']}; border-radius: 14px; padding: 13px 14px; display: flex; flex-direction: column; gap: 9px; }}
.card.hot {{ border-color: rgba(79,214,200,0.5); box-shadow: 0 0 0 3px rgba(79,214,200,0.10), 0 10px 26px rgba(0,0,0,0.18); }}
.card .t {{ font-weight: 700; font-size: 13.5px; letter-spacing: -.01em; }}
.col {{ display: flex; flex-direction: column; gap: 10px; padding: 12px; width: 268px; flex: none; }}
.colhead {{ display: flex; align-items: center; gap: 8px; padding: 2px 4px 4px; }}
.colhead .t {{ font-weight: 800; font-size: 13px; }}
.colhead .cnt {{ font-size: 11px; font-weight: 700; color: {t['muted']}; padding: 2px 7px; border-radius: 999px; background: {t['glass2']}; }}
.prog {{ height: 3px; border-radius: 999px; background: {t['glass2']}; margin: 0 4px 4px; overflow: hidden; display: flex; }}
.prog > div {{ height: 100%; }}
table {{ border-collapse: collapse; width: 100%; }}
th {{ text-align: left; font-size: 11px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: {t['faint']}; padding: 12px 14px; border-bottom: 1px solid {t['border']}; }}
td {{ padding: 12px 14px; border-bottom: 1px solid {t['border']}; vertical-align: middle; }}
tr.sel td {{ background: rgba(79,214,200,0.06); }}
.ring {{ width: 64px; height: 64px; border-radius: 50%; display: grid; place-items: center; font-weight: 800; font-size: 18px;
  background: conic-gradient({ACCENT} 0 var(--p), {t['glass2']} var(--p) 100%); }}
.ring > div {{ width: 52px; height: 52px; border-radius: 50%; display: grid; place-items: center; background: {t['bg']}; }}
.step {{ display: flex; align-items: center; gap: 6px; font-weight: 700; font-size: 12px; color: {t['faint']}; }}
.step.done {{ color: {t['muted']}; }} .step.on {{ color: {t['text']}; }}
.step i {{ width: 8px; height: 8px; border-radius: 50%; background: {t['border2']}; display: block; }}
.step.done i {{ background: {ACCENT}; }} .step.on i {{ background: {ACCENT}; box-shadow: 0 0 0 4px rgba(79,214,200,0.2); }}
.step .ln {{ width: 34px; height: 1px; background: {t['border2']}; }}
.msg {{ display: flex; gap: 10px; }}
.msg .av {{ width: 28px; height: 28px; border-radius: 8px; flex: none; display: grid; place-items: center; font-weight: 800; font-size: 10px; }}
"""

ICON = dict(
    search='<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"></circle><path d="M20 20l-3.5-3.5"></path></svg>',
    moon='<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 13A9 9 0 1 1 11 3a7 7 0 0 0 10 10z"></path></svg>',
    sun='<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"></path></svg>',
    bell='<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.7 21a2 2 0 0 1-3.4 0"></path></svg>',
    kanban='<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="4" width="5" height="16" rx="1"></rect><rect x="10" y="4" width="5" height="10" rx="1"></rect><rect x="17" y="4" width="4" height="13" rx="1"></rect></svg>',
    list='<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"></path></svg>',
    mark='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0b1512" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 14l6-8 4 6 6-9"></path><path d="M4 20h16"></path></svg>',
    mail='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"></rect><path d="M3 7l9 6 9-6"></path></svg>',
    check='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5 9-10"></path></svg>',
    down='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"></path></svg>',
    refresh='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-2.6-6.4"></path><path d="M21 4v5h-5"></path></svg>',
    plus='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M12 5v14M5 12h14"></path></svg>',
)

def nav(t, active):
    items = ["Pipeline", "Review desk", "Leads", "Reporting"]
    toggle = ICON["sun"] if t["scheme"] == "dark" else ICON["moon"]
    return f"""
<div class="nav">
  <div class="brand"><div class="mark">{ICON['mark']}</div><span>Growth Desk</span></div>
  {''.join(f'<div class="navitem{" on" if i == active else ""}">{i}</div>' for i in items)}
  <div class="navright">
    <div class="icobtn">{ICON['search']}</div>
    <div class="icobtn">{ICON['bell']}</div>
    <div class="icobtn">{toggle}</div>
    <div class="avatar">KK</div>
  </div>
</div>"""

def doc(t, body, extra_css=""):
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
  <style>{css(t)}{extra_css}</style>
</helmet>
{body}
</x-dc>
</body>
</html>
"""

# --------------------------------------------------------------- sample data
# Invented companies. No real prospect data may appear in a tracked file.
CARDS = {
    "Target identified": [
        ("Nordfeld Metallbau GmbH", "Hannover · Panel fences", 0, [("dim", "Not qualified")], False),
        ("Halvers Industrietore KG", "Bremen · Gates", 0, [("dim", "Not qualified")], False),
        ("Tannhäuser Bauelemente", "Erfurt · Balustrades", 0, [("review", "Needs review")], False),
    ],
    "Qualified": [
        ("Weserland Stahlhandel", "Minden · Steel trading", 74, [("wait", "Draft ready")], False),
        ("Kessler &amp; Roth GaLaBau", "Kassel · Landscaping", 61, [("dim", "Below floor")], False),
        ("Brückner Zaunsysteme", "Ulm · Panel fences", 83, [("wait", "Awaiting approval")], True),
    ],
    "Approved": [
        ("Steinhagen Gitterwerk", "Bielefeld · Mesh panels", 79, [("ok", "Approved"), ("dim", "v3")], False),
        ("Ahrens Tor &amp; Zaun", "Oldenburg · Gates", 71, [("ok", "Approved"), ("stop", "Claim open")], False),
    ],
    "Sent": [
        ("Lüttich Metall GmbH", "Aachen · Railings", 77, [("ok", "Sent 2 Sep")], False),
        ("Möllenkamp Bauzaun", "Münster · Site fencing", 68, [("ok", "Sent 1 Sep")], False),
        ("Ravensberg Drahtwerk", "Herford · Wire mesh", 80, [("ok", "Sent 29 Aug")], False),
    ],
    "Replied": [
        ("Hollmann Stahlbau", "Osnabrück · Steel", 85, [("review", "Objection")], False),
        ("Dörpfeld Zäune", "Detmold · Panel fences", 76, [("ok", "Interested")], False),
    ],
}
PROG = {
    "Target identified": [(ACCENT2, 30)],
    "Qualified": [(AMBER, 60), (ACCENT2, 20)],
    "Approved": [(ACCENT, 60), (ROSE, 40)],
    "Sent": [(ACCENT, 100)],
    "Replied": [(ACCENT2, 50), (ACCENT, 50)],
}

def pipeline(t):
    cols = []
    for name, cards in CARDS.items():
        prog = ''.join(f'<div style="width:{w}%;background:{c}"></div>' for c, w in PROG[name])
        cs = []
        for title, sub, score, pills, hot in cards:
            sc = (f'<div class="score"><span>{score}</span><div class="bar"><div style="width:{score}%"></div></div></div>'
                  if score else '<span class="faint" style="font-size:12px">no score</span>')
            ps = ''.join(f'<span class="pill {k}"><i></i>{v}</span>' for k, v in pills)
            cs.append(f"""
      <div class="card{' hot' if hot else ''}">
        <div class="t">{title}</div>
        <div class="muted" style="font-size:12px">{sub}</div>
        <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap">{sc}
          <div style="display:flex;gap:6px;flex-wrap:wrap">{ps}</div></div>
      </div>""")
        cols.append(f"""
    <div class="glass col">
      <div class="colhead"><span class="t">{name}</span><span class="cnt">{len(cards)}</span>
        <span style="margin-left:auto;color:{t['faint']}">{ICON['plus']}</span></div>
      <div class="prog">{prog}</div>{''.join(cs)}
    </div>""")
    body = nav(t, "Pipeline") + f"""
<div class="cp">
  <div><div class="crumb">CRM</div><h1>Pipeline</h1></div>
  <div class="search">{ICON['search']}<span class="chip on">My pipeline</span><span>Search opportunities…</span></div>
  <div class="seg"><div class="on">{ICON['kanban']}</div><div>{ICON['list']}</div></div>
  <div class="btn primary">{ICON['plus']}New</div>
</div>
<div style="display:flex;gap:6px;padding:0 26px 14px">
  <span class="chip on">{ICON['check']}Sendable today <span class="n">3 / 20</span></span>
  <span class="chip">Needs review <span class="n">2</span></span>
  <span class="chip">Unresolved claim <span class="n">1</span></span>
  <span class="chip">Replies <span class="n">2</span></span>
</div>
<div style="display:flex;gap:14px;padding:0 26px;align-items:flex-start;overflow:hidden">{''.join(cols)}</div>
"""
    return doc(t, body)

def review_desk(t):
    rows = [
        ("Brückner Zaunsysteme", "Ulm", "m.brueckner@…", 83, ("ok", "Ready"), ("wait", "Ready"), ("dim", "No"), ("dim", "—"), ("dim", "—"), True),
        ("Ahrens Tor &amp; Zaun", "Oldenburg", "info@…", 71, ("ok", "Ready"), ("ok", "Approved"), ("ok", "Yes"), ("stop", "Claimed"), ("dim", "—"), False),
        ("Hollmann Stahlbau", "Osnabrück", "einkauf@…", 85, ("ok", "Ready"), ("ok", "Sent"), ("ok", "Yes"), ("ok", "Accepted"), ("review", "Objection"), False),
        ("Tannhäuser Bauelemente", "Erfurt", "kontakt@…", 0, ("review", "Uncertain"), ("dim", "Empty"), ("dim", "No"), ("dim", "—"), ("dim", "—"), False),
        ("Weserland Stahlhandel", "Minden", "vertrieb@…", 74, ("ok", "Ready"), ("wait", "Ready"), ("dim", "No"), ("dim", "—"), ("dim", "—"), False),
        ("Kessler &amp; Roth GaLaBau", "Kassel", "buero@…", 61, ("ok", "Ready"), ("dim", "Empty"), ("dim", "No"), ("dim", "—"), ("dim", "—"), False),
        ("Dörpfeld Zäune", "Detmold", "d.doerpfeld@…", 76, ("ok", "Ready"), ("ok", "Sent"), ("ok", "Yes"), ("ok", "Accepted"), ("ok", "Interested"), False),
    ]
    def pill(p): return f'<span class="pill {p[0]}"><i></i>{p[1]}</span>'
    trs = []
    for name, city, mail, score, q, d, a, dl, r, sel in rows:
        sc = (f'<div class="score"><span>{score}</span><div class="bar"><div style="width:{score}%"></div></div></div>'
              if score else '<span class="faint">—</span>')
        trs.append(f"""
      <tr class="{'sel' if sel else ''}">
        <td><div style="font-weight:700">{name}</div><div class="faint" style="font-size:12px">{city}</div></td>
        <td class="mono muted">{mail}</td>
        <td>{sc}</td><td>{pill(q)}</td><td>{pill(d)}</td><td>{pill(a)}</td><td>{pill(dl)}</td><td>{pill(r)}</td>
      </tr>""")
    body = nav(t, "Review desk") + f"""
<div class="cp">
  <div><div class="crumb">CRM</div><h1>Review desk</h1></div>
  <div class="search">{ICON['search']}<span>Search name, company, email…</span></div>
  <div class="seg"><div>{ICON['kanban']}</div><div class="on">{ICON['list']}</div></div>
</div>
<div style="display:flex;gap:6px;padding:0 26px 14px;flex-wrap:wrap">
  <span class="chip on">Needs review <span class="n">1</span></span>
  <span class="chip on">Unresolved send claim <span class="n">1</span></span>
  <span class="chip on">Draft awaiting approval <span class="n">2</span></span>
  <span class="chip">Approved, not sent</span>
  <span class="chip">Sent, no reply</span>
  <span class="chip">Reply received <span class="n">2</span></span>
  <span class="chip">Below the draft floor <span class="n">1</span></span>
  <span class="chip" style="margin-left:auto">Group by {ICON['down']}</span>
</div>
<div class="glass" style="margin:0 26px;overflow:hidden">
  <div style="display:flex;align-items:center;gap:10px;padding:12px 14px" class="hair">
    <span class="muted" style="font-weight:600">7 opportunities · 4 waiting on you</span>
    <span class="faint">·</span><span class="faint">Sent today 3 of 20</span>
    <div style="margin-left:auto;display:flex;gap:8px">
      <span class="btn sm">{ICON['refresh']}Fetch mail</span>
      <span class="btn sm primary">{ICON['check']}Approve outreach</span>
    </div>
  </div>
  <table>
    <thead><tr><th>Opportunity</th><th>Email</th><th>Fit</th><th>Qualification</th><th>Draft</th><th>Approved</th><th>Delivery</th><th>Reply</th></tr></thead>
    <tbody>{''.join(trs)}</tbody>
  </table>
</div>
<div style="padding:14px 26px" class="faint">Opens on the three things only a human can settle: records the automation refused to decide, sends whose outcome is unknown, and drafts waiting for approval.</div>
"""
    return doc(t, body)

def lead_form(t):
    def f(label, value, mono=False, dim=False):
        cls = "v" + (" mono" if mono else "") + (" faint" if dim else "")
        return f'<div class="field"><span class="label">{label}</span><span class="{cls}">{value}</span></div>'
    steps = [("Target identified", "done"), ("Qualified", "done"), ("Approved", "on"), ("Sent", ""), ("Replied", "")]
    stepper = '<span class="ln"></span>'.join(f'<span class="step {s}"><i></i>{n}</span>' for n, s in steps)
    body = nav(t, "Pipeline") + f"""
<div class="cp" style="padding-bottom:12px">
  <div><div class="crumb">Pipeline / Qualified</div><h1>Brückner Zaunsysteme</h1></div>
  <div style="display:flex;gap:8px;margin-left:auto">
    <span class="btn">{ICON['refresh']}Fetch mail</span>
    <span class="btn danger">Revoke approval</span>
    <span class="btn primary">{ICON['check']}Approve outreach</span>
  </div>
</div>
<div style="display:grid;grid-template-columns:minmax(0,1fr) 380px;gap:14px;padding:0 26px">
  <div style="display:flex;flex-direction:column;gap:14px">
    <div class="glass" style="padding:16px 18px;display:flex;align-items:center;gap:22px">
      <div class="ring" style="--p:83%"><div>83</div></div>
      <div style="display:flex;flex-direction:column;gap:6px;flex:1">
        <div style="display:flex;gap:8px;align-items:center">
          <span class="pill wait"><i></i>Draft v3 ready</span>
          <span class="pill dim"><i></i>Not yet approved</span>
          <span class="pill dim">Basis · trade fair</span>
        </div>
        <div style="display:flex;align-items:center;gap:6px">{stepper}</div>
      </div>
      <div style="text-align:right;display:flex;flex-direction:column;gap:2px">
        <span class="label">Send key</span><span class="mono muted">ggd-1146-v3-9f2c</span>
        <span class="faint" style="font-size:12px">no claim open</span>
      </div>
    </div>
    <div class="glass" style="padding:0 18px 18px">
      <div style="display:flex;gap:22px" class="hair">
        <span class="tab">Internal notes</span><span class="tab">Extra info</span><span class="tab on">GGD intelligence</span>
      </div>
      <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-top:16px">
        <div class="card" style="gap:12px">
          <span class="label">Qualification</span>
          {f("Industry", "Panel fences · manufacturing")}
          {f("Source", "brueckner-zaun.example", True)}
          {f("Product focus", "Double-wire mesh panels, gates")}
          {f("Fit summary", "Mid-size manufacturer selling through regional dealers; no export desk listed. Fit rests on the DACH-to-EU expansion angle.")}
          {f("Buyer roles", "Geschäftsführung, Vertriebsleitung")}
        </div>
        <div class="card" style="gap:12px">
          <span class="label">Reviewed outreach draft</span>
          <div class="input">Ihr Zaunprogramm für Händler in Benelux</div>
          <div class="input area muted" style="min-height:118px">Guten Tag Herr Brückner,<br><br>auf der Messe in Nürnberg fiel uns Ihr Doppelstabmatten-Programm auf. Wir vermitteln deutsche Hersteller an geprüfte Händler in Benelux und Skandinavien …</div>
          <div style="display:flex;gap:8px;align-items:center">
            <span class="pill ok"><i></i>Ready</span><span class="pill dim">v3 · de</span>
            <span class="faint" style="margin-left:auto;font-size:12px">Approved recipient: —</span>
          </div>
        </div>
        <div class="card" style="gap:12px">
          <span class="label">Outreach control</span>
          <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px">
            {f("Contact basis", "Trade fair, no opt-in")}
            {f("Do not contact", "No")}
            {f("Approved by", "—", dim=True)}
            {f("Approved at", "—", dim=True)}
          </div>
          {f("Basis note", "Business card collected at the stand, 2 Sep. Asked to receive dealer information.")}
        </div>
        <div class="card" style="gap:12px">
          <span class="label">Reply analysis</span>
          <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px">
            {f("Category", "—", dim=True)}
            {f("AI confidence", "—", dim=True)}
            {f("Last analyzed", "—", dim=True)}
            {f("Delivery status", "Not sent")}
          </div>
          {f("Suggested next action", "—", dim=True)}
        </div>
      </div>
    </div>
  </div>
  <div class="glass" style="padding:16px;display:flex;flex-direction:column;gap:14px">
    <div style="display:flex;align-items:center;gap:8px">
      <span style="font-weight:800">Chatter</span>
      <span class="chip" style="margin-left:auto">{ICON['mail']}Send message</span>
      <span class="chip">Log note</span>
    </div>
    <div class="msg"><div class="av" style="background:rgba(160,140,255,0.2);color:{ACCENT2}">AI</div>
      <div><div style="font-weight:700">GGD-02 <span class="faint" style="font-weight:500">· today 09:14</span></div>
      <div class="muted">Draft v3 written. Angle: Nürnberg trade fair, dealer expansion.</div></div></div>
    <div class="msg"><div class="av" style="background:rgba(79,214,200,0.18);color:{ACCENT}">KK</div>
      <div><div style="font-weight:700">Kaan <span class="faint" style="font-weight:500">· yesterday</span></div>
      <div class="muted">Business card from the stand. Send after the fair week.</div></div></div>
    <div class="msg"><div class="av" style="background:rgba(240,180,92,0.18);color:{AMBER}">{ICON['bell']}</div>
      <div><div style="font-weight:700">Automation <span class="faint" style="font-weight:500">· 2 Sep</span></div>
      <div class="muted">Qualified with fit 83 by GGD-01.</div></div></div>
    <div class="hair"></div>
    <span class="label">Activities</span>
    <div class="card" style="gap:4px"><div style="font-weight:700">Follow up if no reply</div><div class="faint" style="font-size:12px">Due in 6 days · Kaan</div></div>
  </div>
</div>
"""
    return doc(t, body)

# --------------------------------------------------------------- alternates
def direction(name, blurb, tone, bg, g1, g2, glass, border, text, muted, accent, accent2, dark=True):
    """A low-fi 720x480 palette and mood sketch: one column, two cards, chips."""
    fg_on_accent = "#0b1512" if dark else "#ffffff"
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@500;700;800&display=swap');
    * {{ box-sizing: border-box; }}
    body {{ margin:0; width:720px; height:480px; overflow:hidden; font-family: Manrope, "Segoe UI", Arial, sans-serif; color:{text}; background:{bg};
      background-image: radial-gradient(520px 360px at -5% -10%, {g1}, transparent 60%), radial-gradient(560px 400px at 105% 110%, {g2}, transparent 62%); font-size:13px; }}
    a {{ color:{accent}; }} a:hover {{ color:{accent2}; }}
    .g {{ background:{glass}; border:1px solid {border}; border-radius:16px; backdrop-filter: blur(20px) saturate(150%); -webkit-backdrop-filter: blur(20px) saturate(150%); }}
    .pill {{ display:inline-flex; align-items:center; height:22px; padding:0 9px; border-radius:999px; font-size:11px; font-weight:700; }}
    .sw {{ width:34px; height:34px; border-radius:10px; border:1px solid {border}; }}
  </style>
</helmet>
<div style="padding:22px 24px;display:flex;flex-direction:column;gap:14px;height:480px">
  <div style="display:flex;align-items:flex-start;gap:16px">
    <div style="flex:1"><div style="font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:{muted}">Direction</div>
      <div style="font-size:22px;font-weight:800;letter-spacing:-.02em">{name}</div>
      <div style="color:{muted};margin-top:4px;max-width:420px">{blurb}</div></div>
    <div style="display:flex;gap:6px">
      <div class="sw" style="background:{bg}"></div><div class="sw" style="background:{glass}"></div>
      <div class="sw" style="background:{accent}"></div><div class="sw" style="background:{accent2}"></div>
    </div>
  </div>
  <div class="g" style="height:46px;display:flex;align-items:center;padding:0 14px;gap:14px;font-weight:700">
    <span style="width:22px;height:22px;border-radius:7px;background:linear-gradient(135deg,{accent},{accent2})"></span>
    <span>Pipeline</span><span style="color:{muted}">Review desk</span><span style="color:{muted}">Leads</span>
    <span style="margin-left:auto;height:30px;padding:0 12px;border-radius:9px;background:{accent};color:{fg_on_accent};display:inline-flex;align-items:center">Approve outreach</span>
  </div>
  <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;flex:1">
    <div class="g" style="padding:12px;display:flex;flex-direction:column;gap:10px">
      <div style="font-weight:800;display:flex;justify-content:space-between"><span>Qualified</span><span style="color:{muted}">3</span></div>
      <div class="g" style="padding:12px;border-radius:12px;border-color:{accent}66"><div style="font-weight:700">Brückner Zaunsysteme</div><div style="color:{muted};font-size:12px">Ulm · Panel fences</div>
        <div style="margin-top:8px;display:flex;gap:6px"><span class="pill" style="color:{accent};background:{accent}22">Awaiting approval</span></div></div>
      <div class="g" style="padding:12px;border-radius:12px"><div style="font-weight:700">Weserland Stahlhandel</div><div style="color:{muted};font-size:12px">Minden · Steel</div></div>
    </div>
    <div class="g" style="padding:12px;display:flex;flex-direction:column;gap:10px">
      <div style="font-weight:800;display:flex;justify-content:space-between"><span>Approved</span><span style="color:{muted}">2</span></div>
      <div class="g" style="padding:12px;border-radius:12px"><div style="font-weight:700">Steinhagen Gitterwerk</div><div style="color:{muted};font-size:12px">Bielefeld · Mesh</div>
        <div style="margin-top:8px;display:flex;gap:6px"><span class="pill" style="color:{accent2};background:{accent2}22">Approved</span></div></div>
    </div>
    <div class="g" style="padding:14px;display:flex;flex-direction:column;gap:8px">
      <div style="font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:{muted}">Tone</div>
      <div style="font-weight:700">{tone}</div>
      <div style="color:{muted};font-size:12px;line-height:1.5">Same glass, same layout as the main direction. Only the temperature and the accent pair change.</div>
    </div>
  </div>
</div>
</x-dc>
</body>
</html>
"""

def main():
    (OUT / "Main.dc.html").write_text(pipeline(DARK))
    (OUT / "ReviewDesk.dc.html").write_text(review_desk(DARK))
    (OUT / "LeadForm.dc.html").write_text(lead_form(DARK))
    (OUT / "PipelineLight.dc.html").write_text(pipeline(LIGHT))
    (OUT / "DirectionEmber.dc.html").write_text(direction(
        "Ember", "Warm charcoal with amber and coral. Friendlier and less 'tech', at the cost of status colours: amber is already the waiting state, so warnings need a second look.",
        "Warm, hospitable, sales-floor",
        "#15110f", "rgba(240,150,80,0.18)", "rgba(230,90,110,0.14)", "rgba(255,255,255,0.06)", "rgba(255,255,255,0.11)",
        "#f2ebe4", "#a89c92", "#f0a35c", "#f27b8e"))
    (OUT / "DirectionGraphite.dc.html").write_text(direction(
        "Graphite", "Near-monochrome glass with one electric lime accent. The most distinctive and the calmest at density, but a single accent carries every state, so pills lean on labels more than colour.",
        "Austere, precise, instrument-like",
        "#101113", "rgba(255,255,255,0.07)", "rgba(200,255,80,0.10)", "rgba(255,255,255,0.05)", "rgba(255,255,255,0.10)",
        "#ecedef", "#8d919a", "#c6f542", "#9aa0aa"))
    canvas = {
        "pages": [{"id": "page-1", "name": "Aurora"}, {"id": "page-2", "name": "Tone alternates"}],
        "artboards": [
            {"file": "Main.dc.html", "title": "Pipeline · dark", "x": 0, "y": 0, "w": 1440, "h": 900},
            {"file": "ReviewDesk.dc.html", "title": "Review desk · dark", "x": 1540, "y": 0, "w": 1440, "h": 900},
            {"file": "LeadForm.dc.html", "title": "Opportunity · dark", "x": 0, "y": 1040, "w": 1440, "h": 900},
            {"file": "PipelineLight.dc.html", "title": "Pipeline · light", "x": 1540, "y": 1040, "w": 1440, "h": 900},
            {"file": "DirectionEmber.dc.html", "title": "Ember", "x": 0, "y": 0, "w": 720, "h": 480, "page": "page-2"},
            {"file": "DirectionGraphite.dc.html", "title": "Graphite", "x": 820, "y": 0, "w": 720, "h": 480, "page": "page-2"},
        ],
        "annotations": [
            {"id": "aurora-note", "x": 0, "y": -150, "w": 560, "page": "page-1",
             "text": "Aurora: cool charcoal, teal + violet accents, glass over a faint two-corner glow.\nDark is the primary theme; light keeps the same structure.\nStatus colours: teal = ok, amber = waiting, violet = needs a human, rose = blocked.\nCompany names are invented sample data."},
            {"id": "alt-note", "x": 0, "y": -110, "w": 480, "page": "page-2",
             "text": "Two tone alternates on the same glass system. Pick one, or keep Aurora."},
        ],
        "launch": {"view": "canvas", "page": "page-1"},
    }
    (OUT / "canvas.json").write_text(json.dumps(canvas, indent=2, ensure_ascii=False))
    print("generated")

if __name__ == "__main__":
    main()
