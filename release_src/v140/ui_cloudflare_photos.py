"""Automatic Cloudflare-generated photos in the local Resell Agent dashboard.

This never calls the user's local GPU and never persists the Cloudflare token.
"""
from __future__ import annotations
from uuid import uuid4
import streamlit as st
from . import db, cloudflare_photos, free_photo_import
from .ai_listing_photos import ANGLES

def render_cloudflare_photo_page(products):
    st.title('Cloudflare AI Product Photos')
    st.caption('One original photo → four individual photorealistic previews → approve or regenerate → save to product.')
    st.info('Cloud generation runs on Cloudflare, not on your GTX 1080. Free-plan usage is limited; new images consume Workers AI quota.')
    if not products:
        st.warning('Add a product and upload a real reference photo first.')
        return
    products_by_id={p['id']:p for p in products}
    product_id=st.selectbox('Product',list(products_by_id),
         format_func=lambda i:f"#{i} · {products_by_id[i]['title']}",
         key='cf_ai_product_id')
    product=products_by_id[product_id]
    photos=db.rows('SELECT * FROM photos WHERE product_id=? ORDER BY id DESC',(product_id,))
    if not photos:
        st.info('Upload a reference photo to this product using Products & photos.')
        return
    by_photo={x['id']:x for x in photos}
    photo_id=st.selectbox('Original reference photo',list(by_photo),
        format_func=lambda i:by_photo[i]['original_name'],key='cf_ai_ref_photo_id')
    photo=by_photo[photo_id]
    original=db.PHOTOS/photo['filename']
    if not original.is_file():
        st.error('The original file is missing.')
        return
    st.image(str(original),caption='Original photo — never overwritten',width=390)

    with st.expander('Cloudflare connection', expanded=True):
        account=st.text_input('Cloudflare Account ID',placeholder='32-character account identifier',
            key='cf_ai_account_id',help='Find this in Cloudflare → Workers AI → Use REST API.')
        token=st.text_input('Cloudflare Workers AI API token',type='password',
            key='cf_ai_token',help='Enter it only here. The token is used in memory for requests and is not saved to the product database.')
        model=st.selectbox('Image model',list(cloudflare_photos.MODELS),
            key='cf_ai_model',help='Start with Klein 4B for inexpensive previews. Klein 9B may be more realistic but uses substantially more daily quota.')
        st.caption('Cloudflare Free currently includes a daily neuron allowance. On the Free plan, requests stop once it is exhausted.')
    ready=bool(account.strip() and token.strip())
    key=(product_id,photo_id,model)
    current=st.session_state.get('cf_ai_batch')
    if not current or current['key']!=key:
        current={'key':key,'images':{}}
        st.session_state['cf_ai_batch']=current

    left,right=st.columns([2,2])
    start=left.button('Generate 4 photos',type='primary',disabled=not ready,
        key='cf_ai_generate_all')
    test=right.button('Test 1 front photo',disabled=not ready,key='cf_ai_test_one')
    if start or test:
        plan=ANGLES if start else ANGLES[:1]
        # Only an explicit button click can incur usage.
        progress=st.progress(0,text='Generating on Cloudflare')
        generated={} if start else dict(current['images'])
        for index,(angle,title,_) in enumerate(plan):
            try:
                with st.spinner('Creating '+title+'…'):
                    generated[angle]={'bytes':cloudflare_photos.generate(
                        original,angle,account,token,model,product['title']),
                        'approved':False}
            except ValueError as error:
                st.error(title+': '+str(error))
                break
            progress.progress((index+1)/len(plan),text=f'{index+1}/{len(plan)} photos ready')
        current['images']=generated
        progress.empty()
        if generated:
            st.success(f'{len(generated)} independent photo preview(s) available below.')
    st.caption('Photos are illustrative. AI may invent side/rear details invisible in the reference. Use genuine photos to document the item being sold.')

    if current['images']:
        st.divider()
        st.subheader('Review your four separate photos')
        for angle,title,_ in ANGLES:
            item=current['images'].get(angle)
            if not item:continue
            st.markdown('**'+title+'**')
            st.image(item['bytes'],caption='AI-generated illustrative product view',width=730)
            cols=st.columns([1,1,1])
            if cols[0].button('Approve ✓' if not item['approved'] else 'Approved ✓',
                key='cf_ai_approve_'+angle,disabled=item['approved']):
                item['approved']=True
                st.rerun()
            cols[1].download_button('Download PNG',data=item['bytes'],
                file_name=f'AI_ILLUSTRATIVE_product_{product_id}_{angle}.png',
                mime='image/png',key='cf_ai_download_'+angle)
            notes=st.text_input('What should change in '+title+'?',
                placeholder='More natural lighting, less perfect framing…',
                key='cf_ai_feedback_'+angle)
            if cols[2].button('Regenerate angle',disabled=not ready,key='cf_ai_regen_'+angle):
                try:
                    with st.spinner('Regenerating '+title+'…'):
                        image=cloudflare_photos.generate(original,angle,account,token,model,
                            product['title'],notes)
                    current['images'][angle]={'bytes':image,'approved':False}
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
            st.divider()
        approved=sum(1 for x in current['images'].values() if x['approved'])
        st.write(f'{approved} approved out of {len(current["images"])} generated')
        if approved:
            if st.button('Save approved photos to this product',type='primary',key='cf_ai_save'):
                try:
                    saved=free_photo_import.save_approved(
                        list(current['images'].values()),db.DATA,product_id)
                    st.success(f'Saved {len(saved)} individual photos to this product.')
                except (OSError,ValueError) as error:
                    st.error(str(error))
            st.download_button('Download approved photos as separate PNGs (ZIP)',
                data=free_photo_import.approved_zip(list(current['images'].values()),product_id),
                file_name=f'product_{product_id}_AI_previews.zip',
                mime='application/zip',key='cf_ai_download_all')
    st.warning('Generated views are not automatically published to marketplaces and are not proof of product condition or ownership.')
