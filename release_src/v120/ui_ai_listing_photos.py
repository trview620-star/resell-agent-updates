"""One-click 4-angle illustrative AI photo previews; each picture is a separate file."""
from __future__ import annotations
from datetime import datetime,timezone
import io
import os
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile,ZIP_DEFLATED
import streamlit as st
from . import db, ai_listing_photos

def _approved_zip(batch, product_id):
    out=io.BytesIO()
    with ZipFile(out,'w',ZIP_DEFLATED) as archive:
        for key,title,_ in ai_listing_photos.ANGLES:
            item=batch['images'].get(key)
            if item and item.get('approved'):
                archive.writestr(f'AI_ILLUSTRATIVE_product_{product_id}_{key}.png',item['bytes'])
        archive.writestr('README.txt',
            'These are AI-generated illustrative views. Check accuracy against real photos. '
            'They do not prove condition, accessories or possession.\n')
    return out.getvalue()

def render_ai_photo_page(products):
    st.title('AI Listing Photos')
    st.caption('Upload a real source → generate four separate home-style photos → preview each → approve or regenerate.')
    st.warning('Generated camera angles are illustrative, not photographs of the actual unseen sides. Do not use them as evidence of product condition. Your original image stays unchanged.')
    if not products:
        st.info('Add a product and upload an original photo first.')
        return
    by_id={p['id']:p for p in products}
    product_id=st.selectbox('Product',list(by_id),
        format_func=lambda id:f"#{id} · {by_id[id]['title']}",key='ai_photos_product')
    product=by_id[product_id]
    photos=db.rows('SELECT * FROM photos WHERE product_id=? ORDER BY id DESC',(product_id,))
    if not photos:
        st.info('Upload a reference image under Add product or Products & photos.')
        return
    photo_id=st.selectbox('Reference photo',[p['id'] for p in photos],
        format_func=lambda id:next(p['original_name'] for p in photos if p['id']==id),
        key='ai_photos_source')
    photo=next(p for p in photos if p['id']==photo_id)
    reference=db.PHOTOS/photo['filename']
    if not reference.is_file():
        st.error('Reference photo is missing from the local data folder.')
        return
    st.image(str(reference),caption='Your unchanged source image',width=420)
    st.caption('Four separate images: front three-quarter, straight front, side, rear three-quarter. No collage and no manual photo adjustment controls.')
    env_key=os.getenv('OPENAI_API_KEY','').strip()
    api_key=env_key or st.text_input('Image generation API key',type='password',
        help='Use your own OpenAI API key. Ollama and ChatGPT subscriptions do not include image API calls.',
        key='ai_photo_api_key')
    if not api_key:
        st.info('To generate new views, enter an OpenAI API key with image-edit access. This is separate from the connected Ollama model.')
    st.caption('4 generation requests use paid API credits. Your image is sent to the API only when you click Generate or Regenerate.')
    key=(product_id,photo_id)
    batch=st.session_state.get('ai_photo_batch')
    if not batch or batch.get('key')!=key:
        batch={'key':key,'images':{},'created_at':None}
        st.session_state['ai_photo_batch']=batch
    if st.button('Generate 4 separate photos',type='primary',disabled=not bool(api_key)):
        # Explicit user action, never called when app renders or automatically on product change.
        new_images={}
        meter=st.progress(0,text='Preparing individual views')
        for i,(angle,title,_) in enumerate(ai_listing_photos.ANGLES):
            try:
                with st.spinner('Generating '+title+'...'):
                    data=ai_listing_photos.generate_view(reference,angle,api_key,product['title'])
                new_images[angle]={'bytes':data,'approved':False}
            except ValueError as e:
                st.error(f'{title}: {e}')
                break
            meter.progress((i+1)/len(ai_listing_photos.ANGLES),text=f'{i+1}/4 completed')
        batch['images']=new_images
        batch['created_at']=datetime.now(timezone.utc).isoformat()
        if new_images:
            st.success(f'{len(new_images)} separate previews generated. Review and approve them below.')
        meter.empty()
    if not batch['images']:
        return
    st.divider()
    st.subheader('Individual previews')
    st.caption('Each image is its own file. The generator does not build collages.')
    for angle,title,_ in ai_listing_photos.ANGLES:
        item=batch['images'].get(angle)
        if not item:continue
        st.markdown('**'+title+'**')
        st.image(item['bytes'],caption='AI illustrative view',width=700)
        controls=st.columns(3)
        if controls[0].button('Approve' if not item.get('approved') else 'Approved ✓',
            key='approve_ai_'+angle,disabled=bool(item.get('approved'))):
            item['approved']=True
            st.success('Approved '+title)
        controls[1].download_button('Download PNG',data=item['bytes'],
            file_name=f'AI_ILLUSTRATIVE_product_{product_id}_{angle}.png',
            mime='image/png',key='download_ai_'+angle)
        instructions=st.text_input('What should change in '+title+'?',
            placeholder='Make it less polished, keep the box on the left…',
            key='feedback_ai_'+angle)
        if controls[2].button('Regenerate angle',key='regen_ai_'+angle,disabled=not bool(api_key)):
            try:
                with st.spinner('Regenerating '+title+'...'):
                    replacement=ai_listing_photos.generate_view(
                        reference,angle,api_key,product['title'],instructions)
                batch['images'][angle]={'bytes':replacement,'approved':False}
                st.success('Updated preview. Reapprove before saving.')
                st.rerun()
            except ValueError as e:
                st.error(str(e))
        st.divider()
    approved=sum(1 for item in batch['images'].values() if item.get('approved'))
    st.write(f'{approved} of {len(batch["images"])} images approved.')
    if approved:
        st.download_button('Download approved images as separate PNGs (ZIP)',
            _approved_zip(batch,product_id),
            file_name=f'ai_photo_previews_product_{product_id}.zip',
            mime='application/zip')
        if st.button('Save approved images to local preview folder'):
            base=db.DATA/'ai_previews'/str(product_id)
            base.mkdir(parents=True,exist_ok=True)
            saved=[]
            for angle,title,_ in ai_listing_photos.ANGLES:
                item=batch['images'].get(angle)
                if not item or not item['approved']:continue
                dest=base/f'AI_ILLUSTRATIVE_{photo_id}_{angle}_{uuid4().hex[:8]}.png'
                dest.write_bytes(item['bytes'])
                saved.append(str(dest))
            st.success(f'Saved {len(saved)} separate image files to '+str(base))
    st.caption('These previews are not automatically attached to marketplace listings. Only original item photos can establish actual condition.')
