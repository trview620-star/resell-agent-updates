"""Demand-led supplier discovery, selection cards and post-ready package."""
from __future__ import annotations
from html import escape
from urllib.parse import quote,quote_plus
import os
import streamlit as st

from . import demand_workbench as demand, product_studio as studio, cloudflare_photos, hunter, shopping, supplier_links

def money(value):return (f'{int(value):,} Ft'.replace(',',' ') if value else '—')

def _capture():
    with st.expander('＋ Új termékkifejezés',expanded=not bool(demand.leads())):
        phrase=st.text_input('Milyen terméket keressek?',placeholder='Pontos márka, modell vagy EAN',key='studio_phrase')
        if phrase.strip():st.link_button('eBay Sold találatok megnyitása','https://www.ebay.de/sch/i.html?_nkw='+quote_plus(phrase.strip())+'&LH_Sold=1&LH_Complete=1')
        add_ebay=st.checkbox('Van kézzel ellenőrzött eBay Sold darabszámom is (opcionális)',key='studio_add_ebay')
        units=days=median=None;url='';checked=False
        if add_ebay:
            a,b,c=st.columns(3)
            with a:units=st.number_input('Ténylegesen eladott darab',1,100000,1,key='studio_units')
            with b:days=st.number_input('Vizsgált napok',1,365,30,key='studio_days')
            with c:median=st.number_input('eBay eladási medián (Ft)',0,100000000,0,step=500,key='studio_median')
            url=st.text_input('eBay Sold bizonyíték URL',key='studio_ebay_url')
            checked=st.checkbox('Ellenőriztem, hogy tényleges eladások, nem aktív hirdetések',key='studio_ebay_confirmed')
        if st.button('Termékkifejezés mentése',type='primary',width='stretch',key='studio_add_phrase'):
            try:
                if add_ebay and checked:
                    lead=demand.save_lead(phrase,int(units),int(days),int(median) or None,url,manually_verified=True)
                else:
                    lead=demand.save_lead(phrase,manually_verified=False)
                st.session_state['studio_lead']=int(lead['id']);st.success('Mentve. Egy keresés indítja a 13 boltot és a piaci diagnosztikákat.');st.rerun()
            except ValueError as e:st.error(str(e))
        st.caption('Az eBay tényleges eladási száma opcionális. Ha nincs megadva, ezt a jelet üresen hagyjuk, a többi forrást pedig automatikusan keressük.')

def _search(lead):
    key=os.getenv('SERPER_API_KEY','').strip() or st.session_state.get('studio_serper','').strip()
    if not key:key=st.text_input('Serper Shopping API-kulcs',type='password',key='studio_serper')
    remaining=shopping.MONTHLY_LIMIT-shopping.current_usage()
    a,b=st.columns([2,1])
    sales=(f"{lead['sold_units']} igazolt eBay-eladás / {lead['period_days']} nap" if lead['manually_verified'] and lead['sold_units'] else 'eBay eladási adat nincs megadva')
    a.caption(f"{lead['phrase']} · {sales} · 1 művelet = 5 keresés · {remaining}/{shopping.MONTHLY_LIMIT} havi keret")
    if b.button('Keresés a 13 boltban + piaci jelek',key='studio_search_'+str(lead['id']),disabled=not bool(key) or remaining<5,type='primary'):
        try:
            with st.spinner('Keresem a 13 boltot és a piaci diagnosztikákat…'):
                result=demand.scan_suppliers(lead['id'],key)
                diagnostics=studio.scan_market_diagnostics(lead['id'],key)
            if result.get('error'):st.warning(result['error'])
            else:st.success(f"{result['found']} elfogadott bolti találat · {diagnostics['found']} piaci forráskivonat")
            if diagnostics.get('errors'):st.info('Néhány diagnosztika most nem volt elérhető; a forráskártyán jelezzük.')
            st.rerun()
        except ValueError as e:st.error(str(e))
    return key

def _cards(rows):
    if not rows:
        st.markdown('<div class="studio-empty"><span>01 / DISCOVER</span><h3>Előbb rögzíts egy keresleti jelet</h3><p>A rendszer a ténylegesen eladott terméket keresi össze a 13 ellenőrzött bolt ajánlataival. Nincs automatikus, teljes bolti katalógus-hozzáférés.</p></div>',unsafe_allow_html=True)
        return
    st.markdown(f"### Lehetőségek <small style='color:#91a8b4'> · {len(rows)} valódi bolti találat</small>",unsafe_allow_html=True)
    st.caption('Rangsorolás: több piaci forrásból érkező egyezés, utána igazolt eBay-eladási tempó. A Google Shopping a beszerzést mutatja; az aktív hirdetés nem eladás.')
    diagnostics={int(x['lead']['id']):studio.market_diagnostics(x['lead']['id']) for x in rows}
    for start in range(0,len(rows),3):
        cols=st.columns(3,gap='medium')
        for col,row in zip(cols,rows[start:start+3]):
            with col,st.container(border=True):
                if row.get('thumbnail'):
                    try:st.image(row['thumbnail'],width='stretch');st.caption('Bolti katalóguskép · stock fotó')
                    except Exception:st.markdown('<div class="studio-placeholder">KATALÓGUSKÉP</div>',unsafe_allow_html=True)
                else:st.markdown('<div class="studio-placeholder">KÉP NINCS</div>',unsafe_allow_html=True)
                badge='✓ 4 napra ellenőrzött' if row['verified'] else 'Ár / készlet / szállítás ellenőrzendő'
                lead_id=int(row['lead']['id']);d=diagnostics[lead_id]
                sources=sum(1 for source in ('trends','vinted','jofogas','ebay_sold') if d['runs'].get(source) and d['runs'][source]['status']=='ok')
                sales=(f"{row['pace']:.1f} igazolt eBay Sold / 30 nap" if row['lead']['manually_verified'] and row['lead']['sold_units'] else 'eBay Sold adat nélkül')
                st.caption(f"{row['lead']['phrase']} · {sources}/4 extra forrás vizsgálva · {sales}")
                st.markdown('**'+escape(row['title'])+'**')
                st.write(money(row['price_huf'])+' · '+row['supplier'])
                st.caption(row['confidence']+' · '+badge)
                target,direct=supplier_links.navigable(row['url'],row['title'],row['merchant'])
                a,b=st.columns(2)
                a.link_button('Bolti ajánlat ↗',target,width='stretch')
                label='Kiválasztva ✓' if row['selected'] else '＋ Hozzáadás'
                if b.button(label,key=f"studio_select_{row['lead']['id']}_{row['id']}",type='primary' if row['selected'] else 'secondary',width='stretch'):
                    studio.toggle(row['lead']['id'],row['id'],not row['selected']);st.rerun()
                if row['verified']:
                    best=row['verified'][0]
                    st.success('Igazolt ajánlat: '+money(best['total_huf'])+' · max. 4 munkanap')
                with st.expander('Készlet és Vácra szállítás ellenőrzése'):
                    if not direct:st.caption('A Shopping-linket megnyitva másold be a bolt közvetlen termékoldalát.')
                    with st.form(f"studio_verify_{row['lead']['id']}_{row['id']}"):
                        url=st.text_input('Közvetlen termékoldal',value=row['url'] if direct else '')
                        v1,v2,v3=st.columns(3)
                        with v1:price=st.number_input('Ellenőrzött termékár (Ft)',1,100000000,int(row['price_huf']),step=100)
                        with v2:shipping=st.number_input('Szállítás (Ft)',0,10000000,0,step=100)
                        with v3:stock=st.selectbox('Készlet',['unknown','available','unavailable'],format_func=lambda x:{'unknown':'Nem ellenőrzött','available':'Rendelhető','unavailable':'Nem rendelhető'}[x])
                        p1,p2,p3=st.columns(3)
                        with p1:postal=st.text_input('Irányítószám',value='2600',max_chars=4)
                        with p2:method=st.text_input('Szállítási mód',placeholder='Házhozszállítás')
                        with p3:days=st.number_input('Vállalt munkanap',0,60,4)
                        guaranteed=st.checkbox('A bolt erre a címre ténylegesen vállalja a határidőt')
                        exact=st.checkbox('Ellenőriztem a pontos modellt / EAN-t')
                        evidence=st.text_input('Hol láttad az árat, készletet és kézbesítési ígéretet?')
                        saved=st.form_submit_button('Ellenőrzés mentése')
                    if saved:
                        try:
                            demand.save_supplier_check(row['lead']['id'],row['id'],url=url,price_huf=int(price),shipping_huf=int(shipping),stock_status=stock,postcode=postal,shipping_method=method,max_workdays=int(days),delivery_guaranteed=guaranteed,exact_match_confirmed=exact,evidence_note=evidence)
                            st.success('Igazolás mentve; az ajánlat része lesz az ártörténetnek.');st.rerun()
                        except ValueError as e:st.error(str(e))

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
                sales=(f"eBay Sold: {row['sold_units']} / {row['period_days']} nap ({row['pace']:.1f} / 30 nap)" if row['manually_verified'] and row['sold_units'] else 'eBay Sold darabszám nincs megadva')
                st.caption(f"{row['merchant']} · {sales}")
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
                    with a:reference=st.number_input('Hasonló Vinted-hirdetések megfigyelt ára (Ft; opcionális)',0,100000000,int(row['vinted_reference_huf'] or 0),step=500)
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
    st.caption('Több piaci jelből rangsorolt termékek · 13 bolt · képes kártyák · leírás és posztcsomag')
    st.info('Az eBay Sold csak egy jel. A keresés egyetlen indításával a Google Trends, Vinted, Jófogás és eBay webes találatokat is lekérjük, miközben a 13 boltot Shoppingon vizsgáljuk. Külön diagnosztikai adatot nem kell begépelned.')
    _capture()
    leads=sorted(demand.leads(),key=lambda x:studio.priority_key(x['id']))
    if leads:
        current=st.session_state.get('studio_lead')
        ids=[int(x['id']) for x in leads]
        if current not in ids:current=ids[0]
        current=st.selectbox('Termék / keresleti jel',ids,index=ids.index(current),format_func=lambda i:next(x['phrase'] for x in leads if int(x['id'])==i),key='studio_current_lead')
        lead=next(x for x in leads if int(x['id'])==int(current));_search(lead)
    st.markdown('<div class="studio-tabs">',unsafe_allow_html=True)
    discovery,diagnostics,posting=st.tabs(['◈  TERMÉKEK','⌕  PIACI DIAGNOSZTIKA','✦  POSZTOLÁSI SOR'])
    with discovery:_cards(studio.candidates())
    with diagnostics:
        if leads:_market_diagnostics(lead)
        else:st.info('Adj meg egy terméknevet, és a diagnosztikákhoz rögzítheted a több forrásból származó piaci jeleket.')
    with posting:_queue()
    st.markdown('</div>',unsafe_allow_html=True)
    with st.expander('Korábbi képprompt és képsorrend'):
        st.markdown('''**A sorrend:** 1. fő kép ¾ elölnézetből · 2. szemből · 3. oldalnézet · 4. hátulról. Mindegyik külön fájl, nem montázs.''')
        st.code(cloudflare_photos.prompt_for('front_three_quarter','[kiválasztott terméknév]'),language='text')
        st.caption('Ez az alkalmazásban ténylegesen használt alapprompt. Az AI-kép csak illusztráció; a modell eltorzíthat logót, feliratot, tartozékot vagy nem látható termékrészt, ezért a kimenet nem igazolja a termék állapotát, és nem saját fotó.')

def _market_diagnostics(lead):
    data=studio.market_diagnostics(lead['id']);links=studio.diagnostic_links(lead['phrase'])
    st.markdown('### Keresési diagnosztikák')
    st.caption('A keresleti és versenyképet együtt nézzük. Az aktív hirdetés kínálati adat, nem bizonyított eladás.')
    runs=data['runs'];results=data['results']
    def state(source):
        row=runs.get(source)
        if not row:return 'Még nincs automatikus keresés'
        if row['status']=='error':return 'Most nem érhető el'
        return f"{row['result_count']} Google-indexelt találat · {row['checked_at'][:16]}"
    trends_value=state('trends')+' · a találat nem Google Trends index'
    vinted_value=state('vinted')+' · a snippetek nem teljes aktív hirdetésszámok'
    jofogas_value=state('jofogas')+' · a snippetek nem teljes aktív hirdetésszámok'
    if lead['manually_verified'] and lead['sold_units']:
        sold_rate=30*int(lead['sold_units'])/max(1,int(lead['period_days']))
        ebay_value=f"Igazolt: {lead['sold_units']} / {lead['period_days']} nap ({sold_rate:.1f} / 30 nap) · webes kivonat: {state('ebay_sold')}"
    else:ebay_value='Nincs megadott eladásszám · webes kivonat: '+state('ebay_sold')
    history=data['price_moves']
    history_value=(f"{history[0]['supplier']}: {money(history[0]['old'])} → {money(history[0]['new'])}" if history else (f"{data['history_count']} ellenőrzés mentve; ármozgáshoz több azonos termékkörű mérés kell." if data['history_count'] else 'Még nincs mentett ártörténet'))
    cards=[
      ('Google Trends','Keresési érdeklődés és irány',trends_value,'Google Trends'),
      ('Google Shopping','13 bolt ajánlatai',f"{data['shopping_count']} találat · {len(data['shopping_suppliers'])} bolt · legalacsonyabb keresési ár {money(data['shopping_lowest'])}",'Google Shopping'),
      ('Vinted','Google-indexelt hirdetés-találatok',vinted_value,'Vinted'),
      ('Jófogás','Google-indexelt kínálati találatok',jofogas_value,'Jófogás'),
      ('eBay Sold','Eladási bizonyíték + külön webes keresés',ebay_value,'eBay Sold'),
      ('Ártörténet','Korábban kézzel ellenőrzött árak',history_value,'Ártörténet'),
    ]
    for start in (0,3):
        cols=st.columns(3,gap='medium')
        for col,(title,subtitle,value,source) in zip(cols,cards[start:start+3]):
            with col,st.container(border=True):
                st.markdown('**'+title+'**');st.caption(subtitle);st.markdown('### '+value)
                if source!='Ártörténet':st.link_button('Forrás megnyitása ↗',links[source],width='stretch')
                else:
                    for move in history[:3]:st.caption(f"{move['supplier']} · {money(move['old'])} → {money(move['new'])} · {move['checked_at'][:10]}")
    st.caption(f"A termékkifejezés legutóbb mentve: {lead['checked_at'][:10]}. Google Shopping-találatok: {data['shopping_count']} · bolt: {', '.join(data['shopping_suppliers']) or 'még nincs'}. A négy extra keresést a 13 boltos keresés automatikusan indítja.")
    source_labels={'trends':'Google Trends','vinted':'Vinted','jofogas':'Jófogás','ebay_sold':'eBay Sold'}
    st.markdown('#### Automatikusan keresett találatok')
    st.caption('Neked nem kell külön kulcsszót, darabszámot vagy árat beírnod; a rendszer automatikusan keres a megadott terméknévvel.')
    for start in range(0,4,2):
        cols=st.columns(2,gap='medium')
        for col,source in zip(cols,('trends','vinted','jofogas','ebay_sold')[start:start+2]):
            run=data['runs'].get(source);items=data['results'].get(source,[])
            with col,st.container(border=True):
                st.markdown('**'+source_labels[source]+'**')
                if run and run['status']=='error':st.warning('A kereső most nem érte el ezt a forrást: '+run['error'])
                elif run:st.caption(f"Google által indexelt szöveges találat: {run['result_count']} · frissítve {run['checked_at'][:16]}")
                else:st.caption('Még nem futott le. A termékkeresés gomb mind a négy forrást elindítja.')
                for item in items[:3]:
                    st.link_button((item['title'] or item['url'])[:100]+' ↗',item['url'],width='stretch')
                    if item['snippet']:st.caption(item['snippet'][:240])
                if source=='trends':st.link_button('Google Trends grafikon megnyitása ↗',links['Google Trends'],width='stretch')
                if source=='trends':
                    trend_query=quote(lead['phrase'],safe='')
                    st.iframe('https://trends.google.com/trends/embed/explore/TIMESERIES?date=today%2012-m&geo=HU&q='+trend_query+'&hl=hu',height=250)
                if source=='ebay_sold':st.caption('Az eBay keresési kivonata önmagában nem igazolt eladásszám. A hivatalos sold-adat API-ja korlátozott hozzáférésű.')
                if source in ('vinted','jofogas'):st.caption('Az indexelt webes találatok nem teljes piactéri készlet és nem bizonyított eladások.')
