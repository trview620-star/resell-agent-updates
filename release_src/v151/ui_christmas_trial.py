"""Minimal Hungarian one-product pilot: one result, one photo, natural listing."""
from __future__ import annotations

import streamlit as st
from . import db, christmas_trial, free_photo_import, cloudflare_photos


def _money(amount):
    return f'{int(amount):,} Ft'.replace(',', ' ')


def _save_candidate(result, title, description):
    """Create/revise one local draft; never publish or buy."""
    offer=result['offer']
    existing=db.row(
        'SELECT * FROM products WHERE brand=? AND model=? ORDER BY id DESC LIMIT 1',
        (christmas_trial.PRODUCT['brand'],christmas_trial.PRODUCT['model']))
    if existing:
        product_id=existing['id']
        db.update_product(product_id,title=title,description=description)
    else:
        product_id=db.insert_product({
            'title':title,
            'brand':christmas_trial.PRODUCT['brand'],
            'model':christmas_trial.PRODUCT['model'],
            'category':christmas_trial.PRODUCT['category'],
            'condition_text':'Állapot még nincs ellenőrizve',
            'description':description,
            'supplier':offer['merchant'],'supplier_url':offer['url'],
            'supplier_price':int(offer['price_huf']),
            'inbound_shipping':int(offer.get('shipping_huf') or 0),
            'outbound_shipping':0,'packaging':0,'marketplace_fees':0,
            'risk_buffer':0,'target_price':0,
            'stock_status':'unknown','stock_verified_at':None,
            'eta_days':0,'fulfillment':db.FULFILLMENT[0],
            'status':'candidate',
            'notes':'Karácsonyi teszt. Szállítás és készlet ellenőrizendő. '
                    'AI-kép: illusztráció, nem a termék hiteles állapotfotója. '
                    'Eladási ár és nyereség még nincs ellenőrizve.'})
    if result.get('photo') and not result.get('photo_saved'):
        free_photo_import.save_approved(
            [{'bytes':result['photo'],'approved':True}],db.DATA,product_id)
        result['photo_saved']=True
    result['saved']=True
    return product_id


def render_christmas_trial(products):
    st.title('Karácsonyi próbahirdetés')
    st.caption('1 termék · 1 kép · 1 hirdetés')
    st.markdown('**Piros adventi koszorú – 25 cm**')

    with st.expander('Kapcsolat és beszerzési adatok',expanded=False):
        serper=st.text_input('Serper kulcs (nem kötelező)',
            value=st.session_state.get('serper_shopping_api_key',''),
            type='password',key='xmas_serper_key')
        account=st.text_input('Cloudflare Account ID',
            value=st.session_state.get('cf_ai_account_id',''),
            key='xmas_cf_account')
        token=st.text_input('Cloudflare API token',
            value=st.session_state.get('cf_ai_token',''),
            type='password',key='xmas_cf_token')
        st.markdown('[Beszerzési oldal]('+christmas_trial.PRODUCT['source_url']+')')
        st.caption('Ár- és készletellenőrzés a tényleges rendelés előtt szükséges. '
                   'Az illusztráció nem a beszerzési tétel valódi fotója.')

    with st.expander('Pontosabb kép készítése (opcionális)',expanded=False):
        uploaded=st.file_uploader('Eredeti vagy beszállítói termékfotó',
            type=['png','jpg','jpeg','webp'],key='xmas_reference_image')
        st.caption('Ha feltöltesz egy valódi termékképet, az AI azt használja mintának, '
                   'és főleg a környezetet és a fényeket alakítja át. '
                   'Termékfotó nélkül a generált kép csak általános illusztráció.')

    ready=bool(account.strip() and token.strip())
    if not ready:
        st.info('A képhez nyisd meg a „Kapcsolat és beszerzési adatok” részt, és add meg a Cloudflare-adatokat.')

    model=next(iter(cloudflare_photos.MODELS))
    picture=uploaded.getvalue() if uploaded else None
    if st.button('Kép és hirdetés készítése',type='primary',disabled=not ready,
                 key='xmas_generate'):
        try:
            offer,note=christmas_trial.find_one_offer(serper)
        except (ValueError,RuntimeError) as e:
            offer,note=christmas_trial.reference_offer(), 'A friss keresés nem sikerült; korábbi ár jelenik meg.'
        result={'offer':offer,'notice':note,'photo':None,'saved':False,
                'photo_saved':False,'had_reference':bool(picture)}
        st.session_state['xmas_trial_result']=result
        st.session_state['xmas_title_draft']=christmas_trial.hungarian_title()
        st.session_state['xmas_desc_draft']=christmas_trial.hungarian_draft()
        try:
            with st.spinner('Egy természetes hatású termékfotó készül...'):
                result['photo']=christmas_trial.generate_one_photo(
                    account,token,model,reference_image=picture)
        except ValueError as e:
            st.error('A képgenerálás nem sikerült: '+str(e))

    result=st.session_state.get('xmas_trial_result')
    if not result:
        return

    offer=result['offer']
    st.divider()
    st.caption('Beszerzési ajánlat: '+str(offer['merchant'])+' · '+_money(offer['price_huf'])+
               (' + '+_money(offer['shipping_huf'])+' szállítás' if isinstance(offer.get('shipping_huf'),int) else ' + szállítás ellenőrizendő'))
    if 'Historical' in str(offer.get('source_status','')):
        st.caption('Korábbi ajánlat, nem élő ár.')
    st.markdown('[Forrás megnyitása]('+str(offer['url'])+')')

    left,right=st.columns([1,1],gap='large')
    with left:
        st.markdown('**Fotó**')
        if result.get('photo'):
            st.image(result['photo'],use_container_width=True)
            st.download_button('Kép letöltése',result['photo'],
                file_name='adventi_koszoru_illusztracio.png',mime='image/png')
        else:
            st.info('Még nincs elkészült kép.')
        st.caption('AI-illusztráció: az eredeti termék részleteit ellenőrizd a beszállítói fotón.')
        if ready and st.button('Másik kép készítése',key='xmas_regenerate'):
            try:
                with st.spinner('Másik fotó készül...'):
                    result['photo']=christmas_trial.generate_one_photo(
                        account,token,model,reference_image=picture)
                result['photo_saved']=False
                result['saved']=False
                st.rerun()
            except ValueError as e:
                st.error('A képgenerálás nem sikerült: '+str(e))

    with right:
        st.markdown('**Hirdetés**')
        if 'xmas_title_draft' not in st.session_state:
            st.session_state['xmas_title_draft']=christmas_trial.hungarian_title()
        if 'xmas_desc_draft' not in st.session_state:
            st.session_state['xmas_desc_draft']=christmas_trial.hungarian_draft()
        title=st.text_input('Cím',key='xmas_title_draft')
        description=st.text_area('Leírás',key='xmas_desc_draft',height=190)
        st.caption('A cikkszám, az AI-megjegyzés és a belső ellenőrzések nem kerülnek a hirdetésszövegbe.')
        if result.get('saved'):
            st.success('A piszkozat és a kép elmentve.')
        elif st.button('Piszkozat és kép mentése',type='primary',
            disabled=not bool(result.get('photo')),key='xmas_save'):
            if not title.strip() or not description.strip():
                st.error('A cím és a leírás nem lehet üres.')
            else:
                try:
                    product_id=_save_candidate(result,title.strip(),description.strip())
                    st.success(f'Elmentve a(z) #{product_id} termékhez. Nincs közzétéve.')
                except (ValueError,OSError,RuntimeError,TypeError) as e:
                    st.error('Nem sikerült menteni: '+str(e))

    st.caption('Ez próbahirdetés: beszerzési készletet, tényleges állapotot és eladási árat külön kell ellenőrizni.')
