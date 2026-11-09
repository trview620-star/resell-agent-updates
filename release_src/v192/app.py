"""Resell Agent v1.9.2 — a simple visual list of current supplier products."""
from __future__ import annotations
import streamlit as st
from agent import db,extra_db,updater
from agent.ui_theme import render_theme
from agent.ui_updates import render_updates
from agent.ui_trending_catalog import render as render_trending_catalog

updater.touch_activity()
st.set_page_config(page_title='Resell Agent · Termékek',page_icon='◈',layout='wide',initial_sidebar_state='expanded')
db.initialize();extra_db.initialize();render_theme()
st.markdown("""<style>
[data-testid="stMainBlockContainer"],.block-container{max-width:1700px!important;padding:.8rem 1.2rem 3rem!important}
section[data-testid="stSidebar"]{min-width:210px!important;max-width:210px!important;background:#09131c!important;border-right:1px solid #263943!important}
section[data-testid="stSidebar"] [data-testid="stRadio"] label{border-radius:10px!important;padding:.55rem .65rem!important}
section[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked){background:rgba(33,208,168,.15)!important;border-left:3px solid #29d9b4}
.trend-brand{display:flex;justify-content:space-between;align-items:center;padding:13px 17px;margin-bottom:20px;border:1px solid #29424a;border-radius:14px;background:linear-gradient(110deg,#12212b,#0c1720)}
.trend-brand b{font-size:1.05rem;color:#eaf6f4}.trend-brand b span{color:#32dfb7}.trend-brand small{color:#8fa8af}
.trend-eyebrow{font-size:.68rem;font-weight:850;letter-spacing:.2em;color:#3cdeba;margin:.45rem 0}
.trend-placeholder{height:175px;display:grid;place-items:center;border:1px dashed #354c56;border-radius:11px;background:radial-gradient(ellipse at 50% 80%,#1a3437,#0b141b 68%);color:#6d8991;font-size:.72rem;letter-spacing:.15em}
.trend-empty{padding:28px;border:1px solid #263c46;border-radius:16px;background:linear-gradient(145deg,#12232d,#0b141c)}.trend-empty span{color:#37dcb6;font-weight:800;letter-spacing:.16em;font-size:.7rem}.trend-empty h3{color:#e9f5f2;margin:.6rem 0}.trend-empty p{color:#9cb2b8;max-width:650px}
[data-testid="stVerticalBlockBorderWrapper"]{background:linear-gradient(155deg,#111f29,#0b151d)!important;border-color:#263b45!important;border-radius:14px!important}
[data-testid="stImage"] img{border-radius:10px;object-fit:contain;background:#0a1218}
[data-testid="stLinkButton"] a,.stButton>button{border-radius:10px!important;min-height:2.4rem!important}
.stButton>button[kind="primary"]{background:#24cfa8!important;color:#05261f!important;border-color:#24cfa8!important;font-weight:800!important}
@media(max-width:850px){[data-testid="stMainBlockContainer"],.block-container{padding:.6rem .55rem 2rem!important}section[data-testid="stSidebar"]{min-width:0!important;max-width:none!important}}
</style>""",unsafe_allow_html=True)
with st.sidebar:
    st.markdown('## ◈ Resell <span style="color:#35dfb7">Agent</span>',unsafe_allow_html=True)
    st.caption('TERMÉKELŐNÉZET')
    page=st.radio('Navigáció',['Termékek','App updates'],key='resell_v192_page',label_visibility='collapsed')
    st.divider();st.caption('13 jóváhagyott bolt')
st.markdown('<div class="trend-brand"><b>◈ &nbsp; Resell <span>Agent</span></b><small>FRISS TERMÉKEK &nbsp;·&nbsp; 13 BOLT &nbsp;·&nbsp; KÉPES ELŐNÉZET</small></div>',unsafe_allow_html=True)
if page=='Termékek':render_trending_catalog()
else:render_updates()
