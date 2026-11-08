"""Look and feel for the ActCheck portal: one stylesheet plus small HTML helpers.

Design follows the editorial style of Project BantAI v2 (dark photo hero, cream "paper" sections,
heavy serif headings, small-caps labels, proportional bars), in ActCheck's navy, gold and red.
Original branding only (a gold scale-and-check mark); no government seals or logos.
"""
from html import escape

import streamlit as st

STATIC = "app/static"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@400;500;600;700;800&family=Source+Serif+4:ital,opsz,wght@0,8..60,600;0,8..60,700;0,8..60,800;0,8..60,900;1,8..60,600&family=IBM+Plex+Mono:wght@500;700&display=swap');
:root{
  --navy:#0B2545; --navy2:#13315C; --ink-dark:#0A1628; --gold:#D4A72C; --gold-soft:#F7EDCC; --red:#B8322A; --red-soft:#F6E1DE;
  --paper:#F4F1EA; --soft:#FAF8F3; --card:#FFFFFF; --ink:#121826; --ink2:#3A3F4B; --mute:#6B6F7A; --line:#D8D3C7; --line2:#E6E1D6;
  --green:#1E6B47; --green-soft:#E3F2E9; --serif:'Source Serif 4', Georgia, serif; --sans:'Libre Franklin', system-ui, -apple-system, sans-serif;
  --mono:'IBM Plex Mono', ui-monospace, monospace;
  --pad:clamp(1rem, 3.2vw, 3.5rem);   /* side margin of the page; full-width bands reach past it */
}
html, body, .stApp, .stMarkdown, button, input, textarea, select, label {font-family:var(--sans);}
.stApp{background:var(--paper); color:var(--ink);}
[data-testid="stHeader"]{background:transparent; height:0;}
[data-testid="stSidebarCollapsedControl"] button, [data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapsedControl"] svg{color:#fff !important;}
.stApp{overflow-x:hidden;}
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"]{visibility:hidden;}
.block-container{padding:0 var(--pad) 0 !important; max-width:100% !important;}
h1, h2, h3, h4{font-family:var(--serif) !important; color:var(--ink) !important; letter-spacing:-.01em;}
.stMarkdown p{line-height:1.6;}

/* masthead + navigation */
.ac-mast{display:flex; align-items:center; justify-content:space-between; gap:1rem; background:var(--ink-dark);
  margin:-1rem calc(-1 * var(--pad)) 0; padding:.85rem var(--pad) .75rem; border-radius:0;}
.ac-brand{display:flex; align-items:center; gap:.7rem; text-decoration:none;}
.ac-brand img{height:38px;}
.ac-word{font:900 1.55rem/1 var(--serif); color:#fff; letter-spacing:.005em;}
.ac-word span{color:var(--gold);}
.ac-sub{font-size:.78rem; color:#BDB8AC; margin-top:.15rem; font-weight:500;}
.ac-mast-right{font:600 .72rem var(--mono); color:#BDB8AC; text-align:right; text-transform:uppercase; letter-spacing:.06em;}
.st-key-nav > div, .st-key-nav [data-testid="stRadio"]{width:100% !important; max-width:100% !important;}
.ac-brand, .ac-brand *{text-decoration:none !important;}
.st-key-nav{background:var(--ink-dark); border-radius:0; padding:0 calc(var(--pad) - .85rem) .5rem; margin:0 calc(-1 * var(--pad)) 0;
  width:calc(100% + 2 * var(--pad)) !important; max-width:none !important; border-top:1px solid #253247;}
.st-key-nav [data-testid="stWidgetLabel"]{display:none;}
.st-key-nav div[role="radiogroup"]{gap:.15rem; flex-wrap:wrap; padding-top:.45rem;}
.st-key-nav label[data-testid="stRadioOption"], .st-key-nav div[role="radiogroup"] label{margin:0 !important; padding:.38rem .85rem;
  border-radius:6px; cursor:pointer;}
.st-key-nav label[data-testid="stRadioOption"] > div > div:first-child:not([data-testid]){display:none;}
.st-key-nav label p{font-weight:600; font-size:.9rem; color:#BDB8AC; margin:0;}
.st-key-nav label:hover p{color:#fff;}
.st-key-nav label[data-selected="true"], .st-key-nav label:has(input:checked){background:transparent; box-shadow:inset 0 -3px 0 var(--gold);}
.st-key-nav label[data-selected="true"] p, .st-key-nav label:has(input:checked) p{color:#fff;}

/* hero */
/* The whole photo is shown: it fills the banner's height and sits on the right; the left is the photo's own navy (#0F1F3B). */
.ac-hero{position:relative; border-radius:0; overflow:hidden; margin:-1rem calc(-1 * var(--pad)) 0; min-height:clamp(540px, 30vw, 660px);
  background:#0F1F3B url('app/static/hero.jpg') right top / auto 100% no-repeat;}
.ac-hero::before{content:""; position:absolute; inset:0;
  background:linear-gradient(90deg, rgba(15,31,59,.96) 0%, rgba(15,31,59,.88) 30%, rgba(15,31,59,.4) 50%, rgba(15,31,59,0) 68%);}
.ac-hero-in{position:relative; padding:3.2rem var(--pad) 1.8rem; max-width:calc(760px + var(--pad));}
.ac-hero-brand{display:flex; align-items:center; gap:.9rem; border-left:4px solid var(--red); padding-left:.9rem;}
.ac-hero-brand img{height:64px;}
.ac-hero h1{font:900 3.1rem/1 var(--serif) !important; color:#fff !important; margin:0 !important; padding:0 !important;}
.ac-hero .ac-hsub{color:var(--gold); font-weight:700; font-size:1.02rem; margin-top:.35rem;}
.ac-tagline{font:italic 600 1.55rem/1.25 var(--serif); color:#fff; margin:1.4rem 0 .8rem;}
.ac-tagline b{color:var(--gold); font-style:normal; font-weight:800;}
.ac-desc{color:#D9DDE5; font-size:1.02rem; line-height:1.6; max-width:560px; display:flex; gap:.8rem;}
.ac-desc::before{content:""; flex:0 0 28px; height:3px; background:var(--gold); margin-top:.75rem;}
.ac-btns{display:flex; gap:.6rem; margin-top:1.4rem; flex-wrap:wrap;}
.ac-btn{display:inline-block; padding:.62rem 1.05rem; font-weight:700; font-size:.92rem; text-decoration:none !important; border-radius:3px;}
.ac-btn.red{background:var(--red); color:#fff !important; border:2px solid var(--red);}
.ac-btn.out{color:#fff !important; border:2px solid #fff;}
.ac-credit{font-size:.72rem; color:#AEB6C4; margin:1.6rem 0 0;}
.ac-hstats{position:relative; display:grid; grid-template-columns:repeat(3, 1fr); gap:1rem; padding:0 var(--pad) 1.6rem; max-width:calc(1250px + var(--pad));}
.ac-hstat{background:rgba(10,22,40,.82); border:1px solid rgba(255,255,255,.16); border-top:5px solid #7FA3D9; border-radius:3px;
  padding:1rem 1.15rem; backdrop-filter:blur(2px);}
.ac-hstat.gold{border-top-color:var(--gold);} .ac-hstat.red{border-top-color:#D9473B;}
.ac-hstat .v{font:700 2.2rem/1.05 var(--mono); color:#A9C3EA;}
.ac-hstat.gold .v{color:#F0C75A;} .ac-hstat.red .v{color:#F08A7E;}
.ac-hstat .l{font-weight:700; font-size:.98rem; margin-top:.35rem; color:#fff;}
.ac-hstat .s{font-size:.82rem; color:#C3CAD6; margin-top:.15rem;}

/* section titles, kicker labels */
.ac-kicker{font:800 .74rem var(--sans); letter-spacing:.1em; text-transform:uppercase; color:var(--red);}
.ac-section{margin:2.2rem 0 .9rem;}
.ac-section h2{font-size:1.75rem !important; font-weight:800 !important; margin:.2rem 0 .3rem !important; padding:0 !important; line-height:1.15;}
.ac-section p{color:var(--ink2); margin:0; max-width:820px; font-size:1rem;}

/* stat cards */
.ac-stats{display:grid; grid-template-columns:repeat(3, 1fr); gap:1rem; margin-top:1rem;}
.ac-stat{background:var(--card); border:1px solid var(--line); border-top:5px solid var(--navy); border-radius:4px; padding:1rem 1.15rem;}
.ac-stat.gold{border-top-color:var(--gold);} .ac-stat.red{border-top-color:var(--red);}
.ac-stat .v{font:700 2.2rem/1.05 var(--mono); color:var(--ink);}
.ac-stat .l{font-weight:700; font-size:.95rem; margin-top:.35rem; color:var(--ink);}
.ac-stat .s{font-size:.82rem; color:var(--mute); margin-top:.15rem;}

/* proportional bars */
.ac-bars{background:var(--card); border:1px solid var(--line); border-radius:4px; padding:.6rem 1.1rem .9rem;}
.ac-bar{display:grid; grid-template-columns:minmax(150px, 290px) 1fr 92px; gap:.8rem; align-items:center; padding:.42rem 0; border-bottom:1px solid var(--line2);}
.ac-bar:last-child{border-bottom:none;}
.ac-bar .n{font-size:.88rem; font-weight:600; color:var(--ink);}
.ac-bar .t{background:var(--line2); height:12px; border-radius:2px; overflow:hidden;}
.ac-bar .t i{display:block; height:100%; background:var(--navy);}
.ac-bar .t i.hl{background:var(--gold);}
.ac-bar .p{font:700 .86rem var(--mono); text-align:right; color:var(--ink);}
.ac-bar .p small{display:block; font:500 .7rem var(--sans); color:var(--mute);}
.ac-stack{display:flex; height:30px; border-radius:3px; overflow:hidden; margin:.6rem 0 .5rem;}
.ac-stack div{display:flex; align-items:center; justify-content:center; color:#fff; font:700 .78rem var(--mono); white-space:nowrap; overflow:hidden;}
.ac-legend{display:flex; gap:1.1rem; flex-wrap:wrap; font-size:.84rem; color:var(--ink2);}
.ac-legend i{display:inline-block; width:11px; height:11px; border-radius:2px; margin-right:.35rem; vertical-align:-1px;}
.ac-note{font-size:.84rem; color:var(--ink2); background:var(--soft); border-left:3px solid var(--gold); padding:.6rem .9rem; margin-top:.8rem; line-height:1.5;}

/* workflow */
.ac-flow{display:grid; grid-template-columns:1fr 26px 1fr 26px 1fr 26px 1fr 26px 1fr; align-items:stretch; margin-top:.4rem;}
.ac-node{background:var(--card); border:1px solid var(--line); border-radius:6px; padding:.9rem .85rem; position:relative;}
.ac-node.dark{background:var(--ink-dark); border-color:var(--ink-dark); color:#fff;}
.ac-node.dark h4, .ac-node.dark .w{color:#fff !important;}
.ac-node .k{font:800 .66rem var(--sans); letter-spacing:.09em; text-transform:uppercase; color:var(--red);}
.ac-node.dark .k{color:var(--gold);}
.ac-node h4{font-size:1.06rem !important; margin:.2rem 0 .3rem !important; padding:0 !important;}
.ac-node .w{font-size:.84rem; color:var(--ink2); line-height:1.45;}
.ac-node .o{margin-top:.5rem; font-size:.74rem; color:var(--mute); border-top:1px dashed var(--line); padding-top:.4rem;}
.ac-node.dark .o{color:#BDB8AC; border-top-color:#33415A;}
.ac-arrow{display:flex; align-items:center; justify-content:center; color:var(--gold); font-size:1.3rem; font-weight:800;}

/* cards, badges, notices */
.ac-card{background:var(--card); border:1px solid var(--line); border-radius:6px; padding:1rem 1.15rem;}
.ac-badges{display:flex; gap:.35rem; flex-wrap:wrap; margin:.2rem 0 .45rem;}
.ac-badge{display:inline-block; padding:.12rem .55rem; border-radius:3px; font-size:.74rem; font-weight:700; background:#ECE8DE; color:var(--ink2);}
.ac-badge.navy{background:#E3E9F3; color:var(--navy);} .ac-badge.gold{background:var(--gold-soft); color:#7A5A00;}
.ac-badge.red{background:var(--red-soft); color:var(--red);} .ac-badge.green{background:var(--green-soft); color:var(--green);}
.ac-notice{background:var(--soft); border:1px solid var(--line); border-left:4px solid var(--gold); border-radius:4px; padding:.65rem .95rem; margin:.5rem 0 .8rem; font-size:.92rem;}
.ac-notice.red{border-left-color:var(--red);} .ac-notice.navy{border-left-color:var(--navy);}
.ac-notice b{color:var(--ink);}
.ac-billtitle{font:600 1.04rem/1.45 var(--sans); color:var(--ink); margin:.1rem 0 .4rem; text-align:justify;}
.ac-crumb{font-size:.82rem; color:var(--mute); margin:1rem 0 .1rem;}

/* bill list */
.ac-thead{display:grid; gap:.6rem; font:800 .7rem var(--sans); letter-spacing:.08em; text-transform:uppercase; color:var(--mute);
  border-bottom:2px solid var(--ink); padding:.5rem .2rem;}
.st-key-billgrid [data-testid="stHorizontalBlock"]{border-bottom:1px solid var(--line2); padding:.55rem 0 .6rem; align-items:center;}
/* keep the filing date inside its row, so the dividing line falls below it */
.st-key-billgrid .stMarkdown, .st-key-billgrid [data-testid="stMarkdown"], .st-key-billgrid [data-testid="stElementContainer"]{margin-bottom:0 !important;}
.st-key-billgrid [data-testid="stColumn"] [data-testid="stVerticalBlock"]{gap:.25rem;}
.st-key-billgrid .ac-filed{margin-top:0;}
.st-key-billgrid [data-testid="stBaseButton-tertiary"]{text-align:left; justify-content:flex-start; padding:0; min-height:0;
  color:var(--navy); font-weight:600; line-height:1.35;}
.st-key-billgrid [data-testid="stBaseButton-tertiary"] p{text-align:left; font-size:.88rem; white-space:normal; overflow:visible;
  text-overflow:clip; display:block;}
.st-key-billgrid [data-testid="stBaseButton-tertiary"] div{white-space:normal; overflow:visible;}
.st-key-billgrid [data-testid="stBaseButton-secondary"]{padding:.25rem .7rem; min-height:0;}
.st-key-billgrid [data-testid="stBaseButton-secondary"] p{font-size:.82rem;}
.st-key-billgrid [data-testid="stBaseButton-tertiary"]:hover p{color:var(--red); text-decoration:underline;}
.ac-billno{font:700 .9rem var(--mono); color:var(--ink);}
.ac-filed{font-size:.75rem; color:var(--mute); margin-top:-.2rem;}
.ac-view a{font-weight:700; font-size:.85rem; color:var(--red) !important; text-decoration:none;}

/* review steps */
.ac-step-h{display:flex; align-items:center; gap:.75rem; flex-wrap:wrap;}
.ac-step-n{display:inline-grid; place-items:center; width:34px; height:34px; border-radius:50%; background:var(--navy); color:#fff;
  font:800 .95rem var(--mono);}
.ac-step-n.done{background:var(--green);} .ac-step-n.lock{background:#B9B4A8;}
.ac-step-t{font:800 1.18rem var(--serif); color:var(--ink);}
.ac-step-t span{color:var(--mute); font-weight:600; font-size:.95rem; font-family:var(--sans);}
.ac-step-d{color:var(--ink2); font-size:.92rem; margin:.35rem 0 .6rem; text-align:justify;}
.ac-progress{display:flex; gap:0; margin:.5rem 0 1rem; border:1px solid var(--line); border-radius:4px; overflow:hidden; background:var(--card);}
.ac-progress div{flex:1; padding:.48rem .4rem; text-align:center; font-size:.78rem; font-weight:700; color:var(--mute); border-right:1px solid var(--line);}
.ac-progress div:last-child{border-right:none;}
.ac-progress .done{background:var(--green-soft); color:var(--green);} .ac-progress .now{background:var(--navy); color:#fff;}
.ac-out p, .ac-out li, .ac-out td{text-align:justify;}
.ac-out{font-size:.94rem;}
.ac-tbl{width:100%; border-collapse:collapse; font-size:.86rem; margin:.4rem 0 .6rem; background:var(--card);}
.ac-tbl th{font:800 .68rem var(--sans); letter-spacing:.07em; text-transform:uppercase; color:var(--mute); text-align:left;
  border-bottom:2px solid var(--ink); padding:.45rem .5rem;}
.ac-tbl td{border-bottom:1px solid var(--line2); padding:.5rem .5rem; vertical-align:top; line-height:1.45;}
.ac-tbl td.m{font:700 .82rem var(--mono); white-space:nowrap;}
.ac-check{background:var(--gold-soft); border:1px solid #E8D79F; border-radius:6px; padding:.7rem .95rem .3rem; margin-top:.7rem;}
.ac-check-h{font:800 .74rem var(--sans); letter-spacing:.09em; text-transform:uppercase; color:#7A5A00; margin-bottom:.3rem;}
.st-key-casecol [data-testid="stVerticalBlockBorderWrapper"]{background:var(--card);}

/* Streamlit widgets */
.stButton > button, .stDownloadButton > button, .stLinkButton > a{border-radius:3px; font-weight:700;}
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"]{background:var(--red); border-color:var(--red); color:#fff;}
.stButton > button[kind="primary"]:hover{background:#9E2A23; border-color:#9E2A23;}
[data-testid="stVerticalBlockBorderWrapper"]{border-radius:6px;}
[data-testid="stDataFrame"]{border:1px solid var(--line); border-radius:4px; background:#fff;}
.stTabs [data-baseweb="tab"]{font-weight:700;}
[data-testid="stMetric"]{background:#fff; border:1px solid var(--line); border-radius:4px; padding:.6rem .8rem;}
[data-testid="stMetricValue"]{font-family:var(--mono); font-size:1.35rem;}
[data-testid="stSidebar"]{background:var(--soft); border-right:1px solid var(--line);}
[data-testid="stExpander"] details{background:#fff; border-radius:4px;}

/* Ask Billy floating companion */
.st-key-billy{position:fixed; right:28px; bottom:96px; z-index:9999; width:auto !important;}
.st-key-billy [data-testid="stPopover"] > div > button, .st-key-billy [data-testid="stPopoverButton"]{
  background:var(--ink-dark) url('app/static/billy.png') 10px center / 46px 46px no-repeat; color:#fff; border:2px solid var(--gold);
  border-radius:40px; padding:.55rem 1.1rem .55rem 62px; min-height:60px; box-shadow:0 8px 24px rgba(10,22,40,.35);}
.st-key-billy [data-testid="stPopover"] > div > button p, .st-key-billy [data-testid="stPopoverButton"] p{color:#fff; font-weight:800; font-size:1rem;}
.st-key-billy [data-testid="stPopover"] > div > button:hover, .st-key-billy [data-testid="stPopoverButton"]:hover{border-color:#fff;}
.ac-billy-head{display:flex; gap:.6rem; align-items:center; border-bottom:1px solid var(--line); padding-bottom:.5rem; margin-bottom:.5rem;}
.ac-billy-head img{width:44px; height:44px;}
.ac-billy-head b{font:800 1.05rem var(--serif);} .ac-billy-head span{display:block; font-size:.78rem; color:var(--mute);}
.ac-msg{border-radius:8px; padding:.5rem .7rem; margin:.3rem 0; font-size:.88rem; line-height:1.45;}
.ac-msg.u{background:#E3E9F3; margin-left:2rem;} .ac-msg.b{background:var(--soft); border:1px solid var(--line); margin-right:1rem;}

/* footer */
.ac-foot{margin:3rem calc(-1 * var(--pad)) 0; background:var(--ink-dark); color:#C9CDD6; border-radius:0; padding:2rem var(--pad) 5.5rem;
  font-size:.84rem; line-height:1.55;}
.ac-foot-grid{display:grid; grid-template-columns:1.3fr 1fr 1fr; gap:1.5rem;}
.ac-foot h5{color:#fff; font:800 .98rem var(--serif); margin:0 0 .35rem;}
.ac-foot a{color:var(--gold) !important;}
.ac-footnote{border-top:1px solid #2A3850; margin-top:1rem; padding-top:.8rem; font-size:.78rem; color:#A9B1C1;}
.ac-footnote b{color:#fff;}

@media (max-width: 900px){
  .ac-mast{padding-left:calc(var(--pad) + 2.4rem);}
  .ac-hero{min-height:0; background-size:cover; background-position:right center;} .ac-hero::before{background:rgba(15,31,59,.86);} .ac-hero h1{font-size:2.3rem !important;}
  .ac-stats{grid-template-columns:1fr;} .ac-hstats{grid-template-columns:1fr;} .ac-foot-grid{grid-template-columns:1fr;}
  .ac-flow{grid-template-columns:1fr;} .ac-arrow{transform:rotate(90deg); height:22px;}
  .ac-bar{grid-template-columns:1fr 70px;} .ac-bar .t{grid-column:1 / -1; grid-row:2;}
  .ac-mast-right{display:none;} .ac-progress{flex-wrap:wrap;} .ac-progress div{flex:1 1 30%;}
}
</style>
"""


def html(s):
    st.markdown(s, unsafe_allow_html=True)


def inject():
    html(CSS)


def masthead(app, sub):
    html(f"""<div class="ac-mast"><a class="ac-brand" href="?page=Home" target="_self"><img src="{STATIC}/logo-mark.svg" alt="">
<div><div class="ac-word">Act<span>Check</span></div><div class="ac-sub">{escape(sub)}</div></div></a>
<div class="ac-mast-right">Philippine legislative review<br>18th–20th Congress</div></div>""")


def hero(app, sub, tagline, desc, credit="", stats=None):
    """stats: (value, label, sub, colour) cards shown inside the banner below the buttons."""
    credit_html = f'<div class="ac-credit">{escape(credit)}</div>' if credit else ""
    stats_html = ""
    if stats:
        stats_html = '<div class="ac-hstats">' + "".join(
            f'<div class="ac-hstat {c}"><div class="v">{escape(str(v))}</div><div class="l">{escape(l)}</div><div class="s">{escape(s)}</div></div>'
            for v, l, s, c in stats) + "</div>"
    t = " ".join(f"<b>{escape(w.split(' ', 1)[0])}</b> {escape(w.split(' ', 1)[1])}" if " " in w else escape(w)
                 for w in [s.strip() + "." for s in tagline.strip(".").split(".") if s.strip()])
    html(f"""<div class="ac-hero"><div class="ac-hero-in">
<div class="ac-hero-brand"><img src="{STATIC}/logo-mark.svg" alt=""><div><h1>{escape(app)}</h1><div class="ac-hsub">{escape(sub)}</div></div></div>
<div class="ac-tagline">{t}</div>
<div class="ac-desc">{escape(desc)}</div>
<div class="ac-btns"><a class="ac-btn red" href="?page=Bills" target="_self">Browse the bills →</a>
<a class="ac-btn out" href="?page=How it Works" target="_self">How it works</a></div>
{credit_html}
</div>{stats_html}</div>""")


def section(kicker, title, text=""):
    html(f'<div class="ac-section"><div class="ac-kicker">{escape(kicker)}</div><h2>{escape(title)}</h2>'
         + (f"<p>{text}</p>" if text else "") + "</div>")


def stats(items):
    """items: (value, label, sub, colour) with colour in '', 'gold', 'red'."""
    html('<div class="ac-stats">' + "".join(
        f'<div class="ac-stat {c}"><div class="v">{escape(str(v))}</div><div class="l">{escape(l)}</div><div class="s">{escape(s)}</div></div>'
        for v, l, s, c in items) + "</div>")


def bars(rows, highlight=None):
    """rows: (label, count, share). Bars are drawn to scale against the largest share."""
    top = max((r[2] for r in rows), default=1) or 1
    cells = "".join(
        f'<div class="ac-bar"><div class="n">{escape(n)}</div><div class="t"><i class="{"hl" if n == highlight else ""}" '
        f'style="width:{100 * s / top:.1f}%"></i></div><div class="p">{s:.1%}<small>{c:,} bills</small></div></div>'
        for n, c, s in rows)
    html(f'<div class="ac-bars">{cells}</div>')


def stack(parts, colors):
    seg = "".join(f'<div style="width:{max(s, .004) * 100:.2f}%; background:{colors[i]}">{s:.0%}</div>' for i, (_, _, s) in enumerate(parts))
    leg = "".join(f'<span><i style="background:{colors[i]}"></i>{escape(n)} · {c:,}</span>' for i, (n, c, _) in enumerate(parts))
    html(f'<div class="ac-stack">{seg}</div><div class="ac-legend">{leg}</div>')


def note(body_html):
    html(f'<div class="ac-note">{body_html}</div>')


def notice(body_html, kind=""):
    html(f'<div class="ac-notice {kind}">{body_html}</div>')


def badges(items):
    """items: (text, kind) with kind in '', 'navy', 'gold', 'red', 'green'."""
    html('<div class="ac-badges">' + "".join(f'<span class="ac-badge {k}">{escape(str(t))}</span>' for t, k in items if t) + "</div>")


def flow(nodes):
    """nodes: (kicker, title, what, output, dark)."""
    parts = []
    for i, (k, t, w, o, dark) in enumerate(nodes):
        if i:
            parts.append('<div class="ac-arrow">→</div>')
        parts.append(f'<div class="ac-node {"dark" if dark else ""}"><div class="k">{escape(k)}</div><h4>{escape(t)}</h4>'
                     f'<div class="w">{escape(w)}</div><div class="o">{escape(o)}</div></div>')
    html('<div class="ac-flow">' + "".join(parts) + "</div>")


def progress(names, states):
    """states: list of 'done' / 'now' / ''."""
    html('<div class="ac-progress">' + "".join(f'<div class="{s}">{"✓ " if s == "done" else ""}{escape(n)}</div>'
                                                for n, s in zip(names, states)) + "</div>")


def step_header(n, title, sub, state):
    cls = {"done": "done", "lock": "lock"}.get(state, "")
    mark = "✓" if state == "done" else str(n)
    chip = {"done": ("Done", "green"), "lock": ("Locked", ""), "now": ("Ready", "gold")}.get(state, ("Ready", "gold"))
    html(f'<div class="ac-step-h"><span class="ac-step-n {cls}">{mark}</span><span class="ac-step-t">{escape(title)} '
         f'<span>· {escape(sub)}</span></span><span class="ac-badge {chip[1]}">{chip[0]}</span></div>')


def table(headers, rows, mono_cols=()):
    head = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f'<td class="{"m" if j in mono_cols else ""}">{c}</td>' for j, c in enumerate(r)) + "</tr>" for r in rows)
    html(f'<table class="ac-tbl"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>')


def footer(app, label):
    html(f"""<div class="ac-foot"><div class="ac-foot-grid">
<div><h5>{escape(app)}</h5>An agentic AI system for Philippine legislative review. Three agents trace a bill's history, spot what changed
and weigh its legal and budget implications; the analyst checks every step and decides.</div>
<div><h5>Data sources</h5>House and Senate bill documents (public); Open Congress Data and the Philippine Legal Documents Library
(BetterGov.PH); DBM salary schedule (NBC No. 601); COA annual audit reports. Bill types are classified from titles by rules.</div>
<div><h5>Use of AI</h5>Every claim is cited and checked against the source text. {escape(label)}
Code: <a href="https://github.com/latsandoval1999/ActCheck" target="_blank">GitHub</a>.</div></div>
<div class="ac-footnote"><b>About this prototype.</b> ActCheck is a prototype made as an individual project by Louise Antonette T. Sandoval,
a student of the Lee Kuan Yew School of Public Policy, National University of Singapore, in fulfilment of the PP5538 Digital Technology
and Public Policy course. It is not an official government website and is not operated by or affiliated with the House of
Representatives, the Senate or the Department of Budget and Management.</div></div>""")
