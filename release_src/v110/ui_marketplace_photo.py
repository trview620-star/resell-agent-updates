"""Streamlit UI for a reversible local marketplace photo workflow."""
from hashlib import sha256
import streamlit as st
from . import db,marketplace_photo

def render_photo_mode(photo):
    st.divider()
    st.subheader('Marketplace Photo Mode')
    st.caption('Preview locally, download or save edited copies. Original files stay untouched.')
    st.info('Natural finish adjusts camera appearance. Room mode uses your own room photo and creates an edited composite, not evidence that this item was actually photographed there.')
    path=db.PHOTOS/photo['filename']
    if not path.is_file():
        st.error('Original photo is missing.')
        return
    mode=st.radio('Mode',['Natural camera finish','Room background composite'],
                  horizontal=True,key='mp_mode')
    strength=st.slider('Natural camera effect',0.0,1.0,0.45,0.05,key='mp_strength')
    scale,x,y,blur=0.73,0.5,0.72,5.0
    room=None
    if mode=='Room background composite':
        st.caption('Use a real desk or kitchen photo. Works best on a product image with a plain white or transparent background.')
        uploaded=st.file_uploader('Upload a room or tabletop image',
                    type=['png','jpg','jpeg','webp'],key='mp_room')
        if uploaded:
            room=uploaded.getvalue()
            st.image(room,caption='Selected room background',width=380)
        a,b=st.columns(2)
        with a:
            scale=st.slider('Product size',0.35,0.95,0.73,0.02,key='mp_scale')
            x=st.slider('Horizontal placement',0.0,1.0,0.5,0.05,key='mp_x')
        with b:
            y=st.slider('Vertical placement',0.0,1.0,0.72,0.05,key='mp_y')
            blur=st.slider('Background blur',0.0,16.0,5.0,1.0,key='mp_blur')
    original=path.read_bytes()
    signature=(photo['id'],sha256(original).hexdigest(),mode,strength,scale,x,y,blur,
               sha256(room).hexdigest() if room else None)
    if st.button('Preview photo edit',
            disabled=(mode=='Room background composite' and not room),
            key='mp_preview',type='primary'):
        try:
            with st.spinner('Editing image locally...'):
                edited=marketplace_photo.make_marketplace_photo(
                    original,room_bytes=room,strength=strength,
                    scale=scale,x=x,y=y,blur=blur)
            st.session_state['mp_edit']=edited
            st.session_state['mp_signature']=signature
        except (ValueError,OSError,MemoryError) as error:
            st.error(str(error))
    image=st.session_state.get('mp_edit') if st.session_state.get('mp_signature')==signature else None
    if image:
        st.image(image,caption='Edited preview — original preserved',width=520)
        st.download_button('Download full-resolution JPEG',
            data=image,file_name=f'product_{photo["product_id"]}_edited.jpg',
            mime='image/jpeg',key='mp_download')
        if st.button('Save edited copy locally',key='mp_save'):
            try:
                saved=marketplace_photo.save_marketplace_variant(photo['id'],image)
                st.success('Saved edited image: '+saved.name)
            except (OSError,ValueError) as error:
                st.error(str(error))
    elif st.session_state.get('mp_signature'):
        st.caption('Click Preview photo edit to apply the new settings.')
    variants=marketplace_photo.saved_variants(photo['id'])
    if variants:
        with st.expander(f'Saved edited copies ({len(variants)})'):
            for index,saved in enumerate(variants[:12]):
                st.image(str(saved),width=380,caption=saved.name)
                st.download_button('Download '+saved.name,data=saved.read_bytes(),
                                   file_name=saved.name,mime='image/jpeg',
                                   key=f'mp_saved_{photo["id"]}_{index}')
