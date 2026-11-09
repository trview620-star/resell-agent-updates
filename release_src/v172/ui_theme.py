"""Shared modern theme across Resell Agent. Safe, CSS-only visual changes."""
from __future__ import annotations
import html
import streamlit as st

CSS=r"""
<style>
:root{
    --resell-bg:#0b1019;
    --resell-surface:#131d29;
    --resell-elevated:#192633;
    --resell-line:#29394a;
    --resell-text:#eef5fa;
    --resell-muted:#a2b3c1;
    --resell-accent:#53d5b4;
}
html,body,[data-testid="stApp"],[data-testid="stMain"] {
    background:#0b1019!important;color:var(--resell-text);
    font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
}
[data-testid="stMain"]{
    background:radial-gradient(ellipse 70% 20% at 70% 0%,rgba(23,106,114,.17),transparent 72%),#0b1019!important;
}
[data-testid="stMainBlockContainer"],.block-container{
    max-width:1520px!important;padding:1.4rem 2.3rem 6rem!important;
}
section[data-testid="stSidebar"]{
    background:#0f1722!important;border-right:1px solid #273443!important;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] label{
    border-radius:12px;transition:background .18s;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] label:hover{background:#1e2d3c}
[data-testid="stHeader"] {background:transparent!important}
[data-testid="stMetric"]{
    background:linear-gradient(145deg,#182534,#121c29)!important;
    border:1px solid #2a3b48!important;border-radius:16px!important;
    padding:1rem 1.15rem!important;
    box-shadow:0 5px 23px rgba(0,0,0,.11);
}
[data-testid="stMetricValue"]{font-weight:750!important;letter-spacing:-.025em;color:#f4fcff!important}
[data-testid="stMetricLabel"]{color:#a7bdca!important}
[data-testid="stVerticalBlockBorderWrapper"]{
    background:linear-gradient(155deg,#141f2c,#111a25);
    border:1px solid #293949!important;border-radius:18px!important;
    box-shadow:0 8px 26px rgba(0,0,0,.1);
}
.stButton>button,.stDownloadButton>button,[data-testid="stLinkButton"] a{
    border-radius:11px!important;min-height:2.65rem;
    font-weight:620!important;transition:transform .12s,background .15s;
}
.stButton>button:hover,[data-testid="stLinkButton"] a:hover{
    transform:translateY(-1px);
}
.stButton>button[kind="primary"]{
    background:linear-gradient(120deg,#54d6b5,#38acbb)!important;
    border-color:#4dc7b3!important;color:#092027!important;
    box-shadow:0 6px 18px rgba(52,193,172,.12);
}
[data-testid="stDataFrame"]{border:1px solid #273746;border-radius:14px;overflow:hidden}
[data-testid="stTextInput"] input,[data-testid="stSelectbox"] [data-baseweb="select"],
[data-testid="stTextArea"] textarea{
    border-radius:11px!important;background-color:#131f2d!important;
}
[data-testid="stExpander"]{background:#111b26!important;border-radius:12px!important}
[data-testid="stRadio"] div[role="radiogroup"][aria-label="Munkaterület"]{
    display:flex;gap:.5rem!important;flex-wrap:wrap;
    padding:.55rem;border-radius:16px;background:#111d29;border:1px solid #2a3c4b;
}
[data-testid="stRadio"] div[role="radiogroup"][aria-label="Munkaterület"] label{
    padding:.45rem .7rem;border-radius:10px;background:#172432;
}
.resell-topbar{
    display:flex;align-items:center;justify-content:space-between;
    gap:1rem;padding:13px 19px;margin-bottom:22px;
    background:rgba(17,28,41,.92);border:1px solid #2b3b49;
    border-radius:18px;box-shadow:0 6px 22px rgba(0,0,0,.15);
}
.resell-brand{font-size:1.05rem;font-weight:800;letter-spacing:-.03em;color:#edfbff}
.resell-brand span{color:#51d9b9}
.resell-top-meta{font-size:.77rem;color:#98b5c2}
.resell-hero{
    padding:28px 30px;margin-bottom:1.3rem;
    border-radius:22px;border:1px solid #285365;
    background:linear-gradient(125deg,rgba(34,94,98,.35),#142238 70%,#141c2d);
}
.resell-hero .eyebrow{font-size:.73rem;font-weight:760;letter-spacing:.17em;color:#76dbc9}
.resell-hero h1{font-size:2.35rem;line-height:1.2;letter-spacing:-.05em;margin:.3rem 0 .65rem;color:#f2fcff}
.resell-hero p{font-size:1rem;color:#b3c9d3;max-width:760px;margin:0}
.resell-bottomcap{
    padding:12px 16px;margin-top:1.3rem;background:#131e2b;
    border:1px solid #2b3b49;border-radius:16px;color:#9fb4c3;
    font-size:.81rem;
}
small,.stCaption{color:#a6bac8}
/* Dense single-user workspace, matching the approved product dashboard. */
section[data-testid="stSidebar"]{min-width:205px!important;max-width:205px!important}
[data-testid="stMainBlockContainer"],.block-container{padding:.7rem .8rem 3rem!important}
.private-chip{min-height:2.4rem;padding:.48rem .4rem}
[data-testid="stHorizontalBlock"]{gap:.55rem!important}
[data-testid="stVerticalBlockBorderWrapper"]{border-radius:13px!important}
[data-testid="stImage"] img{object-fit:contain;border-radius:9px}
div[data-testid="stRadio"] label{font-size:.86rem}
@media(max-width:900px){
  section[data-testid="stSidebar"]{min-width:0!important;max-width:none!important}
  [data-testid="stMainBlockContainer"],.block-container{padding:.7rem .55rem 3rem!important}
}
@media(max-width:800px){
    [data-testid="stMainBlockContainer"],.block-container{padding:1.2rem .8rem 5rem!important}
    .resell-hero{padding:22px 18px}
    .resell-hero h1{font-size:1.8rem}
    .resell-topbar{padding:12px;flex-wrap:wrap}
}

/* Personal dark workspace: calm graphite, teal highlights, dense data. */
:root{
  --resell-bg:#080f17;--resell-surface:#111c27;
  --resell-elevated:#16232e;--resell-line:#273946;
  --resell-text:#edf6f7;--resell-muted:#9caebc;
  --resell-accent:#31d7b3;
}
html,body,[data-testid="stApp"],[data-testid="stMain"]{
  background:#080f17!important;color:#edf6f7!important;
}
[data-testid="stMain"]{
  background:radial-gradient(ellipse 75% 15% at 55% 0%,
    rgba(21,124,115,.085),transparent 78%),#080f17!important;
}
[data-testid="stMainBlockContainer"],.block-container{
  max-width:1760px!important;
  padding:1.0rem 1.55rem 5rem!important;
}
section[data-testid="stSidebar"]{
  background:#0c151d!important;
  border-right:1px solid #21323c!important;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] label{
  border-radius:10px!important;padding:.35rem .5rem;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked){
  background:linear-gradient(90deg,rgba(42,205,171,.20),rgba(33,115,114,.11))!important;
  border-left:3px solid #30d5b2;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] label:hover{
  background:#192832!important;
}
[data-testid="stMetric"]{
  background:#121e29!important;border:1px solid #283b46!important;
  border-radius:13px!important;box-shadow:none!important;
}
[data-testid="stVerticalBlockBorderWrapper"]{
  background:#111b25!important;border:1px solid #2b3b46!important;
  border-radius:14px!important;box-shadow:none!important;
}
.stButton>button[kind="primary"]{
  background:#20cba7!important;border-color:#20cba7!important;
  color:#052b29!important;box-shadow:none!important;font-weight:720!important;
}
.stButton>button[kind="secondary"],[data-testid="stLinkButton"] a{
  background:#192631!important;border:1px solid #344752!important;
  color:#e2f4f5!important;
}
.stButton>button:hover,[data-testid="stLinkButton"] a:hover{
  transform:none!important;border-color:#36cfaf!important;
}
[data-testid="stDataFrame"]{
  background:#121c25!important;border:1px solid #2b3b46!important;
}
.resell-topbar{
  padding:10px 15px;margin-bottom:14px;
  border-radius:12px;background:#101b25;
  border:1px solid #293b46;box-shadow:none;
}
.resell-top-meta{font-size:.76rem;color:#94afae}
.private-heading{
  display:flex;align-items:flex-end;justify-content:space-between;
  margin:0 0 13px;
}
.private-heading h1{
  font-size:1.72rem;font-weight:800;letter-spacing:-.045em;
  color:#e6f7f5;margin:1px 0 4px;
}
.private-heading h1 span{color:#32d5b4}
.private-heading p{font-size:.84rem;color:#9bafbc;margin:0}
.private-overline{font-size:.67rem;letter-spacing:.19em;font-weight:800;color:#30d8b3}
.private-kicker{
  margin:0 0 14px;font-size:.79rem;color:#93b4b8;letter-spacing:.01em;
}
.private-kicker strong{color:#44e2ba}
.private-chip{
  border:1px solid #2c4450;background:#14232c;
  border-radius:10px;padding:.55rem .48rem;min-height:2.5rem;
  color:#d5e6e8;text-align:center;font-size:.77rem;
  white-space:nowrap;
}
.private-kpi{
  font-size:1.65rem;font-weight:800;letter-spacing:-.03em;
  color:#f1f9f7;line-height:1.4;
}
[data-testid="stCaptionContainer"]{line-height:1.42}
@media(max-width:1150px){
  .private-chip{white-space:normal;padding:.48rem}
  .private-kpi{font-size:1.37rem}
}
@media(max-width:800px){
  [data-testid="stMainBlockContainer"],.block-container{
    padding:.9rem .65rem 5rem!important;
  }
  .private-heading h1{font-size:1.35rem}
  .resell-topbar{flex-wrap:wrap}
}
</style>
"""
def render_theme():
    st.markdown(CSS,unsafe_allow_html=True)

def top_bar(version):
    safe=html.escape(str(version))
    st.markdown(
        '<div class="resell-topbar">'
        '<div class="resell-brand">↗ &nbsp; Resell <span>Agent</span> &nbsp; <small>privát</small></div>'
        '<div class="resell-top-meta">Market Intelligence &nbsp; · &nbsp; '
        '13 beszállító &nbsp; · &nbsp; Vinted + Jófogás &nbsp; · &nbsp; v'+safe+' &nbsp; · &nbsp; HUF</div>'
        '</div>',unsafe_allow_html=True)
