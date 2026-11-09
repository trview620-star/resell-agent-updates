"""A safe one-click seasonal trial. Exactly one product and one generated image."""
from __future__ import annotations
import streamlit as st
from . import db, christmas_trial, free_photo_import, cloudflare_photos

def render_christmas_trial(products):
    st.title('Christmas pilot — 1 product + 1 photo')
    st.caption('One real Christmas candidate → one sourced price → one AI image → one unpriced draft. Nothing is published or purchased.')
    st.info('Pilot item: MagicHome 25 cm red Advent wreath (SKU 8090234). An example source was found in Hungary; retail price and shipping are rechecked where possible.')
    with st.expander('Connections',expanded=False):
        serper=st.text_input('Serper shopping API key (optional)',
            value=st.session_state.get('serper_shopping_api_key',''),
            type='password',key='xmas_serper_key',
            help='If omitted, the pilot uses a dated, explicitly labeled retailer quote.')
        account=st.text_input('Cloudflare Account ID',
            value=st.session_state.get('cf_ai_account_id',''),
            key='xmas_cf_account',help='Your Workers AI account ID, not secret.')
        token=st.text_input('Cloudflare Workers AI API token',
            value=st.session_state.get('cf_ai_token',''),
            type='password',key='xmas_cf_token',
            help='Entered only in this local Streamlit session; not saved in the database.')
        model=st.selectbox('Model',list(cloudflare_photos.MODELS),
            index=0,key='xmas_cf_model')
    ready=bool(account.strip() and token.strip())
    st.markdown('**This pilot performs at most one Serper query and one Cloudflare image request per click.**')
    if not ready:
        st.warning('Open Connections and enter your Cloudflare Account ID and token to generate the photo.')
    if st.button('Run one Christmas product + one photo',type='primary',disabled=not ready):
        offer=christmas_trial.reference_offer()
        notice='Using dated example quote.'
        try:
            with st.spinner('Checking one Christmas supplier product...'):
                offer,notice=christmas_trial.find_one_offer(serper)
        except (ValueError,RuntimeError) as error:
            notice='Shopping search not available ('+str(error)[:150]+'); showing the dated source example.'
        result={'offer':offer,'notice':notice,'photo':None,'saved':False}
        st.session_state['xmas_trial_result']=result
        try:
            with st.spinner('Generating one natural-looking holiday product photo on Cloudflare...'):
                result['photo']=christmas_trial.generate_one_photo(account,token,model)
            st.success('Created one Christmas candidate with one AI photo. Nothing has been published.')
        except ValueError as error:
            st.error('The product research is ready, but photo generation failed: '+str(error))
            st.info('You can retry the one-product pilot after correcting the Cloudflare connection.')
    result=st.session_state.get('xmas_trial_result')
    if not result:
        st.caption('No trial has been run in this browser session.')
        return
    offer=result['offer']
    st.divider()
    st.subheader('One Christmas product')
    st.write('**'+christmas_trial.PRODUCT['name']+'**')
    st.write('Supplier lead: **'+str(offer['merchant'])+'**')
    st.markdown('[Open actual supplier product]('+str(offer['url'])+')')
    st.write('Advertised or example price: **'+f"{offer['price_huf']:,} Ft".replace(',',' ')+'**')
    if isinstance(offer.get('shipping_huf'),int):
        st.write('Known supplier delivery example: **'+f"{offer['shipping_huf']:,} Ft".replace(',',' ')+'**')
        st.write('Combined known price + supplier delivery: **'+
                 f"{christmas_trial.purchase_cost_known(offer):,} Ft".replace(',',' ')+'**')
    else:
        st.warning('Supplier delivery price unknown — checkout must be verified.')
    st.caption(str(result['notice']))
    st.warning('No verified resale price, margin, current stock or delivery deadline. This is a research candidate, NOT a qualified profitable product.')
    st.subheader('One AI-generated picture')
    if result.get('photo'):
        st.image(result['photo'],width=700,
            caption='AI concept illustration. Not a photograph of this exact MagicHome product.')
        st.download_button('Download this one PNG',result['photo'],
           file_name='CHRISTMAS_AI_ILLUSTRATION_8090234.png',mime='image/png')
    else:
        st.info('One-photo preview not available yet. Your supplier candidate remains saved in this session.')
    st.subheader('One Hungarian listing draft — unpriced')
    st.text_area('Review draft',christmas_trial.hungarian_draft(),
        height=190,key='xmas_preview_draft')
    st.caption('No price or condition is invented. You can verify the supplier item before choosing a resale price.')
    if result.get('saved'):
        st.success('Pilot candidate and single AI preview already saved.')
    elif result.get('photo') and st.button('Approve photo and save ONE draft candidate',
          type='primary',key='xmas_save_candidate'):
        try:
            existing=db.row('SELECT * FROM products WHERE brand=? AND model=? ORDER BY id DESC LIMIT 1',
                           (christmas_trial.PRODUCT['brand'],christmas_trial.PRODUCT['model']))
            if existing:product_id=existing['id']
            else:
                product_id=db.insert_product({
                    'title':christmas_trial.PRODUCT['name'],
                    'brand':christmas_trial.PRODUCT['brand'],
                    'model':christmas_trial.PRODUCT['model'],
                    'category':christmas_trial.PRODUCT['category'],
                    'condition_text':'Unknown — supplier stock/condition not verified',
                    'description':christmas_trial.hungarian_draft(),
                    'supplier':offer['merchant'],'supplier_url':offer['url'],
                    'supplier_price':int(offer['price_huf']),
                    'inbound_shipping':int(offer['shipping_huf'] or 0),
                    'outbound_shipping':0,'packaging':0,'marketplace_fees':0,
                    'risk_buffer':0,'target_price':0,
                    'stock_status':'unknown','stock_verified_at':None,
                    'eta_days':None,'fulfillment':db.FULFILLMENT[0],
                    'status':'candidate',
                    'notes':'Christmas pilot; dated/third-party research lead. Supplier shipping may be unknown. '
                            'No resale comparable evidence or verified selling price; do not publish. '
                            'AI photo is illustrative and not a real photograph of item.'})
            photos=free_photo_import.save_approved(
                [{'bytes':result['photo'],'approved':True}],db.DATA,product_id)
            result['saved']=True
            st.success(f'Saved candidate #{product_id} with exactly one AI illustrative photo. No live listing created.')
        except (ValueError,OSError,RuntimeError,TypeError) as error:
            st.error('Could not save draft candidate: '+str(error))
    st.caption('The AI photo is stored separately from real product photographs. Real product images are necessary to verify condition and included items.')
