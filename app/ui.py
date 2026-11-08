"""Look and feel for the ActCheck portal: one stylesheet plus small HTML helpers.

Original branding only (an "AC" monogram, no government seals or logos), with a permanent
prototype notice so the portal is never mistaken for an official government website.
"""
from html import escape

import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,600;8..60,700&display=swap');
:root{
  --ac-navy:#0B2545; --ac-blue:#1B3B6F; --ac-sky:#E8EEF8; --ac-gold:#C9A227; --ac-gold-soft:#FBF5E1;
  --ac-bg:#F3F5F9; --ac-surface:#FFFFFF; --ac-text:#172033; --ac-muted:#5B6475; --ac-border:#DCE2EC;
  --ac-green:#1E6B47; --ac-green-soft:#E6F4EC; --ac-amber:#8A5A00; --ac-amber-soft:#FFF4DB; --ac-grey-soft:#EEF1F5;
}
html, body, .stApp, .stMarkdown, button, input, textarea, select {font-family:'Source Sans 3', system-ui, -apple-system, 'Segoe UI', sans-serif;}
.stApp{background:var(--ac-bg); color:var(--ac-text);}
[data-testid="stHeader"]{background:transparent; height:2.2rem;}
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"]{visibility:hidden;}
.block-container{padding-top:.75rem; padding-bottom:2rem; max-width:1240px;}
h1, h2, h3, h4{font-family:'Source Serif 4', Georgia, serif !important; color:var(--ac-navy) !important; letter-spacing:-.005em;}

/* top strip and header */
.ac-strip{display:flex; justify-content:space-between; gap:1rem; flex-wrap:wrap; background:var(--ac-surface);
  border:1px solid var(--ac-border); border-bottom:none; border-radius:12px 12px 0 0; padding:.32rem 1.1rem;
  font-size:.78rem; color:var(--ac-muted);}
.ac-strip b{color:var(--ac-navy); font-weight:600;}
.ac-header{display:flex; align-items:center; justify-content:space-between; gap:1rem;
  background:linear-gradient(115deg, var(--ac-navy) 0%, var(--ac-blue) 70%, #24508F 100%); color:#fff;
  border-radius:0 0 14px 14px; padding:1.05rem 1.4rem; box-shadow:0 8px 24px rgba(11,37,69,.16); position:relative; overflow:hidden;}
.ac-header::after{content:""; position:absolute; right:-60px; top:-60px; width:220px; height:220px; border-radius:50%;
  border:28px solid rgba(201,162,39,.12);}
.ac-brand{display:flex; align-items:center; gap:.9rem; z-index:1;}
.ac-mark{width:48px; height:48px; border-radius:11px; background:#fff; color:var(--ac-navy); display:grid; place-items:center;
  font:700 1.2rem 'Source Serif 4', Georgia, serif; border:2px solid var(--ac-gold); box-shadow:0 2px 6px rgba(0,0,0,.15);}
.ac-name{font:700 1.65rem/1.05 'Source Serif 4', Georgia, serif; letter-spacing:.01em;}
.ac-tag{font-size:.86rem; opacity:.86; margin-top:.18rem;}
.ac-right{text-align:right; font-size:.8rem; line-height:1.35; z-index:1;}
.ac-right b{display:block; font-size:1.02rem; color:#fff;}
.ac-right .ac-rule{display:inline-block; width:46px; height:3px; background:var(--ac-gold); border-radius:2px; margin:.25rem 0;}

/* navigation (horizontal radio with key "nav") */
.st-key-nav{margin:.7rem 0 .2rem 0;}
.st-key-nav [data-testid="stWidgetLabel"]{display:none;}
.st-key-nav div[role="radiogroup"]{gap:.25rem; flex-wrap:wrap; background:var(--ac-surface); border:1px solid var(--ac-border);
  border-radius:10px; padding:.3rem;}
.st-key-nav label[data-testid="stRadioOption"], .st-key-nav div[role="radiogroup"] label{margin:0 !important; padding:.4rem 1rem;
  border-radius:7px; cursor:pointer;}
.st-key-nav label[data-testid="stRadioOption"] > div > div:first-child:not([data-testid]){display:none;}
.st-key-nav label p{font-weight:600; font-size:.93rem; color:var(--ac-muted); margin:0;}
.st-key-nav label:hover{background:var(--ac-sky);}
.st-key-nav label:hover p{color:var(--ac-navy);}
.st-key-nav label[data-selected="true"], .st-key-nav label:has(input:checked){background:var(--ac-navy);}
.st-key-nav label[data-selected="true"] p, .st-key-nav label:has(input:checked) p{color:#fff;}

/* hero */
.ac-hero{background:var(--ac-surface); border:1px solid var(--ac-border); border-radius:14px; padding:1.4rem 1.5rem 1.2rem;
  margin:.6rem 0 1rem; display:grid; grid-template-columns:1.25fr 1fr; gap:1.4rem; align-items:center;}
.ac-kicker{font-size:.75rem; font-weight:700; letter-spacing:.09em; text-transform:uppercase; color:var(--ac-gold);}
.ac-hero h1{font-size:2rem !important; margin:.15rem 0 .4rem !important; padding:0 !important;}
.ac-hero p{color:var(--ac-muted); margin:0; font-size:1rem; line-height:1.5;}
.ac-kpis{display:grid; grid-template-columns:repeat(2, 1fr); gap:.7rem;}
.ac-kpis.four{grid-template-columns:repeat(4, 1fr);}
.ac-kpi{background:var(--ac-surface); border:1px solid var(--ac-border); border-top:3px solid var(--ac-gold);
  border-radius:10px; padding:.7rem .95rem;}
.ac-kpi .v{font:700 1.65rem/1.1 'Source Serif 4', Georgia, serif; color:var(--ac-navy);}
.ac-kpi .l{font-size:.74rem; color:var(--ac-muted); text-transform:uppercase; letter-spacing:.05em; font-weight:600; margin-top:.15rem;}

/* cards, notices, section titles */
.ac-section{margin:1.3rem 0 .55rem;}
.ac-section h3{margin:0 !important; padding:0 !important; font-size:1.3rem !important;}
.ac-section .ac-sub{color:var(--ac-muted); font-size:.92rem; margin-top:.1rem;}
.ac-section::after{content:""; display:block; width:42px; height:3px; background:var(--ac-gold); border-radius:2px; margin-top:.4rem;}
.ac-card{background:var(--ac-surface); border:1px solid var(--ac-border); border-radius:12px; padding:1rem 1.15rem; height:100%;}
.ac-card h4{margin:.1rem 0 .35rem !important; font-size:1.08rem !important;}
.ac-card p{margin:0; color:var(--ac-muted); font-size:.93rem; line-height:1.5;}
.ac-card .ac-num{display:inline-grid; place-items:center; width:26px; height:26px; border-radius:50%; background:var(--ac-navy);
  color:#fff; font-weight:700; font-size:.82rem; margin-right:.4rem;}
.ac-notice{display:flex; gap:.8rem; align-items:flex-start; background:var(--ac-gold-soft); border:1px solid #EBDCA8;
  border-left:4px solid var(--ac-gold); border-radius:10px; padding:.7rem 1rem; margin:.4rem 0 .8rem; font-size:.93rem;}
.ac-notice.info{background:var(--ac-sky); border-color:#C9D6EC; border-left-color:var(--ac-blue);}
.ac-notice b{color:var(--ac-navy);}
.ac-notice .ac-nlabel{font-size:.7rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; color:var(--ac-amber); display:block;}
.ac-notice.info .ac-nlabel{color:var(--ac-blue);}

/* badges and status steps */
.ac-badges{display:flex; gap:.35rem; flex-wrap:wrap; margin:.25rem 0 .5rem;}
.ac-badge{display:inline-block; padding:.12rem .6rem; border-radius:999px; font-size:.76rem; font-weight:600;
  background:var(--ac-grey-soft); color:var(--ac-text); border:1px solid var(--ac-border);}
.ac-badge.pilot{background:var(--ac-gold-soft); color:var(--ac-amber); border-color:#EBDCA8;}
.ac-badge.good{background:var(--ac-green-soft); color:var(--ac-green); border-color:#BFE0CD;}
.ac-badge.navy{background:var(--ac-sky); color:var(--ac-navy); border-color:#C9D6EC;}
.ac-crumb{font-size:.84rem; color:var(--ac-muted); margin:.5rem 0 .1rem;}
.ac-crumb b{color:var(--ac-navy);}
.ac-billtitle{font:600 1.02rem/1.45 'Source Sans 3', sans-serif; color:var(--ac-text); margin:.1rem 0 .3rem;}
.ac-steps{display:flex; gap:0; margin:.5rem 0 .9rem; background:var(--ac-surface); border:1px solid var(--ac-border); border-radius:10px; overflow:hidden;}
.ac-step{flex:1; padding:.5rem .6rem; font-size:.8rem; color:var(--ac-muted); border-right:1px solid var(--ac-border); text-align:center; font-weight:600;}
.ac-step:last-child{border-right:none;}
.ac-step.done{background:var(--ac-green-soft); color:var(--ac-green);}
.ac-step.now{background:var(--ac-navy); color:#fff;}

/* Streamlit widgets */
.stButton > button, .stDownloadButton > button{border-radius:8px; font-weight:600; border:1px solid var(--ac-border);}
.stButton > button[kind="primary"]{background:var(--ac-navy); border-color:var(--ac-navy);}
.stButton > button[kind="primary"]:hover{background:var(--ac-blue); border-color:var(--ac-blue);}
[data-testid="stDataFrame"]{border:1px solid var(--ac-border); border-radius:10px; overflow:hidden; background:#fff;}
[data-testid="stVerticalBlockBorderWrapper"]{background:var(--ac-surface); border-radius:12px;}
.stTabs [data-baseweb="tab-list"]{gap:.2rem; border-bottom:2px solid var(--ac-border);}
.stTabs [data-baseweb="tab"]{font-weight:600; padding:.45rem .9rem;}
.stTabs [aria-selected="true"]{color:var(--ac-navy) !important;}
[data-testid="stMetric"]{background:#fff; border:1px solid var(--ac-border); border-radius:10px; padding:.6rem .8rem;}
[data-testid="stSidebar"]{background:#fff; border-right:1px solid var(--ac-border);}
[data-testid="stExpander"] details{background:#fff; border-radius:10px;}

/* footer */
.ac-footer{margin-top:2.4rem; background:var(--ac-navy); color:#D9E1EE; border-radius:14px; padding:1.3rem 1.5rem 1rem;
  display:grid; grid-template-columns:1.2fr 1fr 1fr; gap:1.4rem; font-size:.84rem; line-height:1.5;}
.ac-footer h5{color:#fff; font:700 .95rem 'Source Serif 4', Georgia, serif; margin:0 0 .35rem;}
.ac-footer a{color:#F3D77A;}
.ac-footer .ac-legal{grid-column:1 / -1; border-top:1px solid rgba(255,255,255,.15); padding-top:.7rem; font-size:.76rem; color:#AEB9CC;}

@media (max-width: 820px){
  .ac-hero{grid-template-columns:1fr;} .ac-kpis.four{grid-template-columns:repeat(2, 1fr);}
  .ac-right{display:none;} .ac-footer{grid-template-columns:1fr;} .ac-steps{flex-wrap:wrap;}
  .ac-step{flex:1 1 45%; border-bottom:1px solid var(--ac-border);}
}
</style>
"""


def html(s):
    st.markdown(s, unsafe_allow_html=True)


def inject():
    html(CSS)


def header(app, tagline, congress="20th Congress"):
    html(f"""
<div class="ac-strip"><span><b>Student prototype</b> · PP5538 Digital Technology and Public Policy · Not an official government website</span>
<span>AI-assisted drafts for reviewer validation</span></div>
<div class="ac-header">
  <div class="ac-brand"><div class="ac-mark">AC</div>
    <div><div class="ac-name">{escape(app)}</div><div class="ac-tag">{escape(tagline)}</div></div></div>
  <div class="ac-right"><b>{escape(congress)}</b><span class="ac-rule"></span><br>Bill monitoring and preliminary review</div>
</div>""")


def section(title, sub=""):
    html(f'<div class="ac-section"><h3>{escape(title)}</h3>' + (f'<div class="ac-sub">{escape(sub)}</div>' if sub else "") + "</div>")


def kpis(items, four=True):
    cells = "".join(f'<div class="ac-kpi"><div class="v">{escape(str(v))}</div><div class="l">{escape(l)}</div></div>' for v, l in items)
    return f'<div class="ac-kpis{" four" if four else ""}">{cells}</div>'


def hero(kicker, title, text, stats):
    html(f"""<div class="ac-hero"><div><div class="ac-kicker">{escape(kicker)}</div><h1>{escape(title)}</h1><p>{escape(text)}</p></div>
{kpis(stats, four=False)}</div>""")


def notice(label, body_html, kind=""):
    html(f'<div class="ac-notice {kind}"><div><span class="ac-nlabel">{escape(label)}</span>{body_html}</div></div>')


def badges(items):
    """items: list of (text, kind) with kind in '', 'pilot', 'good', 'navy'."""
    html('<div class="ac-badges">' + "".join(f'<span class="ac-badge {k}">{escape(t)}</span>' for t, k in items) + "</div>")


def steps(names, current):
    i = names.index(current) if current in names else 0
    cells = "".join(f'<div class="ac-step {"done" if j < i else "now" if j == i else ""}">{escape(n.capitalize())}</div>'
                    for j, n in enumerate(names))
    html(f'<div class="ac-steps">{cells}</div>')


def card(title, text, num=None):
    n = f'<span class="ac-num">{num}</span>' if num is not None else ""
    html(f'<div class="ac-card"><h4>{n}{escape(title)}</h4><p>{text}</p></div>')


def footer(app, label):
    html(f"""<div class="ac-footer">
<div><h5>{escape(app)}</h5>A student prototype for PP5538 Digital Technology and Public Policy (Lee Kuan Yew School of Public Policy).
It helps a budget reviewer do the preliminary review of proposed legislative measures. It is not operated by, or affiliated with,
the House of Representatives, the Senate or the Department of Budget and Management.</div>
<div><h5>Data sources</h5>House and Senate bill documents (public); Open Congress Data and the Philippine Legal Documents Library
(BetterGov.PH); DBM salary schedule (NBC No. 601); COA annual audit reports. See the About page for licences.</div>
<div><h5>Use of AI</h5>Three agents draft evidence, comparisons and appraisals. Every claim is cited and checked against the source;
a person reviews and decides. Code: <a href="https://github.com/latsandoval1999/ActCheck" target="_blank">GitHub</a>.</div>
<div class="ac-legal">{escape(label)}</div></div>""")
