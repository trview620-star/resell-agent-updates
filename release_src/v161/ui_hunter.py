"""Resell Agent visual product hunter and on-site workflow.

Shopping leads are not completed-sale comparables, not product photographs,
and never proof of supplier stock. All actions stay inside this dashboard.
"""
from __future__ import annotations

import json
import os
import re
from urllib.parse import urlsplit

import streamlit as st
from . import db, hunter, shopping, free_photo_import, cloudflare_photos, auto_stock_photo
from .publisher import MODES


STYLE=r"""
<style>
:root {color-scheme:dark}
section.main {background:radial-gradient(ellipse at 90% -15%,rgba(57,97,135,.14),transparent 48%),#0d121c}
.block-container{max-width:1500px;padding-top:1.35rem;padding-bottom:5rem}
section[data-testid="stSidebar"]{background:#111a27!important;border-right:1px solid rgba(255,255,255,.07)}
[data-testid="stSidebar"] [data-testid="stRadio"] label{font-weight:550}
[data-testid="stMetric"]{background:#151f2e;border:1px solid #263244;border-radius:16px;padding:18px}
[data-testid="stMetricLabel"]{color:#a7bacb}
[data-testid="stMetricValue"]{color:#f0f7ff}
div[data-testid="stVerticalBlockBorderWrapper"]{border-color:#2b3848;border-radius:16px}
.stButton>button[kind="primary"], .stFormSubmitButton>button[kind="primary"]{
  background:linear-gradient(115deg,#38c5a7,#198bbf)!important;
  border:none!important;color:#091722!important;font-weight:750!important;
  border-radius:11px!important;
}
.stButton>button{border-radius:11px}
[data-testid="stTabs"] button{font-weight:650}
.hunter-hero{
  border:1px solid #244352;
  border-radius:21px;
  background:linear-gradient(110deg,#132734,#111e30 68%,#182a36);
  padding:27px 30px;margin:0 0 20px;
}
.hunter-hero h1{color:#f0f9ff;font-size:2.15rem;letter-spacing:-.04em;margin:0}
.hunter-hero p{color:#b0c6d2;max-width:700px;font-size:1.02rem;margin:8px 0 0}
.hunter-pill{
  display:inline-block;background:#193a3d;color:#8ae1cc;border:1px solid #2a6466;
  border-radius:999px;padding:4px 11px;font-size:.74rem;font-weight:650;margin-bottom:13px
}
.hunter-tile{margin:0 0 12px}
.hunter-muted{color:#9daebf;font-size:.83rem}
</style>
"""


def money(value):
    return f'{int(value or 0):,} Ft'.replace(',',' ')


def credentials():
    serper=os.getenv('SERPER_API_KEY','').strip()
    cloud_id=os.getenv('CLOUDFLARE_ACCOUNT_ID','').strip()
    cloud_token=os.getenv('CLOUDFLARE_API_TOKEN','').strip()
    if not serper:
        serper=st.session_state.get('hunter_serper_key','') or st.session_state.get('serper_shopping_api_key','')
    if not cloud_id:
        cloud_id=st.session_state.get('hunter_cloud_id','') or st.session_state.get('cf_ai_account_id','')
    if not cloud_token:
        cloud_token=st.session_state.get('hunter_cloud_token','') or st.session_state.get('cf_ai_token','')
    return serper,cloud_id,cloud_token


def prepare_ids(ids,marketplaces,*,cloud_id='',cloud_token='',use_ai=True):
    done=[];errors=[]
    unique=list(dict.fromkeys(ids))
    if len(unique)>25:raise ValueError('Egy körben legfeljebb 25 termék választható.')
    for identifier in unique:
        try:
            result=hunter.prepare(identifier,marketplaces,account=cloud_id,
                                  token=cloud_token,use_ai=use_ai)
            done.append(result)
        except (ValueError,RuntimeError) as e:
            errors.append(f'#{identifier}: {e}')
    return done,errors


def _show_badges(row):
    labels=[]
    if row['status']=='selected':labels.append('Kiválasztva')
    if row['status']=='prepared':labels.append('Piszkozatok készen')
    if row['status']=='new':labels.append('Új találat')
    return ' · '.join(labels)


def _cards(items, markets, cloud_id,cloud_token, use_ai, page_size=12):
    max_page=max(1,(len(items)+page_size-1)//page_size)
    page=st.number_input('Oldal',min_value=1,max_value=max_page,value=1,step=1,
                         key='hunter_gallery_page')
    visible=items[(page-1)*page_size:page*page_size]
    for offset in range(0,len(visible),3):
        cols=st.columns(3,gap='medium')
        for col,row in zip(cols,visible[offset:offset+3]):
            with col:
                with st.container(border=True):
                    if row.get('thumbnail'):
                        try:st.image(row['thumbnail'],width=215)
                        except Exception:st.caption('Nincs elérhető előnézeti kép')
                    else:
                        st.caption('📦 Kép nem érhető el')
                    st.write('**'+row['title'][:115]+'**')
                    st.caption(row['merchant']+' · '+row['topic'])
                    st.markdown('### '+money(row['price_huf']))
                    st.caption('Beszerzési találat · készlet és szállítás ellenőrizendő')
                    st.caption(_show_badges(row))
                    st.markdown('[Beszállítói találat]('+row['url']+')')
                    if row['status']=='new':
                        if st.button('Kiválasztom → előkészítés',key='hunt_choose_'+str(row['id']),
                                     use_container_width=True,type='primary'):
                            done,errors=prepare_ids([row['id']],markets,cloud_id=cloud_id,
                                                    cloud_token=cloud_token,use_ai=use_ai)
                            if done:
                                st.success('Piszkozatok előkészítve. Megnyithatod a „Kiválasztottak” fület.')
                            if errors:st.error('; '.join(errors))
                            st.rerun()
                    elif row['status'] in ('selected','prepared'):
                        st.caption('✓ Elmentve a termékek közé')
    if len(items)>page_size:
        st.caption(f'{len(items)} találat · {page}/{max_page}. oldal')


def _feed_tab(serper,cloud_id,cloud_token,markets,use_ai):
    st.subheader('Termékek keresése')
    a,b,c,d=st.columns([1.2,1.1,1.1,1.4],gap='small')
    topic=a.selectbox('Témakör',list(hunter.TOPICS),key='hunter_topic')
    count=b.selectbox('Keresések száma',[3,6,9],index=1,key='hunter_search_count',
                      help='Egy keresés általában több terméket hoz. 6 keresés kb. 100 vagy több találatot is adhat.')
    max_price=c.selectbox('Maximum beszerzési ár',[10000,20000,50000,100000,250000,1000000],
        index=2,format_func=money,key='hunter_max_price')
    phrase=d.text_input('Egyedi kulcsszó (opcionális)',key='hunter_custom_phrase',
        placeholder='pl. LEGO 42154')
    if st.button('Új termékeket keresek',type='primary',disabled=not bool(serper),
                 key='hunter_run_search'):
        with st.spinner(f'{count} különálló magyar Shopping-keresés fut...'):
            try:
                result=hunter.scan(serper,topic,count,phrase)
                st.session_state['hunter_last_scan']=result
                st.toast(f'{result["offers"]} ajánlat feldolgozva',icon='✅')
            except ValueError as error:st.error(str(error))
    if not serper:
        st.info('A kereséshez a „Beállítások” fülön add meg a Serper API-kulcsodat.')
    if st.session_state.get('hunter_last_scan'):
        recent=st.session_state['hunter_last_scan']
        st.caption(f'Legutóbbi keresés: {recent["queries"]} lekérés · {recent["offers"]} ellenőrizhető árú találat')
        if recent['errors']:
            with st.expander('Keresési hibák'):
                for err in recent['errors']:st.write(err)

    x,y,z=st.columns([1,1,1.1])
    filter_text=x.text_input('Szűrés név vagy kereskedő alapján',key='hunter_filter_text')
    state=y.selectbox('Állapot',['Mind','Új','Kiválasztva','Előkészítve'],
                        key='hunter_filter_state')
    mode=z.selectbox('Nézet',['Képes termékkártyák','Tömeges kiválasztás'],key='hunter_view')
    statuses={'Mind':'all','Új':'new','Kiválasztva':'selected','Előkészítve':'prepared'}
    items=hunter.offers(topic=topic,status=statuses[state],query=filter_text,
                        max_price=max_price,limit=450)
    if not items:
        st.info('Még nincs találat ezekkel a szűrőkkel. Kattints az „Új termékeket keresek” gombra.')
        return
    st.caption(f'{len(items)} ellenőrizhető forintáras ajánlat. Ezek nem bizonyítottan nyereséges termékek.')
    if mode=='Képes termékkártyák':
        _cards(items,markets,cloud_id,cloud_token,use_ai)
    else:
        rows=[{'Kiválaszt':False,'ID':r['id'],'Termék':r['title'],
               'Kereskedő':r['merchant'],'Beszerzési ár (Ft)':r['price_huf'],
               'Állapot':r['status']} for r in items]
        edited=st.data_editor(rows,use_container_width=True,hide_index=True,
            disabled=['ID','Termék','Kereskedő','Beszerzési ár (Ft)','Állapot'],
            column_config={'Kiválaszt':st.column_config.CheckboxColumn('Kiválaszt')},
            key='hunter_bulk_grid')
        table_rows=edited.to_dict('records') if hasattr(edited,'to_dict') else list(edited)
        chosen=[int(r['ID']) for r in table_rows if r['Kiválaszt'] and r['Állapot']=='new']
        if st.button(f'{len(chosen)} termék automatikus előkészítése',disabled=not bool(chosen),
                     type='primary',key='hunter_bulk_prepare'):
            with st.spinner('Termékenként készülnek a hirdetéspiszkozatok...'):
                done,errors=prepare_ids(chosen,markets,cloud_id=cloud_id,
                                        cloud_token=cloud_token,use_ai=use_ai)
            st.success(f'{len(done)} termék előkészítve.')
            if errors:st.error(' | '.join(errors[:5]))
            st.rerun()


def _selected_tab():
    st.subheader('Automatikusan előkészített termékek')
    rows=db.rows("""SELECT h.*,p.status AS product_status,
                   p.target_price, p.stock_status,
                   COALESCE(x.description_source,'') AS description_source
                   FROM hunter_results h
                   LEFT JOIN products p ON p.id=h.product_id
                   LEFT JOIN hunter_preparations x ON x.hunter_id=h.id
                   WHERE h.status IN ('selected','prepared')
                   ORDER BY h.selected_at DESC,h.id DESC LIMIT 200""")
    if not rows:
        st.info('Válassz ki egy vagy több terméket a Termékvadász találatai közül.')
        return
    st.dataframe([{'Termék':r['title'],'Beszerzés':money(r['price_huf']),
        'Állapot':'Piszkozat kész' if r['status']=='prepared' else 'Kiválasztva',
        'Eladási ár':'Még nincs igazolva' if not r['target_price'] else money(r['target_price']),
        'Készlet':r['stock_status'] or 'ismeretlen','Leírás':r['description_source']} for r in rows],
        hide_index=True,use_container_width=True)
    ids={r['id']:r for r in rows}
    selected=st.selectbox('Termék részletei',list(ids),
            format_func=lambda i:ids[i]['title'],key='hunter_selected_id')
    row=ids[selected]
    if not row.get('product_id'):return
    product=db.row('SELECT * FROM products WHERE id=?',(row['product_id'],))
    if not product:return
    st.markdown('**'+product['title']+'**')
    st.markdown('[Beszállítói ajánlat ellenőrzése]('+row['url']+')')
    st.caption('A Google Shopping-ból érkező előnézeti képek nem kerülnek automatikusan a hirdetésbe.')
    notes=st.text_area('Hirdetésszöveg – szerkeszthető',value=product['description'] or '',
             height=160,key='hunter_desc_edit_'+str(selected))
    if st.button('Leírás mentése',key='hunter_desc_save'):
        if notes.strip():
            db.update_product(product['id'],description=notes.strip())
            for l in db.rows("SELECT * FROM listings WHERE product_id=? AND status IN ('draft','ready')",(product['id'],)):
                db.update_listing(l['id'],description=notes.strip())
            st.success('A leírás frissült a piszkozatokban.')
        else:st.error('Üres hirdetésszöveg nem menthető.')
    st.markdown('**Automatikus katalóguskép-átalakítás**')
    st.caption('A rendszer a keresési találat termékképét használja mintának. '
               'Kézi feltöltés nem szükséges. A kapott kép AI-illusztráció, '
               'nem igazolja a termék pontos állapotát vagy a kép felhasználási jogát.')
    photo=auto_stock_photo.preview_record(selected)
    cloud_id,cloud_token=credentials()[1:]
    if photo and photo.get('bytes'):
        st.image(photo['bytes'],width=620,
                 caption='AI-val átdolgozott képelőnézet · csak ellenőrzés után használható')
        st.markdown('[Eredeti katalóguskép forrása]('+photo['source_image_url']+')')
        if photo['status']=='pending':
            x,y=st.columns(2)
            if x.button('Kép jóváhagyása',type='primary',key='hunter_approve_stock_'+str(selected)):
                try:
                    auto_stock_photo.approve(selected)
                    st.success('Az AI-kép jóváhagyva, elmentve a termékhez.')
                    st.rerun()
                except (ValueError,OSError) as error:st.error(str(error))
            if y.button('Új változat készítése',disabled=not bool(cloud_id and cloud_token),
                        key='hunter_regen_stock_'+str(selected)):
                new=auto_stock_photo.generate_preview(selected,cloud_id,cloud_token,force=True)
                if new.get('status')=='failed':st.error(new['last_error'])
                st.rerun()
        else:
            st.success('A kép jóváhagyva és elmentve.')
    elif photo and photo.get('status') in ('failed','missing'):
        st.warning(photo.get('last_error') or 'Nem sikerült forrásképet találni.')
        if photo['status']=='failed' and cloud_id and cloud_token and st.button('Képgenerálás újra',
              key='hunter_retry_stock_'+str(selected)):
            new=auto_stock_photo.generate_preview(selected,cloud_id,cloud_token,force=True)
            if new.get('status')=='failed':st.error(new['last_error'])
            st.rerun()
    else:
        st.caption('Ehhez a termékhez még nem készült AI-előnézet.')
        if cloud_id and cloud_token and st.button('Kép automatikus elkészítése',
              key='hunter_make_stock_'+str(selected)):
            new=auto_stock_photo.generate_preview(selected,cloud_id,cloud_token)
            if new.get('status')=='failed':st.error(new['last_error'])
            st.rerun()
    if not cloud_id or not cloud_token:
        st.caption('Az automatikus képekhez add meg a Cloudflare-adatokat a Beállítások fülön.')

    drafts=db.rows('SELECT * FROM listings WHERE product_id=? ORDER BY marketplace',(product['id'],))
    if drafts:
        st.markdown('**Elkészült piactéri piszkozatok**')
        st.dataframe([{'Piactér':l['marketplace'],'Cím':l['title'],'Ár':money(l['price']) if l['price'] else 'Ellenőrizendő',
                       'Állapot':l['status']} for l in drafts],hide_index=True,use_container_width=True)
    st.caption('Az eladási ár, készlet, szállítás és tényleges termékfotó még ellenőrizendő. Nem történt automatikus közzététel.')


def _publishing_tab():
    st.subheader('Piactéri közzététel')
    st.info('Hivatalos API-val történő publikálás: jelenleg eBay előkészítve. '
            'Vinted, Facebook Marketplace, Jófogás, Vatera, HardverApró és Amazon: '
            'egyelőre szerkeszthető piszkozat és export, NEM működő automatikus posztolás.')
    rows=db.rows("""SELECT h.* FROM hunter_results h WHERE h.status='prepared' AND h.product_id IS NOT NULL
                    ORDER BY h.selected_at DESC,h.id DESC LIMIT 100""")
    if not rows:
        st.warning('Előbb válassz ki egy terméket, hogy elkészüljenek a hirdetések.')
        return
    selected=st.selectbox('Termék',rows,
        format_func=lambda r:r['title'],key='hunter_publish_product')
    pid=selected['product_id']
    prod=db.row('SELECT * FROM products WHERE id=?',(pid,))
    if not prod:return
    l=db.row("SELECT * FROM listings WHERE product_id=? AND marketplace='eBay' ORDER BY id DESC LIMIT 1",(pid,))
    st.write('**'+prod['title']+'**')
    st.markdown('[Forrás ellenőrzése]('+selected['url']+')')
    with st.expander('1. Termék, ár és saját fotó ellenőrzése',expanded=True):
        price=st.number_input('Tervezett eladási ár (HUF) — ellenőrzött piaci adatok alapján',
            min_value=0,max_value=10_000_000,value=int(prod['target_price'] or 0),
            step=500,key='hunter_target_price')
        verified=st.checkbox('Ellenőriztem, hogy a termék ténylegesen beszerezhető',
            key='hunter_stock_verified')
        if st.button('Ellenőrzött adatok mentése'):
            db.update_product(pid,target_price=int(price),
                **({'stock_status':'available','stock_verified_at':db.utcnow()} if verified else {}))
            if l and l['status'] in ('draft','ready'):
                db.update_listing(l['id'],price=int(price))
            st.success('A termékadatok elmentve. A közzétételhez további eBay fiókadatok kellenek.')

    st.markdown('**Előkészített hirdetések exportálása**')
    from .publisher import listing_package
    st.download_button('Összes piszkozat letöltése (ZIP)',
        listing_package(pid),file_name=f'hirdetesek_{pid}.zip',mime='application/zip')

    with st.expander('2. Hivatalos eBay API — éles közzététel',expanded=False):
        st.caption('A fotót nem kell kézzel feltölteni, de a valódi képhivatkozásokhoz és azok felhasználási jogához továbbra is engedély szükséges. '
                   'Egyszeri beállítás szükséges: OAuth, üzleti szabályzatok, kategória és publikus termékfotók.')
        if l and l['status']=='published':
            st.success('Ez a termék már eBay-en publikáltként szerepel. Újbóli feltöltés tiltva.')
            return
        with st.form('hunter_ebay_form'):
            environment=st.selectbox('Környezet',['sandbox','production'],index=0)
            oauth=st.text_input('eBay eladói OAuth token',type='password')
            a,b=st.columns(2)
            with a:
                merchant=a.text_input('Merchant Location Key')
                category=a.text_input('eBay Category ID')
                sku=a.text_input('Egyedi eBay SKU',value=f'resell-{pid}')
                e_market=a.text_input('Marketplace ID',value='EBAY_DE')
                ccy=a.selectbox('Pénznem',['EUR','USD','GBP','HUF'])
                ebay_price=a.text_input('Eladási ár a választott pénznemben',
                    help='NEM automatikusan átváltott HUF ár.')
            with b:
                condition=b.selectbox('Termék eBay állapotkód',['NEW','USED_EXCELLENT','USED_VERY_GOOD','USED_GOOD'])
                pay=b.text_input('Payment policy ID')
                returns=b.text_input('Return policy ID')
                fulfillment=b.text_input('Fulfillment policy ID')
            image_urls=st.text_area('Saját / engedélyezett HTTPS termékfotók URL-je (soronként egy)')
            aspects=st.text_area('eBay specifikus adatok (JSON)',value='{}')
            rights=st.checkbox('A termék tényleges állapotát és a fotóhasználati jogot ellenőriztem.')
            consent=st.checkbox('Kifejezetten engedélyezem ennek az egy terméknek az eBay-közzétételét.')
            submit=st.form_submit_button('eBay API-közzététel indítása',
                      disabled=not bool(rights and consent and oauth),type='primary')
        if submit:
            try:
                profile={'environment':environment,'merchant_location_key':merchant,
                   'category_id':category,'sku':sku,'marketplace_id':e_market,
                   'currency':ccy,'market_price':ebay_price,
                   'condition':condition,
                   'payment_policy_id':pay,'return_policy_id':returns,
                   'fulfillment_policy_id':fulfillment,
                   'image_urls':[x.strip() for x in image_urls.splitlines() if x.strip()],
                   'aspects':json.loads(aspects),'confirmed_source_photo':rights}
                with st.spinner('Hivatalos eBay API-n keresztül publikálás...'):
                    output=hunter.publish_ebay(selected['id'],oauth,profile)
                if output.get('mode')=='sandbox':
                    st.info('A tesztkörnyezetben létrejött ajánlat — ez nem éles hirdetés.')
                else:
                    st.success('Az eBay visszaigazolta a közzétételt.')
                st.json(output)
            except (ValueError,TypeError,json.JSONDecodeError) as e:
                st.error(str(e))


def _settings_tab():
    st.subheader('Csatlakozások és működés')
    st.caption('Kulcsokat csak az aktuális munkamenetben használunk, nem mentjük az adatbázisba.')
    with st.form('hunter_credentials_form'):
        st.text_input('Serper API-kulcs',type='password',
            value=st.session_state.get('hunter_serper_key',''),key='hunter_serper_input')
        st.text_input('Cloudflare Account ID',
            value=st.session_state.get('hunter_cloud_id',''),key='hunter_account_input')
        st.text_input('Cloudflare Workers AI token',type='password',
            value=st.session_state.get('hunter_cloud_token',''),key='hunter_token_input')
        saved=st.form_submit_button('Kapcsolatok mentése a munkamenetben')
        if saved:
            st.session_state['hunter_serper_key']=st.session_state['hunter_serper_input'].strip()
            st.session_state['hunter_cloud_id']=st.session_state['hunter_account_input'].strip()
            st.session_state['hunter_cloud_token']=st.session_state['hunter_token_input'].strip()
            st.success('A munkamenetben elmentve, adatbázisba nem került.')
    st.markdown('**Piacterek**')
    st.dataframe([{'Piactér':name,'Funkció':MODES[name]} for name in db.PLATFORMS],
        hide_index=True,use_container_width=True)
    st.caption('A képek generálása Cloudflare-t, a keresések a Serper keretét használják. '
               'A hirdetés-előkészítés automatikus; más piactérre nem állítunk hamis publikálási státuszt.')


def render_hunter():
    hunter.initialize()
    st.markdown(STYLE,unsafe_allow_html=True)
    st.markdown("""<div class="hunter-hero">
       <div class="hunter-pill">RESELL AGENT · DISCOVERY</div>
       <h1>Termékvadász</h1>
       <p>Találd meg, válogasd ki, és készítsd elő a hirdetéseket egy helyen.
       Sok magyarországi ajánlatból választhatsz; a kiválasztott termékek piszkozata és katalógusképes AI-előnézete automatikusan készül.</p>
       </div>""",unsafe_allow_html=True)
    count=db.row("SELECT COUNT(*) n FROM hunter_results")['n']
    chosen=db.row("SELECT COUNT(*) n FROM hunter_results WHERE status IN ('selected','prepared')")['n']
    prepared=db.row("SELECT COUNT(*) n FROM hunter_results WHERE status='prepared'")['n']
    m1,m2,m3,m4=st.columns(4)
    m1.metric('Találatok',count)
    m2.metric('Kiválasztott',chosen)
    m3.metric('Előkészített',prepared)
    m4.metric('Serper lekérések / hónap',f'{shopping.current_usage()}/{shopping.MONTHLY_LIMIT}')
    serper,cloud_id,cloud_token=credentials()
    markets=st.session_state.get('hunter_marketplaces',list(db.PLATFORMS))
    use_ai=st.session_state.get('hunter_use_ai',True)
    with st.expander('Melyik piacterekre készüljenek a hirdetések?',expanded=False):
        st.multiselect('Piacterek',list(db.PLATFORMS),default=list(db.PLATFORMS),
                       key='hunter_marketplaces')
        st.checkbox('Természetes magyar AI-leírás Cloudflare-rel (ha van kulcs)',
                    value=True,key='hunter_use_ai')
    tabs=st.tabs(['Felfedezés','Kiválasztottak','Közzététel','Beállítások'])
    with tabs[0]:
        _feed_tab(serper,cloud_id,cloud_token,markets,use_ai)
    with tabs[1]:
        _selected_tab()
    with tabs[2]:
        _publishing_tab()
    with tabs[3]:
        _settings_tab()
