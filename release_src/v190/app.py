"""Resell Agent v1.9.0 — supplier catalogue cards to a posting pack."""
from __future__ import annotations
import streamlit as st
from agent import db, extra_db, updater
from agent.ui_theme import render_theme
from agent.ui_updates import render_updates
from agent.ui_product_studio import render as render_product_studio

updater.touch_activity()
st.set_page_config(page_title='Resell Agent · Product Studio',page_icon='◈',layout='wide',initial_sidebar_state='expanded')
db.initialize();extra_db.initialize();render_theme()
st.markdown("""<style>
[data-testid="stMainBlockContainer"],.block-container{max-width:1740px!important;padding:.7rem 1.25rem 3rem!important}
section[data-testid="stSidebar"]{min-width:215px!important;max-width:215px!important;background:#09121a!important;border-right:1px solid #22343b!important}
section[data-testid="stSidebar"] [data-testid="stRadio"] label{border-radius:10px!important;padding:.52rem .6rem!important}
section[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked){background:linear-gradient(90deg,rgba(35,205,165,.2),rgba(13,77,73,.12))!important;border-left:3px solid #27dfb6}
.studio-brand{display:flex;align-items:center;justify-content:space-between;padding:13px 18px;margin-bottom:18px;border:1px solid #29424a;border-radius:15px;background:radial-gradient(ellipse at 8% 50%,rgba(41,209,171,.12),transparent 38%),linear-gradient(110deg,#12212a,#0b151e)}
.studio-brand b{font-size:1.05rem;letter-spacing:-.02em;color:#eff9f7}.studio-brand b span{color:#37e1b8}.studio-brand small{color:#8ba8b0;font-size:.76rem}
.studio-eyebrow{font-size:.67rem;letter-spacing:.2em;font-weight:850;color:#37e1b8;margin:.35rem 0}
.studio-placeholder{height:190px;display:grid;place-items:center;border:1px dashed #34505a;border-radius:11px;background:radial-gradient(ellipse at 50% 80%,#1a3337,#0b141d 65%);color:#67828a;font-size:.7rem;letter-spacing:.16em}
.studio-empty{padding:30px;border:1px solid #263b46;border-radius:17px;background:radial-gradient(ellipse at 72% 10%,rgba(24,176,147,.14),transparent 36%),linear-gradient(150deg,#12212c,#0b141b)}
.studio-empty span{font-size:.7rem;letter-spacing:.18em;color:#3be0b7;font-weight:800}.studio-empty h3{margin:.6rem 0;color:#ebf7f4}.studio-empty p{max-width:640px;color:#9cb1b8}
[data-testid="stVerticalBlockBorderWrapper"]{background:linear-gradient(155deg,#111e28,#0c151d)!important;border-color:#243943!important;border-radius:15px!important;box-shadow:0 6px 24px rgba(0,0,0,.1)}
[data-testid="stMetric"]{background:#12212b!important;border:1px solid #2a4148!important;border-radius:12px!important}
[data-testid="stMetricValue"]{color:#f1faf8!important}
[data-testid="stImage"] img{border-radius:10px;object-fit:contain;background:#0a1118}
[data-testid="stLinkButton"] a,.stButton>button,.stDownloadButton>button{border-radius:10px!important;min-height:2.45rem!important}
.stButton>button[kind="primary"],.stDownloadButton>button[kind="primary"]{background:#25d0a8!important;color:#062721!important;border-color:#25d0a8!important;font-weight:800!important}
[data-testid="stTextInput"] input,[data-testid="stNumberInput"] input,[data-testid="stSelectbox"] [data-baseweb="select"],[data-testid="stTextArea"] textarea{background:#111e28!important;border-color:#2b424c!important;border-radius:9px!important}
@media(max-width:850px){[data-testid="stMainBlockContainer"],.block-container{padding:.55rem .55rem 2rem!important}section[data-testid="stSidebar"]{min-width:0!important;max-width:none!important}}
</style>""",unsafe_allow_html=True)
with st.sidebar:
    st.markdown('## ◈ Resell <span style="color:#36dfb7">Agent</span>',unsafe_allow_html=True)
    st.caption('V1.9 · PRODUCT STUDIO')
    page=st.radio('Navigáció',['Termékkatalógus','App updates'],key='resell_v190_page',label_visibility='collapsed')
    st.divider();st.caption('13 bolt · eBay Sold kereslet')
    st.caption('Kiválasztás → képcsomag → poszt')
st.markdown('<div class="studio-brand"><b>◈ &nbsp; Resell <span>Agent</span></b><small>DEMAND SIGNAL &nbsp;·&nbsp; 13 SUPPLIERS &nbsp;·&nbsp; POST STUDIO</small></div>',unsafe_allow_html=True)
if page=='Termékkatalógus':render_product_studio()
else:render_updates()
