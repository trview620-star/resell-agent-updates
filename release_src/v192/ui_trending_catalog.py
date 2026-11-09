"""Minimal grid of real product offers from the thirteen approved retailers."""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime
from html import escape
import re
import unicodedata
from urllib.parse import quote_plus
import os
import streamlit as st

from . import hunter, market_intelligence as intelligence, private_research, shopping, supplier_links

def search_topics(month=None):
    month=month or datetime.now().month
    seasonal=(month in (10,11,12))
    if seasonal:
        return [
          ('Karácsonyi ajándék','LEGO adventi naptár 2026'),
          ('Karácsonyi ajándék','családi társasjáték karácsonyra'),
          ('Karácsonyi dekoráció','LED karácsonyi fényfüzér'),
          ('Gamer ajándék','Nintendo Switch játék ajándék'),
          ('Gamer ajándék','vezeték nélküli gamer fejhallgató'),
          ('Kreatív ajándék','LEGO Botanicals'),
          ('Háztartási ajándék','forrólevegős sütő air fryer'),
          ('Háztartási ajándék','robotporszívó'),
        ]
    return [
      ('Kreatív ajándék','LEGO Botanicals'),
      ('Családi program','népszerű családi társasjáték'),
      ('Gamer kiegészítő','vezeték nélküli kontroller'),
      ('Audio','Bluetooth fejhallgató'),
      ('Háztartás','forrólevegős sütő air fryer'),
      ('Háztartás','robotporszívó'),
    ]

def group_offers(offers):
    """Deduplicate real supplier results into product cards."""
    groups={}
    for offer in offers:
        if not private_research.offer_matches_scope(offer):continue
        title=' '.join(str(offer.get('title') or '').split())
        if not title:continue
        code=shopping.model_code_from_phrase(title)
        normalized=unicodedata.normalize('NFKD',title.casefold())
        normalized=''.join(c for c in normalized if not unicodedata.combining(c))
        tokens=set(re.findall(r'[a-z0-9]{2,}',normalized))
        key=('model',code.casefold()) if code else ('title',' '.join(sorted(tokens)))
        item=groups.setdefault(key,{'title':title,'offers':[],'thumbnail':''})
        item['offers'].append(offer)
        if not item['thumbnail'] and offer.get('thumbnail'):item['thumbnail']=offer['thumbnail']
    output=[]
    for item in groups.values():
        item['offers'].sort(key=lambda x:(int(x.get('price_huf') or 10**12),
                                         str(x.get('merchant') or '').casefold()))
        item['best']=item['offers'][0]
        item['retailers']=sorted({private_research.supplier_name(x) for x in item['offers'] if private_research.supplier_name(x)})
        output.append(item)
    return sorted(output,key=lambda x:(-len(x['retailers']),int(x['best'].get('price_huf') or 10**12),x['title'].casefold()))

def _money(value):
    return f"{int(value):,} Ft".replace(',',' ') if value else 'Ár nincs'

def _api_key():
    if 'trend_catalog_key' not in st.session_state:
        st.session_state['trend_catalog_key']=os.getenv('SERPER_API_KEY','').strip()
    return st.text_input('Serper API-kulcs',type='password',key='trend_catalog_key',
                         placeholder='Serper API-kulcs megadása')

def _load_topics(key,topics):
    reports=[]
    for category,phrase in topics:
        if shopping.current_usage()>=shopping.MONTHLY_LIMIT:
            reports.append({'phrase':phrase,'error':'A havi keresési keret elfogyott.'});break
        result=intelligence.scan_keyword(key,phrase,'Szezonális keresleti ötletek · '+category)
        reports.append(result)
    st.session_state['trend_catalog_last_run']=reports

def render():
    intelligence.initialize()
    hunter.initialize()
    st.markdown('<div class="trend-eyebrow">RESELL AGENT · TRENDING PICKS</div>',unsafe_allow_html=True)
    st.title('Most keresett termékötletek')
    st.caption('Szezonális témákból élő termékkártyák a 13 jóváhagyott boltból.')
    st.info('A lista a mostani szezonhoz illő keresési témákból indul. A Google Trends link a keresési érdeklődést mutatja; a kártyák az aktuális bolti Shopping-találatok.')
    topics=search_topics()
    key=_api_key()
    used=shopping.current_usage()
    left,right=st.columns([2,1])
    left.caption(f'{len(topics)} aktuális keresési téma · {used}/{shopping.MONTHLY_LIMIT} havi keresés')
    if right.button('Friss termékek keresése',type='primary',disabled=not bool(key),width='stretch'):
        with st.spinner('Keresem a bolti termékeket és képeket…'):
            _load_topics(key,topics)
        st.rerun()
    if not key:st.info('A termékkereséshez Serper API-kulcs szükséges. Megadás után nyomd meg a „Friss termékek keresése” gombot.')
    st.caption('A képek bolti katalógusfotók. A Google Trends link minden kártyán az adott terméktémára nyílik meg.')
    reports=st.session_state.get('trend_catalog_last_run',[])
    if reports:
        errors=[r for r in reports if r.get('error')]
        successes=[r for r in reports if not r.get('error')]
        st.caption(f"Legutóbbi frissítés: {len(successes)} téma lefutott"+
                   (f" · {len(errors)} nem volt elérhető" if errors else ''))
    products=[]
    for category,phrase in topics:
        offers=intelligence.offers_for(phrase,80)
        for product in group_offers(offers):
            product['category']=category;product['phrase']=phrase
            products.append(product)
    if not products:
        st.markdown('<div class="trend-empty"><span>01 / PRODUCT RADAR</span><h3>Még nincs friss bolti találat</h3><p>Indítsd el a keresést, és a kártyákon megjelennek a 13 boltból talált termékek, képekkel és árakkal.</p></div>',unsafe_allow_html=True)
        return
    st.markdown(f"### Termékek <small style='color:#91a8b4'> · {len(products)} bolti termék</small>",unsafe_allow_html=True)
    for start in range(0,min(len(products),36),3):
        cols=st.columns(3,gap='medium')
        for col,item in zip(cols,products[start:start+3]):
            with col,st.container(border=True):
                if item['thumbnail']:
                    try:st.image(item['thumbnail'],width='stretch')
                    except Exception:st.markdown('<div class="trend-placeholder">KATALÓGUSKÉP</div>',unsafe_allow_html=True)
                else:st.markdown('<div class="trend-placeholder">KÉP NINCS</div>',unsafe_allow_html=True)
                st.caption(item['category']+' · '+str(len(item['retailers']))+' boltban található')
                st.markdown('**'+escape(item['title'])+'**')
                best=item['best'];supplier=private_research.supplier_name(best) or str(best.get('merchant') or 'Bolt')
                st.markdown('### '+_money(best.get('price_huf')))
                st.caption('Legolcsóbb találat: '+supplier)
                target,direct=supplier_links.navigable(best.get('url'),best.get('title'),best.get('merchant'))
                st.link_button('Termék megnyitása ↗',target,width='stretch')
                trends='https://trends.google.com/trends/explore?geo=HU&q='+quote_plus(item['phrase'])
                st.link_button('Google Trends · '+item['phrase'],trends,width='stretch')
    if len(products)>36:st.caption('A lista első 36 terméke látható; a keresési témák között több oldalról frissíthetsz.')
