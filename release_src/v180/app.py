"""Resell Agent v1.8.0 — demand-first product discovery board."""
from __future__ import annotations

import streamlit as st

from agent import db, extra_db, updater
from agent.ui_theme import render_theme
from agent.ui_updates import render_updates
from agent.ui_demand_workbench import render as render_demand_workbench

updater.touch_activity()
st.set_page_config(page_title='Resell Agent · Keresleti radar',page_icon='⌁',layout='wide',initial_sidebar_state='expanded')
db.initialize()
extra_db.initialize()
render_theme()

st.markdown("""<style>
[data-testid="stMainBlockContainer"],.block-container{max-width:1780px!important;padding:.7rem 1.1rem 3rem!important}
section[data-testid="stSidebar"]{min-width:212px!important;max-width:212px!important;background:#0a121c!important;border-right:1px solid #23313f!important}
section[data-testid="stSidebar"] [data-testid="stRadio"] label{border-radius:10px!important;padding:.48rem .55rem!important}
section[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked){background:linear-gradient(90deg,rgba(22,201,165,.22),rgba(15,86,91,.18))!important;border-left:3px solid #26d8b3}
.demand-brand{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;margin-bottom:18px;border:1px solid #243844;border-radius:13px;background:linear-gradient(100deg,#111f2a,#0c1821)}
.demand-brand b{font-size:1rem;letter-spacing:-.02em;color:#eaf6f6}.demand-brand b span{color:#2bd9b4}.demand-brand small{color:#8ba4b2}
.demand-eyebrow{font-size:.67rem;font-weight:800;letter-spacing:.18em;color:#2bd9b4;margin:.4rem 0}
.demand-image-empty{height:145px;display:flex;align-items:center;justify-content:center;flex-direction:column;border:1px dashed #344651;border-radius:10px;background:#0b141d;color:#57707d;text-align:center;font-size:2.2rem}
.demand-image-empty small{font-size:.7rem}.demand-diagnostic{padding:14px 15px;min-height:68px;background:#101b26;border:1px solid #1d2b38;border-radius:11px;color:#e2ecee}.demand-diagnostic span{font-size:.78rem;color:#8fa3af}
.demand-empty{padding:22px 18px;border:1px solid #263642;border-radius:14px;background:linear-gradient(155deg,#111f2a,#0b141d);color:#a8bbc3}.demand-empty>span{font-weight:800;color:#28d6b4}.demand-empty h3{margin:.6rem 0;color:#e7f1f3}.demand-empty-side{min-height:440px;padding:2rem;border:1px solid #233642;border-radius:17px;background:radial-gradient(ellipse at 58% 22%,rgba(26,159,144,.18),transparent 44%),linear-gradient(160deg,#101d28,#0a1119);display:flex;flex-direction:column;justify-content:center}.demand-empty-side h3{color:#eaf3f5}.demand-empty-side p{max-width:450px;color:#97aeb8}.orbit{font-size:3rem;color:#20d3ac}.demand-steps{display:flex;gap:.5rem;flex-wrap:wrap;margin-top:1.3rem}.demand-steps span{border:1px solid #29414b;padding:.5rem .7rem;border-radius:9px;color:#abd4d2;background:#13232c;font-size:.78rem}
[data-testid="stVerticalBlockBorderWrapper"]{background:linear-gradient(150deg,#101a24,#0c141d)!important;border-color:#23333f!important;border-radius:14px!important}
[data-testid="stMetric"]{background:#111e28!important;border:1px solid #263944!important;border-radius:13px!important}
[data-testid="stMetricValue"]{color:#eff7f6!important}
[data-testid="stLinkButton"] a,.stButton>button,.stDownloadButton>button{border-radius:10px!important}
.stButton>button[kind="primary"]{background:#21cba8!important;color:#052622!important;border-color:#21cba8!important;font-weight:750!important}
[data-testid="stTextInput"] input,[data-testid="stNumberInput"] input,[data-testid="stSelectbox"] [data-baseweb="select"],[data-testid="stTextArea"] textarea{background:#111d28!important;border-color:#2a3c48!important;border-radius:9px!important}
@media(max-width:900px){[data-testid="stMainBlockContainer"],.block-container{padding:.6rem .5rem 2rem!important}section[data-testid="stSidebar"]{min-width:0!important;max-width:none!important}}
</style>""",unsafe_allow_html=True)

with st.sidebar:
    st.markdown('## ⌁ Resell <span style="color:#28d8b1">Agent</span>',unsafe_allow_html=True)
    st.caption('V1.8 · KERESLETI RADAR')
    page=st.radio('Navigáció',['Keresleti radar','App updates'],key='resell_v180_page',label_visibility='collapsed')
    st.divider()
    st.caption('13 beszállító · Vác · max. 4 munkanap')
    st.caption('Vinted: kutatási/értékesítési piac')

st.markdown('<div class="demand-brand"><b>⌁ &nbsp; Resell <span>Agent</span></b><small>13 webshop &nbsp;·&nbsp; eBay Sold kereslet &nbsp;·&nbsp; Vinted-piackutatás</small></div>',unsafe_allow_html=True)
if page=='Keresleti radar':
    render_demand_workbench()
else:
    render_updates()
