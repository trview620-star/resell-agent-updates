"""Images alongside product and marketplace listing drafts.

Preference order: authentic seller uploads, approved illustrations, pending
illustrations, supplier catalogue thumbnails. Every source is labelled. No
catalogue photo or AI picture is silently promoted into an authentic image.
"""
from __future__ import annotations

from pathlib import Path
from . import db

MAX_PREVIEW_BYTES = 18_000_000


def _local_image(path):
    try:
        p=Path(path)
        if p.is_file() and 0<p.stat().st_size<=MAX_PREVIEW_BYTES:
            return str(p)
    except (OSError,ValueError,TypeError):
        return None
    return None


def sources(product_id, *, hunter_id=None, include_pending=True, limit=4):
    pid=int(product_id)
    if pid<=0:return []
    limit=max(1,min(int(limit),12))
    out=[]
    seen=set()

    def add(obj,label,kind):
        if obj is None or len(out)>=limit:return
        signature=obj if isinstance(obj,str) else (kind,len(obj),obj[:96])
        if signature in seen:return
        seen.add(signature)
        out.append({'image':obj,'label':label,'kind':kind})

    # Actual seller uploads are the only images we label as real product photos.
    for row in db.rows(
        'SELECT filename,original_name FROM photos WHERE product_id=? ORDER BY created_at,id',
        (pid,)):
        safe=Path(str(row['filename'])).name
        if safe!=row['filename']:continue
        img=_local_image(db.PHOTOS/safe)
        add(img,'Saját, feltöltött termékfotó','original')
        if len(out)>=limit:return out

    # Approved AI illustrations are separate from original photos in all exports.
    directory=db.DATA/'ai_previews'/str(pid)
    if directory.is_dir():
        for file in sorted(directory.glob('AI_ILLUSTRATIVE_*.png'),
                           key=lambda p:p.stat().st_mtime,reverse=True):
            add(_local_image(file),'Jóváhagyott AI-illusztráció','approved')
            if len(out)>=limit:return out

    # Only read pending AI files when explicitly requested for previews.
    # A pending image is never a photo supplied by the seller.
    if hunter_id is None:
        from . import hunter
        hunter.initialize()
        linked=db.row(
            "SELECT id,thumbnail FROM hunter_results WHERE product_id=? "
            "ORDER BY selected_at DESC,id DESC LIMIT 1",(pid,))
        hunter_id=linked['id'] if linked else None
    if hunter_id is not None:
        from . import stock_photo_gallery
        pictures=stock_photo_gallery.slots(int(hunter_id))
        if include_pending:
            for item in pictures:
                if item['status']=='pending' and item['bytes']:
                    add(item['bytes'],f"AI-előnézet · {item['slot']}/4",'pending')
                    if len(out)>=limit:return out
        row=db.row('SELECT thumbnail FROM hunter_results WHERE id=?',(int(hunter_id),))
        if row:
            from . import hunter
            url=hunter.safe_thumbnail(row['thumbnail'])
            if url:
                add(url,'Beszállítói katalóguskép · nem saját fotó','catalogue')
    return out


def primary(product_id, *, hunter_id=None):
    images=sources(product_id,hunter_id=hunter_id,limit=1)
    return images[0] if images else None


def image_or_placeholder(item, *, height=140, caption=True):
    """Use Streamlit's native image widget (no untrusted HTML)."""
    import streamlit as st
    if item:
        try:
            st.image(item['image'],width='stretch')
            if caption:st.caption(item['label'])
            return
        except (ValueError,OSError,TypeError):
            pass
    st.info('Nincs még fotó ehhez a termékhez.')


def render_selected_cards(rows,page_size=9):
    import streamlit as st
    if not rows:return
    st.markdown('#### Termékek képes előnézete')
    size=max(1,min(18,int(page_size)))
    maxpage=(len(rows)+size-1)//size
    page=st.number_input('Oldal · termékelőnézet',min_value=1,max_value=maxpage,
                         value=1,step=1,key='selected_picture_page')
    current=rows[(page-1)*size:page*size]
    for offset in range(0,len(current),3):
        columns=st.columns(3,gap='medium')
        for col,row in zip(columns,current[offset:offset+3]):
            with col:
                with st.container(border=True):
                    image_or_placeholder(primary(row['product_id'],hunter_id=row['id']))
                    st.markdown('**'+str(row['title'])[:115]+'**')
                    st.caption(str(row['merchant'])+' · '+
                        ('Piszkozat kész' if row['status']=='prepared' else 'Kiválasztva'))
                    if st.button('Megnyitom',key='selected_img_open_'+str(row['id']),
                                 width='stretch'):
                        st.session_state['hunter_selected_id']=row['id']
                        st.rerun()


def render_listing_cards(listings,page_size=9):
    import streamlit as st
    if not listings:return
    st.markdown('#### Hirdetések képes áttekintése')
    size=max(1,min(int(page_size),18))
    maxpage=(len(listings)+size-1)//size
    page=st.number_input('Oldal · hirdetéselőnézet',min_value=1,max_value=maxpage,
                         value=1,step=1,key='listing_picture_page')
    items=listings[(page-1)*size:page*size]
    for offset in range(0,len(items),3):
        columns=st.columns(3,gap='medium')
        for col,row in zip(columns,items[offset:offset+3]):
            with col:
                with st.container(border=True):
                    image_or_placeholder(primary(row['product_id']))
                    st.markdown('**'+str(row['product_name'])[:115]+'**')
                    st.caption(row['marketplace']+' · '+row['status'])
                    st.caption(
                        f"{int(row['price']):,} Ft".replace(',',' ')
                        if row['price'] else 'Ár még nincs megadva')
                    if st.button('Hirdetés szerkesztése',
                                 key='listing_img_open_'+str(row['id']),
                                 width='stretch'):
                        st.session_state['listing_edit_id']=row['id']
                        st.rerun()


def render_gallery(product_id, *, hunter_id=None, limit=4):
    import streamlit as st
    images=sources(product_id,hunter_id=hunter_id,include_pending=True,limit=limit)
    st.markdown('**Termékképek előnézete**')
    if not images:
        st.caption('Ehhez a hirdetéshez még nem került kép.')
        return
    for offset in range(0,len(images),4):
        columns=st.columns(min(4,len(images)-offset),gap='small')
        for col,item in zip(columns,images[offset:offset+4]):
            with col:image_or_placeholder(item)
    st.caption('Az AI-előnézetek és beszállítói katalógusképek '
               'nem igazolják a tényleges termék állapotát.')
