#!/usr/bin/env python3
"""Four non-glass directions for the GGD pipeline, same content as Aurora."""
import json, pathlib
from gen import CARDS, ICON, OUT

HEAD = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
  <style>{css}</style>
</helmet>
{body}
</x-dc>
</body>
</html>
"""

def page(css, body):
    return HEAD.format(css=css, body=body)

STAGES = list(CARDS.keys())

# ------------------------------------------------------------------ Ledger
def ledger():
    ink, muted, rule, verm = "#1a1714", "#6e675d", "#d9d2c5", "#d2452b"
    css = f"""
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Instrument+Sans:wght@400;500;600&display=swap');
* {{ box-sizing: border-box; }}
body {{ margin:0; width:1440px; height:900px; overflow:hidden; background:#f6f2ea; color:{ink};
  font-family: "Instrument Sans", "Helvetica Neue", Arial, sans-serif; font-size:13px; line-height:1.45; -webkit-font-smoothing:antialiased; }}
a {{ color:{verm}; }} a:hover {{ color:{ink}; }}
.serif {{ font-family: "Instrument Serif", Georgia, "Times New Roman", serif; }}
.caps {{ font-size:11px; letter-spacing:.14em; text-transform:uppercase; font-weight:600; color:{muted}; }}
.mast {{ display:flex; align-items:baseline; gap:28px; padding:26px 40px 14px; border-bottom:1px solid {ink}; margin:0 40px; position:relative; }}
.mast::after {{ content:""; position:absolute; left:0; right:0; bottom:-4px; border-bottom:1px solid {ink}; }}
.mast .brand {{ font-size:13px; letter-spacing:.22em; text-transform:uppercase; font-weight:600; }}
.mast .sec {{ color:{muted}; font-weight:500; }}
.mast .sec.on {{ color:{ink}; text-decoration:underline; text-underline-offset:6px; text-decoration-color:{verm}; text-decoration-thickness:2px; }}
.mast .right {{ margin-left:auto; display:flex; gap:22px; color:{muted}; font-weight:500; }}
.head {{ display:flex; align-items:flex-end; gap:26px; padding:30px 40px 18px; }}
.head h1 {{ margin:0; font-size:56px; font-weight:400; line-height:.95; letter-spacing:-.01em; }}
.head h1 em {{ color:{verm}; }}
.head .sum {{ color:{muted}; max-width:360px; font-size:14px; }}
.head .acts {{ margin-left:auto; display:flex; gap:10px; }}
.btn {{ height:38px; padding:0 16px; display:inline-flex; align-items:center; gap:8px; border:1px solid {ink}; font-weight:600; border-radius:2px; }}
.btn.primary {{ background:{ink}; color:#f6f2ea; }}
.tally {{ display:flex; gap:0; padding:0 40px 22px; }}
.tally > div {{ padding:8px 18px 8px 0; margin-right:18px; border-right:1px solid {rule}; display:flex; flex-direction:column; gap:2px; }}
.tally > div:last-child {{ border-right:0; }}
.tally .n {{ font-size:26px; line-height:1; }}
.board {{ display:grid; grid-template-columns:repeat(5, minmax(0,1fr)); gap:34px; padding:0 40px; }}
.colh {{ display:flex; align-items:baseline; gap:8px; padding-bottom:8px; border-bottom:2px solid {ink}; margin-bottom:4px; }}
.colh .cnt {{ margin-left:auto; font-size:18px; }}
.row {{ padding:14px 0 13px; border-bottom:1px solid {rule}; display:flex; flex-direction:column; gap:5px; }}
.row .t {{ font-size:19px; line-height:1.15; }}
.row.hot .t {{ text-decoration:underline; text-decoration-color:{verm}; text-underline-offset:4px; text-decoration-thickness:2px; }}
.row .m {{ color:{muted}; font-size:12px; }}
.row .s {{ display:flex; align-items:center; gap:10px; margin-top:3px; font-size:12px; font-weight:500; }}
.st {{ display:inline-flex; align-items:center; gap:6px; }}
.st::before {{ content:""; width:7px; height:7px; background:currentColor; }}
.st.ok {{ color:{ink}; }} .st.wait {{ color:{verm}; }} .st.review {{ color:{verm}; }} .st.stop {{ color:{verm}; font-weight:600; }} .st.dim {{ color:{muted}; }}
.fit {{ margin-left:auto; font-size:16px; display:inline-flex; align-items:baseline; gap:6px; }}
.fit .bar {{ width:40px; height:2px; background:{rule}; position:relative; top:-4px; }}
.fit .bar > div {{ height:100%; background:{ink}; }}
"""
    cols = []
    for name in STAGES:
        rows = []
        for title, sub, score, pills, hot in CARDS[name]:
            st = ''.join(f'<span class="st {k}">{v}</span>' for k, v in pills)
            fit = (f'<span class="fit serif">{score}<span class="bar"><div style="width:{score}%"></div></span></span>' if score else '')
            rows.append(f'<div class="row{" hot" if hot else ""}"><div class="t serif">{title}</div><div class="m">{sub}</div><div class="s">{st}{fit}</div></div>')
        cols.append(f'<div><div class="colh"><span class="caps" style="color:{ink}">{name}</span><span class="cnt serif">{len(CARDS[name])}</span></div>{"".join(rows)}</div>')
    body = f"""
<div class="mast"><span class="brand">Growth Desk</span><span class="sec on">Pipeline</span><span class="sec">Review desk</span><span class="sec">Leads</span><span class="sec">Reporting</span>
  <div class="right"><span>Search</span><span>Dark</span><span style="color:{ink}">K. Kadıoğlu</span></div></div>
<div class="head"><h1 class="serif">Pipeline, <em>Thursday</em></h1><div class="sum">Four opportunities wait on you: two drafts, one unresolved claim, one reply the model would not classify.</div>
  <div class="acts"><span class="btn">List view</span><span class="btn primary">{ICON['plus']}New opportunity</span></div></div>
<div class="tally">
  <div><span class="caps">Sendable today</span><span class="n serif">3 <span style="color:{muted};font-size:16px">of 20</span></span></div>
  <div><span class="caps">Needs review</span><span class="n serif">2</span></div>
  <div><span class="caps">Unresolved claim</span><span class="n serif" style="color:{verm}">1</span></div>
  <div><span class="caps">Replies</span><span class="n serif">2</span></div>
</div>
<div class="board">{''.join(cols)}</div>
"""
    return page(css, body)

# ------------------------------------------------------------------- Bento
def bento():
    ink, muted = "#221d18", "#7a7068"
    tints = {"Target identified": ("#ebe6fa", "#5b46c9"), "Qualified": ("#fbefd0", "#9a6a05"), "Approved": ("#e3efe2", "#2f7a4a"), "Sent": ("#e2eef8", "#2b6aa8"), "Replied": ("#fbe6dc", "#b8532e")}
    css = f"""
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap');
* {{ box-sizing: border-box; }}
body {{ margin:0; width:1440px; height:900px; overflow:hidden; background:#fbf7f2; color:{ink};
  font-family:"Plus Jakarta Sans", "Segoe UI", "Helvetica Neue", Arial, sans-serif; font-size:13px; line-height:1.45; -webkit-font-smoothing:antialiased; }}
a {{ color:#2b6aa8; }} a:hover {{ color:{ink}; }}
.nav {{ margin:16px 24px 0; height:58px; background:#fff; border-radius:999px; box-shadow:0 1px 2px rgba(60,40,20,.05), 0 10px 30px rgba(60,40,20,.07); display:flex; align-items:center; padding:0 10px 0 22px; gap:4px; }}
.nav .brand {{ font-weight:800; font-size:15px; margin-right:16px; display:flex; align-items:center; gap:10px; }}
.nav .brand i {{ width:28px; height:28px; border-radius:50%; background:{ink}; display:block; }}
.nav .it {{ padding:9px 14px; border-radius:999px; color:{muted}; font-weight:600; }}
.nav .it.on {{ background:{ink}; color:#fff; }}
.nav .r {{ margin-left:auto; display:flex; align-items:center; gap:4px; }}
.ico {{ width:40px; height:40px; border-radius:50%; display:grid; place-items:center; color:{muted}; }}
.ico:hover {{ background:#f3ede6; color:{ink}; }}
.av {{ width:38px; height:38px; border-radius:50%; background:linear-gradient(135deg,#fbd38d,#f6a5a5); display:grid; place-items:center; font-weight:800; font-size:12px; margin-left:6px; }}
.head {{ display:flex; align-items:center; gap:16px; padding:26px 30px 16px; }}
.head h1 {{ margin:0; font-size:30px; font-weight:800; letter-spacing:-.03em; }}
.head .sub {{ color:{muted}; font-weight:600; }}
.search {{ margin-left:auto; width:360px; height:46px; border-radius:999px; background:#fff; box-shadow:inset 0 0 0 1px #ece5dc; display:flex; align-items:center; gap:10px; padding:0 18px; color:{muted}; font-weight:500; }}
.btn {{ height:46px; padding:0 20px; border-radius:999px; display:inline-flex; align-items:center; gap:8px; font-weight:700; background:#fff; box-shadow:inset 0 0 0 1px #ece5dc; }}
.btn.primary {{ background:{ink}; color:#fff; box-shadow:none; }}
.stats {{ display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); gap:14px; padding:0 30px 16px; }}
.stat {{ background:#fff; border-radius:20px; padding:14px 18px; display:flex; align-items:center; gap:14px; box-shadow:0 1px 2px rgba(60,40,20,.04), 0 6px 20px rgba(60,40,20,.05); }}
.stat .n {{ font-size:26px; font-weight:800; letter-spacing:-.03em; }}
.stat .l {{ color:{muted}; font-weight:600; font-size:12px; }}
.stat .ring {{ width:42px; height:42px; border-radius:50%; display:grid; place-items:center; font-weight:800; font-size:12px; }}
.board {{ display:flex; gap:14px; padding:0 30px; align-items:flex-start; }}
.col {{ flex:1; border-radius:24px; padding:14px; display:flex; flex-direction:column; gap:10px; }}
.colh {{ display:flex; align-items:center; gap:8px; padding:2px 6px 6px; font-weight:800; font-size:14px; }}
.colh .cnt {{ width:24px; height:24px; border-radius:50%; background:#fff; display:grid; place-items:center; font-size:11px; }}
.card {{ background:#fff; border-radius:16px; padding:14px 15px; display:flex; flex-direction:column; gap:8px; box-shadow:0 1px 2px rgba(60,40,20,.05); }}
.card.hot {{ box-shadow:0 0 0 2px {ink}, 0 10px 24px rgba(60,40,20,.10); }}
.card .t {{ font-weight:700; font-size:14px; letter-spacing:-.01em; }}
.card .m {{ color:{muted}; font-size:12px; font-weight:500; }}
.card .s {{ display:flex; align-items:center; gap:6px; flex-wrap:wrap; }}
.pill {{ height:24px; padding:0 10px; border-radius:999px; display:inline-flex; align-items:center; font-weight:700; font-size:11px; }}
.pill.ok {{ background:#e3efe2; color:#2f7a4a; }} .pill.wait {{ background:#fbefd0; color:#9a6a05; }} .pill.review {{ background:#ebe6fa; color:#5b46c9; }} .pill.stop {{ background:#fde0e0; color:#c0392b; }} .pill.dim {{ background:#f3ede6; color:{muted}; }}
.fit {{ margin-left:auto; width:30px; height:30px; border-radius:50%; display:grid; place-items:center; font-weight:800; font-size:11px; }}
.fit > div {{ width:24px; height:24px; border-radius:50%; background:#fff; display:grid; place-items:center; }}
"""
    cols = []
    for name in STAGES:
        bg, fg = tints[name]
        cards = []
        for title, sub, score, pills, hot in CARDS[name]:
            ps = ''.join(f'<span class="pill {k}">{v}</span>' for k, v in pills)
            fit = (f'<span class="fit" style="background:conic-gradient({fg} 0 {score}%, #eee6dc {score}% 100%)"><div>{score}</div></span>' if score else '')
            cards.append(f'<div class="card{" hot" if hot else ""}"><div class="t">{title}</div><div class="m">{sub}</div><div class="s">{ps}{fit}</div></div>')
        cols.append(f'<div class="col" style="background:{bg}"><div class="colh" style="color:{fg}">{name}<span class="cnt">{len(CARDS[name])}</span></div>{"".join(cards)}</div>')
    body = f"""
<div class="nav"><span class="brand"><i></i>Growth Desk</span><span class="it on">Pipeline</span><span class="it">Review desk</span><span class="it">Leads</span><span class="it">Reporting</span>
  <div class="r"><span class="ico">{ICON['search']}</span><span class="ico">{ICON['bell']}</span><span class="ico">{ICON['moon']}</span><span class="av">KK</span></div></div>
<div class="head"><div><h1>Good afternoon, Kaan</h1><div class="sub">4 things wait on you today</div></div>
  <div class="search">{ICON['search']}Search opportunities…</div><span class="btn">{ICON['list']}List</span><span class="btn primary">{ICON['plus']}New</span></div>
<div class="stats">
  <div class="stat"><span class="ring" style="background:conic-gradient({ink} 0 15%, #f3ede6 15% 100%)"><span style="background:#fff;width:32px;height:32px;border-radius:50%;display:grid;place-items:center">3</span></span><div><div class="n">3 <span style="font-size:14px;color:{muted}">/ 20</span></div><div class="l">Sendable today</div></div></div>
  <div class="stat"><div class="n" style="color:#5b46c9">2</div><div class="l">Needs review</div></div>
  <div class="stat"><div class="n" style="color:#c0392b">1</div><div class="l">Unresolved send claim</div></div>
  <div class="stat"><div class="n" style="color:#b8532e">2</div><div class="l">Replies to read</div></div>
</div>
<div class="board">{''.join(cols)}</div>
"""
    return page(css, body)

# -------------------------------------------------------------------- Noir
def noir():
    ivory, muted, gold, line = "#ece7dc", "#8b8578", "#c9a962", "#232326"
    css = f"""
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;1,500&family=Outfit:wght@300;400;500;600&display=swap');
* {{ box-sizing: border-box; }}
body {{ margin:0; width:1440px; height:900px; overflow:hidden; background:#0a0a0b; color:{ivory};
  background-image: linear-gradient(180deg, rgba(201,169,98,.06), transparent 30%), radial-gradient(800px 500px at 50% 120%, rgba(201,169,98,.08), transparent 60%);
  font-family: Outfit, "Segoe UI", "Helvetica Neue", Arial, sans-serif; font-size:13px; line-height:1.5; font-weight:300; -webkit-font-smoothing:antialiased; }}
a {{ color:{gold}; }} a:hover {{ color:{ivory}; }}
.serif {{ font-family:"Cormorant Garamond", Georgia, "Times New Roman", serif; }}
.nav {{ height:64px; margin:0 48px; border-bottom:1px solid {line}; display:flex; align-items:center; gap:34px; }}
.nav .brand {{ font-size:22px; font-weight:500; letter-spacing:.04em; margin-right:20px; display:flex; align-items:center; gap:12px; }}
.nav .brand i {{ width:8px; height:8px; background:{gold}; transform:rotate(45deg); display:block; }}
.nav .it {{ color:{muted}; letter-spacing:.12em; text-transform:uppercase; font-size:11px; font-weight:500; }}
.nav .it.on {{ color:{gold}; }}
.nav .r {{ margin-left:auto; display:flex; align-items:center; gap:22px; color:{muted}; }}
.av {{ width:32px; height:32px; border-radius:50%; border:1px solid {gold}; color:{gold}; display:grid; place-items:center; font-size:11px; letter-spacing:.08em; }}
.head {{ display:flex; align-items:flex-end; gap:30px; padding:40px 48px 24px; }}
.head h1 {{ margin:0; font-size:52px; font-weight:500; line-height:1; letter-spacing:.01em; }}
.head .sub {{ color:{muted}; font-size:14px; max-width:380px; }}
.head .acts {{ margin-left:auto; display:flex; gap:12px; }}
.btn {{ height:42px; padding:0 22px; display:inline-flex; align-items:center; gap:10px; border:1px solid {line}; color:{ivory}; letter-spacing:.08em; text-transform:uppercase; font-size:11px; font-weight:500; }}
.btn.primary {{ background:{gold}; color:#0a0a0b; border-color:{gold}; }}
.tally {{ display:flex; gap:40px; padding:0 48px 26px; }}
.tally > div {{ display:flex; align-items:baseline; gap:10px; }}
.tally .n {{ font-size:34px; line-height:1; }}
.tally .l {{ color:{muted}; letter-spacing:.12em; text-transform:uppercase; font-size:10px; }}
.board {{ display:grid; grid-template-columns:repeat(5, minmax(0,1fr)); gap:18px; padding:0 48px; }}
.colh {{ display:flex; align-items:baseline; gap:10px; padding:0 4px 12px; border-bottom:1px solid {line}; margin-bottom:12px; }}
.colh .t {{ color:{gold}; letter-spacing:.14em; text-transform:uppercase; font-size:11px; font-weight:500; }}
.colh .cnt {{ margin-left:auto; color:{muted}; font-size:16px; }}
.card {{ background:#121214; border:1px solid {line}; padding:16px 16px 14px; display:flex; flex-direction:column; gap:6px; margin-bottom:10px; }}
.card.hot {{ border-color:{gold}; }}
.card .t {{ font-size:20px; line-height:1.1; font-weight:500; }}
.card .m {{ color:{muted}; font-size:12px; }}
.card .s {{ display:flex; align-items:center; gap:8px; margin-top:6px; flex-wrap:wrap; }}
.tag {{ font-size:10px; letter-spacing:.1em; text-transform:uppercase; padding:4px 8px; border:1px solid {line}; color:{muted}; }}
.tag.ok {{ color:{ivory}; border-color:#3a3a3e; }} .tag.wait {{ color:{gold}; border-color:rgba(201,169,98,.5); }} .tag.review {{ color:{ivory}; border-color:{gold}; }} .tag.stop {{ color:#e08a8a; border-color:rgba(224,138,138,.5); }}
.fit {{ margin-left:auto; font-size:20px; color:{gold}; }}
"""
    cols = []
    for name in STAGES:
        cards = []
        for title, sub, score, pills, hot in CARDS[name]:
            tg = ''.join(f'<span class="tag {k}">{v}</span>' for k, v in pills)
            fit = f'<span class="fit serif">{score}</span>' if score else ''
            cards.append(f'<div class="card{" hot" if hot else ""}"><div class="t serif">{title}</div><div class="m">{sub}</div><div class="s">{tg}{fit}</div></div>')
        cols.append(f'<div><div class="colh"><span class="t">{name}</span><span class="cnt serif">{len(CARDS[name])}</span></div>{"".join(cards)}</div>')
    body = f"""
<div class="nav"><span class="brand serif"><i></i>Growth Desk</span><span class="it on">Pipeline</span><span class="it">Review desk</span><span class="it">Leads</span><span class="it">Reporting</span>
  <div class="r">{ICON['search']}{ICON['bell']}{ICON['moon']}<span class="av">KK</span></div></div>
<div class="head"><h1 class="serif">Pipeline</h1><div class="sub">Thirteen opportunities in motion. Four wait on your judgment.</div>
  <div class="acts"><span class="btn">List</span><span class="btn primary">{ICON['plus']}New</span></div></div>
<div class="tally">
  <div><span class="n serif">3<span style="color:{muted};font-size:18px"> / 20</span></span><span class="l">Sendable today</span></div>
  <div><span class="n serif">2</span><span class="l">Needs review</span></div>
  <div><span class="n serif" style="color:#e08a8a">1</span><span class="l">Unresolved claim</span></div>
  <div><span class="n serif">2</span><span class="l">Replies</span></div>
</div>
<div class="board">{''.join(cols)}</div>
"""
    return page(css, body)

# ---------------------------------------------------------------- Terminal
def terminal():
    fg, muted, line, green, amber, red, violet = "#d8dee0", "#7d8a8e", "#23292c", "#5ef0a3", "#ffb454", "#ff6b6b", "#b9a6ff"
    css = f"""
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Space+Grotesk:wght@500;700&display=swap');
* {{ box-sizing: border-box; }}
body {{ margin:0; width:1440px; height:900px; overflow:hidden; background:#0e1012; color:{fg};
  background-image: linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px); background-size:28px 28px;
  font-family:"JetBrains Mono", "SF Mono", Menlo, Consolas, monospace; font-size:12.5px; line-height:1.5; -webkit-font-smoothing:antialiased; }}
a {{ color:{green}; }} a:hover {{ color:{fg}; }}
.grot {{ font-family:"Space Grotesk", "Segoe UI", Arial, sans-serif; }}
.top {{ height:44px; border-bottom:1px solid {line}; background:#0e1012; display:flex; align-items:center; padding:0 22px; gap:26px; }}
.top .brand {{ font-weight:700; font-size:14px; letter-spacing:.02em; display:flex; align-items:center; gap:10px; }}
.top .brand i {{ width:10px; height:10px; background:{green}; display:block; box-shadow:0 0 12px {green}; }}
.top .path {{ color:{muted}; }} .top .path b {{ color:{fg}; font-weight:500; }}
.top .r {{ margin-left:auto; display:flex; gap:22px; color:{muted}; }}
.top .r .k {{ color:{fg}; border:1px solid {line}; padding:0 6px; border-radius:3px; margin-right:6px; font-size:11px; }}
.head {{ display:flex; align-items:center; gap:22px; padding:26px 22px 14px; }}
.head h1 {{ margin:0; font-size:28px; font-weight:700; letter-spacing:-.02em; }}
.head .cursor {{ display:inline-block; width:12px; height:26px; background:{green}; vertical-align:-3px; margin-left:6px; }}
.head .acts {{ margin-left:auto; display:flex; gap:8px; }}
.btn {{ height:34px; padding:0 14px; display:inline-flex; align-items:center; gap:8px; border:1px solid {line}; border-radius:3px; font-weight:500; background:#121517; }}
.btn.primary {{ border-color:{green}; color:{green}; }}
.tally {{ display:flex; gap:10px; padding:0 22px 16px; }}
.tally > div {{ border:1px solid {line}; background:#121517; padding:8px 12px; border-radius:3px; display:flex; gap:12px; align-items:baseline; }}
.tally .n {{ font-weight:700; font-size:16px; }} .tally .l {{ color:{muted}; text-transform:uppercase; font-size:11px; letter-spacing:.06em; }}
.board {{ display:grid; grid-template-columns:repeat(5, minmax(0,1fr)); gap:10px; padding:0 22px; }}
.col {{ border:1px solid {line}; background:rgba(14,16,18,.85); border-radius:3px; }}
.colh {{ display:flex; align-items:center; padding:8px 12px; border-bottom:1px solid {line}; text-transform:uppercase; letter-spacing:.08em; font-size:11px; color:{muted}; }}
.colh b {{ color:{fg}; font-weight:700; }} .colh .cnt {{ margin-left:auto; color:{fg}; }}
.row {{ padding:11px 12px; border-bottom:1px solid {line}; display:flex; flex-direction:column; gap:3px; }}
.row:last-child {{ border-bottom:0; }}
.row.hot {{ background:rgba(94,240,163,.06); box-shadow:inset 2px 0 0 {green}; }}
.row .t {{ font-weight:700; font-size:13px; }}
.row .m {{ color:{muted}; font-size:11.5px; }}
.row .s {{ display:flex; gap:10px; align-items:center; margin-top:4px; font-size:11px; flex-wrap:wrap; }}
.tag::before {{ content:"["; color:{muted}; }} .tag::after {{ content:"]"; color:{muted}; }}
.tag {{ font-weight:500; text-transform:uppercase; letter-spacing:.04em; }}
.tag.ok {{ color:{green}; }} .tag.wait {{ color:{amber}; }} .tag.review {{ color:{violet}; }} .tag.stop {{ color:{red}; }} .tag.dim {{ color:{muted}; }}
.fit {{ margin-left:auto; color:{fg}; }} .fit span {{ color:{green}; letter-spacing:-1px; }} .fit span.off {{ color:{line}; }}
.foot {{ position:absolute; left:0; right:0; bottom:0; height:34px; border-top:1px solid {line}; background:#0e1012; display:flex; align-items:center; gap:22px; padding:0 22px; color:{muted}; font-size:11.5px; }}
.foot .k {{ color:{fg}; border:1px solid {line}; padding:0 6px; border-radius:3px; margin-right:6px; }}
"""
    def blocks(score):
        n = round(score / 20)
        return '<span>' + '▮' * n + '</span><span class="off">' + '▮' * (5 - n) + '</span>'
    cols = []
    for name in STAGES:
        rows = []
        for title, sub, score, pills, hot in CARDS[name]:
            tg = ''.join(f'<span class="tag {k}">{v}</span>' for k, v in pills)
            fit = f'<span class="fit">{score} {blocks(score)}</span>' if score else ''
            rows.append(f'<div class="row{" hot" if hot else ""}"><div class="t">{title}</div><div class="m">{sub}</div><div class="s">{tg}{fit}</div></div>')
        cols.append(f'<div class="col"><div class="colh"><b>{name}</b><span class="cnt">{len(CARDS[name]):02d}</span></div>{"".join(rows)}</div>')
    body = f"""
<div class="top"><span class="brand grot"><i></i>GROWTH DESK</span><span class="path">growth-desk <b>▸ pipeline</b> ▸ my-pipeline</span>
  <div class="r"><span><span class="k">/</span>search</span><span><span class="k">D</span>dark</span><span style="color:{fg}">kaan@ggd</span></div></div>
<div class="head"><h1 class="grot">Pipeline<span class="cursor"></span></h1><span style="color:{muted}">13 open · sorted by fit · updated 09:14</span>
  <div class="acts"><span class="btn">{ICON['list']}list</span><span class="btn">{ICON['refresh']}fetch mail</span><span class="btn primary">{ICON['plus']}new</span></div></div>
<div class="tally">
  <div><span class="n">03<span style="color:{muted}">/20</span></span><span class="l">sendable today</span></div>
  <div><span class="n" style="color:{violet}">02</span><span class="l">needs review</span></div>
  <div><span class="n" style="color:{red}">01</span><span class="l">unresolved claim</span></div>
  <div><span class="n">02</span><span class="l">replies</span></div>
</div>
<div class="board">{''.join(cols)}</div>
<div class="foot"><span><span class="k">A</span>approve</span><span><span class="k">R</span>revoke</span><span><span class="k">F</span>fetch mail</span><span><span class="k">↵</span>open</span><span style="margin-left:auto">send cap 20/day · gate: approver + not do-not-contact</span></div>
"""
    return page(css, body)

def main():
    (OUT / "DirectionLedger.dc.html").write_text(ledger())
    (OUT / "DirectionBento.dc.html").write_text(bento())
    (OUT / "DirectionNoir.dc.html").write_text(noir())
    (OUT / "DirectionTerminal.dc.html").write_text(terminal())
    c = json.loads((OUT / "canvas.json").read_text())
    c["pages"] = [p for p in c["pages"] if p["id"] != "page-3"] + [{"id": "page-3", "name": "Other directions"}]
    c["artboards"] = [a for a in c["artboards"] if a.get("page") != "page-3"] + [
        {"file": "DirectionLedger.dc.html", "title": "Ledger · editorial paper", "x": 0, "y": 0, "w": 1440, "h": 900, "page": "page-3"},
        {"file": "DirectionBento.dc.html", "title": "Bento · soft tinted", "x": 1540, "y": 0, "w": 1440, "h": 900, "page": "page-3"},
        {"file": "DirectionNoir.dc.html", "title": "Noir · black and gold", "x": 0, "y": 1040, "w": 1440, "h": 900, "page": "page-3"},
        {"file": "DirectionTerminal.dc.html", "title": "Terminal · operator console", "x": 1540, "y": 1040, "w": 1440, "h": 900, "page": "page-3"},
    ]
    c["annotations"] = [a for a in c["annotations"] if a.get("page") != "page-3"] + [
        {"id": "dir-note", "x": 0, "y": -170, "w": 640, "page": "page-3",
         "text": "Four directions that are not glass, each on its own axis. Same content as Aurora so only the look differs.\nLedger: warm paper, serif, ruled lists, one vermilion. Calm and unlike any CRM; dark mode becomes an 'ink' inversion, and status must carry on text more than colour.\nBento: cream ground, tinted columns, pill-shaped everything. Friendly and quick to read; the risk is reading as a consumer app.\nNoir: black, ivory, gold hairlines, serif titles. Premium and quiet; density costs are real and light mode is an afterthought.\nTerminal: monospace operator console, grid, bracketed tags, key hints. Most distinctive and densest; the least forgiving for a non-developer."},
    ]
    c["launch"] = {"view": "canvas", "page": "page-3"}
    (OUT / "canvas.json").write_text(json.dumps(c, indent=2, ensure_ascii=False))
    print("generated 4 directions")

main()
