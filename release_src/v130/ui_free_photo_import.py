"""Free ChatGPT-to-Resell Agent photo import and review UI."""
from __future__ import annotations
import streamlit as st
from . import db, free_photo_import

def _prompt(title: str):
    return (
      f"Use my uploaded original photo of {title} as the source. Make FOUR SEPARATE "
      "high-resolution, realistic, natural-looking product photos in a normal home "
      "(wooden table, daylight, soft background blur, mild imperfections of a "
      "real phone photo). One image per angle: (1) front three-quarter, "
      "(2) straight front, (3) side profile, (4) rear three-quarter. "
      "NO COLLAGES, no labels, no text overlays, no advertisements, no extra "
      "objects being sold. Preserve the product identity, colors, visible details "
      "and any box or accessories accurately. Where the original does not show "
      "a side, that view must be treated as illustrative, never evidence of "
      "condition or included parts. Produce four separate full-resolution images."
    )

def render_free_photo_import_page(products):
    st.title('Free ChatGPT Photo Import')
    st.caption('Generate in ChatGPT, import all photos together, preview and approve, save to this product. No API key. No local GPU generation.')
    if not products:
        st.info('Add a product first.')
        return
    by_id={p['id']:p for p in products}
    product_id=st.selectbox('Choose product',list(by_id),
        format_func=lambda i:f"#{i} · {by_id[i]['title']}",key='free_import_product')
    product=by_id[product_id]
    st.subheader('1. Generate your photos in ChatGPT')
    st.write('Upload your genuine source photo in ChatGPT and ask for four separate angles. Download the generated pictures or a ZIP.')
    st.markdown('[Open ChatGPT](https://chatgpt.com/)')
    with st.expander('Copy suggested generation prompt',expanded=False):
        st.code(_prompt(product['title']),language=None)
    st.subheader('2. Import and preview')
    files=st.file_uploader('Drop your photos here (or one ZIP)',type=['png','jpg','jpeg','webp','zip'],
        accept_multiple_files=True,key=f'free_import_upload_{product_id}',
        help='Up to 12 separate images, 18 MB per image, 85 MB total upload.')
    if st.button('Load photos for review',disabled=not bool(files),type='primary'):
        try:
            images=free_photo_import.unpack_uploads([(file.name,file.getvalue()) for file in files])
            st.session_state['free_photo_import_batch']={'id':product_id,'images':images}
            st.success(f'Imported {len(images)} separate images. All are awaiting approval.')
        except (ValueError,OSError) as e:
            st.error(str(e))
    batch=st.session_state.get('free_photo_import_batch')
    if not batch or batch['id']!=product_id:
        st.info('Import photos above to review them. No external service is called.')
    else:
        st.subheader('3. Approve individual images')
        images=batch['images']
        for i,item in enumerate(images):
            st.markdown(f"**Photo {i+1}: {item['name']}**")
            st.image(item['bytes'],width=720,
                caption=f"AI illustrative preview — {item['width']} × {item['height']}")
            cols=st.columns([1,1,1])
            if cols[0].button('Approve ✓' if not item['approved'] else 'Approved ✓',
                key=f'free_import_approve_{product_id}_{item["sha256"][:12]}',
                disabled=item['approved']):
                item['approved']=True
                st.rerun()
            if cols[1].button('Remove from selection',
                key=f'free_import_reject_{product_id}_{item["sha256"][:12]}'):
                item['approved']=False
                st.rerun()
            cols[2].download_button('Download PNG',item['bytes'],
                file_name=f'AI_ILLUSTRATIVE_product_{product_id}_{i+1}.png',
                mime='image/png',key=f'free_import_download_{product_id}_{item["sha256"][:12]}')
            st.divider()
        chosen=sum(bool(x['approved']) for x in images)
        st.write(f'{chosen} of {len(images)} approved.')
        if chosen:
            st.download_button('Export approved photos (ZIP)',
                free_photo_import.approved_zip(images,product_id),
                file_name=f'product_{product_id}_ai_previews.zip',
                mime='application/zip',key=f'free_import_export_{product_id}')
            if st.button('Save approved photos to product',type='primary'):
                try:
                    saved=free_photo_import.save_approved(images,db.DATA,product_id)
                    st.success(f'Saved {len(saved)} individual photos. Originals unchanged.')
                except (ValueError,OSError) as e:st.error(str(e))
    st.subheader('Previously saved AI preview files')
    directory=db.DATA/'ai_previews'/str(product_id)
    saved=sorted(directory.glob('AI_ILLUSTRATIVE_*.png')) if directory.is_dir() else []
    if saved:
        st.caption(f'{len(saved)} saved preview(s); separate from real product photos.')
        for j,path in enumerate(saved[-16:]):
            data=path.read_bytes()
            st.image(data,width=540,caption='AI illustrative image — not verified product evidence')
            st.download_button('Download saved image',data,file_name=path.name,
                mime='image/png',key=f'free_saved_{product_id}_{j}_{path.name}')
    else:
        st.caption('No AI previews have been saved for this product yet.')
    st.warning('AI-generated rear/side views may invent product details. Keep genuine product photos to show the actual condition. AI previews are not automatically published.')
