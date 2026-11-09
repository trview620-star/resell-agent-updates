"""Demand-led supplier discovery, selection cards and post-ready package."""
from __future__ import annotations
from html import escape
from urllib.parse import quote_plus
import os
import streamlit as st

from . import demand_workbench as demand, product_studio as studio, cloudflare_photos, hunter, supplier_links

def money(value):return (f'{int(value):,} Ft'.replace(',',' ') if value else '—')

def _capture():
    with st.expander('＋ Új keresleti jel · eBay Sold',expanded=not bool(demand.leads())):
        phrase=st.text_input('Mit kerestek / vettek meg?',placeholder='Pontos márka, termékmodell vagy EAN',key='studio_phrase')
        if phrase.strip():st.link_button('eBay Sold keresés', 'https://www.ebay.de/sch/i.html?_nkw='+quote_plus(phrase.strip())+'&LH_Sold=1&LH_Complete=1')
        with st.form('studio_demand_form'):
            a,b,c=st.columns(3)
            with a:units=st.number_input('Ténylegesen eladott darab',1,100000,1)
            with b:days=st.number_input('Vizsgált napok',1,365,30)
            with c:median=st.number_input('eBay eladási medián (Ft)',0,100000000,0,step=500)
            url=st.text_input('eBay Sold bizonyíték URL')
            checked=st.checkbox('Ellenőriztem: tényleges eladások, nem aktív hirdetések')
            go=st.form_submit_button('Keresleti jel mentése',type='primary',width='stretch')
        if go:
            try:
                lead=demand.save_lead(phrase,int(units),int(days),int(median) or None,url,manually_verified=checked)
                st.session_state['studio_lead']=int(lead['id']);st.success('Mentve. Indítsd el a 13 boltos keresést.');st.rerun()
            except ValueError as e:st.error(str(e))
        st.caption('Az eBay sold adatot kézzel, az eBay találatok ellenőrzése után rögzítjük. Az API nem érhető el általánosan.')

def _search(lead):
    key=os.getenv('SERPER_API_KEY','').strip() or st.session_state.get('studio_serper','').strip()
    if not key:key=st.text_input('Serper Shopping API-kulcs',type='password',key='studio_serper')
    a,b=st.columns([2,1])
    a.caption(f"{lead['phrase']} · {lead['sold_units']} eladás / {lead['period_days']} nap")
    if b.button('Keresés a 13 boltban',key='studio_search_'+str(lead['id']),disabled=not bool(key),type='primary'):
        try:
            result=demand.scan_suppliers(lead['id'],key)
            if result.get('error'):st.warning(result['error'])
            else:st.success(f"{result['found']} elfogadott bolti találat")
            st.rerun()
        except ValueError as e:st.error(str(e))

def _cards(rows):
    if not rows:
        st.markdown('<div class="studio-empty"><span>01 / DISCOVER</span><h3>Előbb rögzíts egy keresleti jelet</h3><p>A rendszer a ténylegesen eladott terméket keresi össze a 13 ellenőrzött bolt ajánlataival. Nincs automatikus, teljes bolti katalógus-hozzáférés.</p></div>',unsafe_allow_html=True)
        return
    st.markdown(f"### Lehetőségek <small style='color:#91a8b4'> · {len(rows)} valódi bolti találat</small>",unsafe_allow_html=True)
    for start in range(0,len(rows),3):
        cols=st.columns(3,gap='medium')
        for col,row in zip(cols,rows[start:start+3]):
            with col,st.container(border=True):
                if row.get('thumbnail'):
                    try:st.image(row['thumbnail'],width='stretch');st.caption('Bolti katalóguskép · stock fotó')
                    except Exception:st.markdown('<div class="studio-placeholder">KATALÓGUSKÉP</div>',unsafe_allow_html=True)
                else:st.markdown('<div class="studio-placeholder">KÉP NINCS</div>',unsafe_allow_html=True)
                badge='✓ 4 napra ellenőrzött' if row['verified'] else 'Ár / készlet / szállítás ellenőrzendő'
                st.caption(f"{row['lead']['phrase']} · {row['pace']:.1f} eBay eladás / 30 nap")
                st.markdown('**'+escape(row['title'])+'**')
                st.write(money(row['price_huf'])+' · '+row['supplier'])
                st.caption(row['confidence']+' · '+badge)
                target,direct=supplier_links.navigable(row['url'],row['title'],row['merchant'])
                a,b=st.columns(2)
                a.link_button('Bolti ajánlat ↗',target,width='stretch')
                label='Kiválasztva ✓' if row['selected'] else '＋ Hozzáadás'
                if b.button(label,key=f"studio_select_{row['lead']['id']}_{row['id']}",type='primary' if row['selected'] else 'secondary',width='stretch'):
                    studio.toggle(row['lead']['id'],row['id'],not row['selected']);st.rerun()

def _photo_settings():
    with st.expander('AI-képgenerálás beállítása',expanded=False):
        account=st.text_input('Cloudflare Account ID',type='password',key='studio_cf_account')
        token=st.text_input('Workers AI token',type='password',key='studio_cf_token')
        model=st.selectbox('Képgeneráló modell',list(__import__('agent.cloudflare_photos',fromlist=['MODELS']).MODELS),key='studio_cf_model')
        st.caption('A kulcsok csak a jelenlegi böngésző-munkamenetben élnek. A négy kép külön kérés, a szolgáltatói kvótából fogyaszt.')
    return account,token,model

def _queue():
    rows=studio.selected()
    st.markdown('<div class="studio-eyebrow">02 · POSTING STUDIO</div>',unsafe_allow_html=True)
    st.title('Kiválasztott termékek')
    st.caption('A legerősebb, igazolt keresleti tempó kerül előre. A kártyán szerkeszd a leírást, az árat és készíts képcsomagot.')
    if not rows:st.info('A katalógusból a ＋ Hozzáadás gombbal tehetsz terméket a posztolási sorba.');return
    account,token,model=_photo_settings()
    for order,row in enumerate(rows,1):
        with st.container(border=True):
            pic,details=st.columns([1,2.2],gap='large')
            with pic:
                if row.get('thumbnail'):
                    try:st.image(row['thumbnail'],width='stretch')
                    except Exception:st.caption('Katalóguskép nem elérhető')
                st.caption('Beszállítói katalóguskép · stock fotó')
            with details:
                st.markdown(f"### {order:02d} · {escape(row['title'])}")
                st.caption(f"{row['merchant']} · eBay Sold kereslet: {row['sold_units']} / {row['period_days']} nap ({row['pace']:.1f} / 30 nap)")
                offer=row['verified_offer']
                if offer:
                    st.success(f"Legalacsonyabb friss, ellenőrzött ajánlat: {offer['supplier']} · {money(offer['total_huf'])} szállítással · vállalt max. 4 munkanap")
                else:st.warning('Nincs friss, pontos modellre, készletre és ≤4 munkanapos kézbesítésre igazolt ajánlat.')
                copy_key=f"studio_copy_text_{row['lead_id']}_{row['source_result_id']}"
                if copy_key not in st.session_state:st.session_state[copy_key]=row['description']
                if st.button('✦ Magyar leírásjavaslat készítése',key=f"studio_ai_copy_{row['source_result_id']}",disabled=not(account.strip() and token.strip())):
                    try:
                        with st.spinner('Rövid, magyar szöveg készül…'):
                            suggestion=hunter.ai_description({'title':row['title'],'brand':'','model':'','category':'','condition_text':'Unknown / verify'},account,token)
                        st.session_state[copy_key]=suggestion;st.rerun()
                    except ValueError as e:st.error(str(e))
                with st.form(f"studio_copy_{row['lead_id']}_{row['source_result_id']}"):
                    a,b=st.columns(2)
                    with a:reference=st.number_input('Hasonló Vinted-hirdetések megfigyelt ára (Ft)',0,100000000,int(row['vinted_reference_huf'] or 0),step=500)
                    landed=offer['total_huf'] if offer else None
                    suggested=studio.suggested_price(reference,landed)
                    with b:st.metric('Irányár',money(suggested),help='max(megfigyelt Vinted-ár, igazolt beszerzés+szállítás+4 900 Ft). A megfigyelt ár kézzel megadott adat.')
                    description=st.text_area('Posztszöveg · szerkeszthető',height=155,key=copy_key)
                    if st.form_submit_button('Szöveg és irányár mentése'):
                        try:studio.save_posting(row['lead_id'],row['source_result_id'],reference,description);st.success('Mentve');st.rerun()
                        except ValueError as e:st.error(str(e))
                images=row['images']
                if len(images)<4:
                    disabled=not (account.strip() and token.strip() and row.get('thumbnail'))
                    if st.button('✦ Négy AI-illusztráció létrehozása',key=f"studio_generate_{row['source_result_id']}",type='primary',disabled=disabled):
                        try:
                            with st.spinner('A négy külön képkocka készül…'):
                                studio.generate_pack(row['lead_id'],row['source_result_id'],account,token,model)
                            st.rerun()
                        except (ValueError,OSError) as e:st.error(str(e))
                    if not account or not token:st.caption('Add meg a Cloudflare hozzáférést a fenti AI-képgenerálás beállítása résznél.')
                if images:
                    cols=st.columns(4)
                    for col,image in zip(cols,images):
                        with col:st.image(image['bytes'],width='stretch');st.caption(f"{image['slot']}/4 · AI-illusztráció")
    if rows:
        st.download_button('↓ Posztcsomag letöltése · sorrend + szöveg + képek',studio.posting_zip(),file_name='resell_posztcsomag.zip',mime='application/zip',type='primary',width='stretch')
        st.caption('A csomag a legerősebb eBay-eladási tempójú termékkel kezdődik. A Vintedre kézzel posztold; automatikus közzététel nincs.')

def render():
    studio.initialize()
    st.markdown('<div class="studio-eyebrow">RESELL AGENT · PRODUCT TO POST</div>',unsafe_allow_html=True)
    st.title('A keresletből kész poszt lesz.')
    st.caption('13 bolt · valódi eladási jel · képes termékkártyák · ellenőrizhető irányár · posztolási sorrend')
    st.info('A keresés egy ellenőrzött eBay-termékhez kér Shopping-találatokat a 13 boltból; ez nem jelenti mind a 13 webshop teljes katalógusának automatikus letöltését.')
    _capture()
    leads=demand.leads()
    if leads:
        current=st.session_state.get('studio_lead')
        ids=[int(x['id']) for x in leads]
        if current not in ids:current=ids[0]
        current=st.selectbox('Keresleti jel',ids,index=ids.index(current),format_func=lambda i:next(x['phrase'] for x in leads if int(x['id'])==i),key='studio_current_lead')
        lead=next(x for x in leads if int(x['id'])==int(current));_search(lead)
    st.markdown('<div class="studio-tabs">',unsafe_allow_html=True)
    discovery,posting=st.tabs(['◈  TERMÉKEK','✦  POSZTOLÁSI SOR'])
    with discovery:_cards(studio.candidates())
    with posting:_queue()
    st.markdown('</div>',unsafe_allow_html=True)
    with st.expander('Korábbi képprompt és képsorrend'):
        st.markdown('''**A sorrend:** 1. fő kép ¾ elölnézetből · 2. szemből · 3. oldalnézet · 4. hátulról. Mindegyik külön fájl, nem montázs.''')
        st.code(cloudflare_photos.prompt_for('front_three_quarter','[kiválasztott terméknév]'),language='text')
        st.caption('Ez az alkalmazásban ténylegesen használt alapprompt. Az AI-kép csak illusztráció; a modell eltorzíthat logót, feliratot, tartozékot vagy nem látható termékrészt, ezért a kimenet nem igazolja a termék állapotát, és nem saját fotó.')
