"""UI for source-faithful shots alongside existing optional AI illustrations."""
from __future__ import annotations

import streamlit as st

from . import db, photo_shot_plan, source_photo_series
from .photos import save_photo

SCENE_LABELS={
    'gaming_headset':'Gamer-/íróasztal, monitor közeli szoba – ne konyha',
    'gaming_accessory':'Otthoni íróasztal vagy PC-kuckó',
    'lego':'Polc, komód vagy természetes otthoni asztal',
    'boardgame':'Nappali asztal vagy társasjátékos sarok',
    'kitchen':'Konyhapult / étkező',
    'clothes':'Hálószoba, szekrény vagy egyszerű textilháttér',
    'other':'Termékhez illő, hétköznapi otthoni környezet',
}


def render(product_id,hunter_id,title):
    pid=int(product_id)
    prefix='source_series_'+str(pid)+'_'
    category=photo_shot_plan.category(title)

    with st.container(border=True):
        st.markdown('### <font color="#6ee3cb">Termékhű képsorozat</font>',unsafe_allow_html=True)
        st.caption('A termék eredeti képpontjaiból készülő vágások: '
                   'logó, betűk, rajzok és jelölések újragenerálása nélkül. '
                   'Nem készül kitalált doboz, tartozék vagy láthatatlan kameraállás.')
        st.info('Javasolt eredeti fotóhelyszín: '+SCENE_LABELS[category])

        originals=db.rows('SELECT id FROM photos WHERE product_id=?',(pid,))
        st.caption(f'Feltöltött saját forrásfotók: {len(originals)}. '
                   'A különböző szögekhez valódi, más helyzetből készült képek szükségesek.')

        with st.expander('Saját fotók hozzáadása (a legjobb minőséghez)',expanded=not bool(originals)):
            uploads=st.file_uploader(
                'Termék, részletek és valódi doboz fotói',
                type=['jpg','jpeg','png','webp'],accept_multiple_files=True,
                key=prefix+'source_uploads')
            st.caption('A feltöltött képek változatlanul is megmaradnak. '
                       'A dobozfotó fájlneve tartalmazhatja: doboz vagy box.')
            if st.button('Saját fotók mentése',key=prefix+'store_uploads',
                         disabled=not bool(uploads)):
                added=0
                for photo in uploads or []:
                    try:
                        added+=int(save_photo(pid,photo.name,photo.getvalue()))
                    except ValueError as error:
                        st.error(f'{photo.name}: {error}')
                if added:
                    st.success(f'{added} eredeti kép mentve.')
                    st.rerun()

        current=source_photo_series.read(pid)
        if current and originals and not any(p['status']=='approved' for p in current):
            if st.button('Katalógusképek cseréje saját fotókra / sorozat újrakészítése',
                         key=prefix+'rebuild_originals',width='stretch'):
                try:
                    source_photo_series.create(pid,hunter_id=hunter_id,replace_existing=True)
                    st.success('Az új forrásfotókból készült képsorozat.')
                    st.rerun()
                except (ValueError,OSError) as error:
                    st.error(str(error))
        if not current:
            st.caption('Nincs termékhű képsorozat. '
                       'Az első létrehozás nem használ AI-képgenerálási keretet.')
        if st.button('4 termékhű képelőnézet létrehozása',
                     key=prefix+'create',type='primary',
                     disabled=bool(current)):
            try:
                result=source_photo_series.create(pid,hunter_id=hunter_id)
                st.success(f"{len(result['created'])} kép elkészült – nézd át őket.")
                st.rerun()
            except (ValueError,OSError) as error:
                st.error(str(error))

        current=source_photo_series.read(pid)
        if current:
            for offset in range(0,len(current),2):
                subset=current[offset:offset+2]
                if not subset:continue
                columns=st.columns(2,gap='medium')
                for col,item in zip(columns,subset):
                    slot=item['slot']
                    with col:
                        with st.container(border=True):
                            st.markdown(f"**{slot}/4 · {item['role']}**")
                            if item['bytes']:
                                st.image(item['bytes'],width='stretch')
                            else:
                                st.warning('A forráskivágás fájlja hiányzik.')
                            origin=('Saját fotóból – változatlan képpontok'
                                    if item['source_type']=='original' else
                                    'Katalógusképből – nem saját fotó')
                            st.caption(origin)
                            st.caption(item['note'])
                            if item['status']=='approved':
                                st.success('Jóváhagyva a hirdetés-előnézethez')
                            elif item['status']=='rejected':
                                st.warning('Elutasítva – frissítheted a kivágást')
                            elif item['source_type']=='catalogue':
                                st.info('Ez csak beszállítói előnézet. '
                                        'Saját, valódi termékfotóként nem hagyható jóvá.')
                            else:
                                if st.button('Kép jóváhagyása',
                                             key=prefix+f'approve_{slot}',
                                             disabled=not bool(item['bytes']),
                                             width='stretch'):
                                    try:
                                        source_photo_series.approve(pid,slot)
                                        st.rerun()
                                    except ValueError as error:
                                        st.error(str(error))
                            if item['status']!='approved':
                                if slot==1:
                                    if st.button('Főkép frissítése az aktuális forrásból',
                                                 key=prefix+'refresh_main'):
                                        try:
                                            source_photo_series.create(
                                                pid,hunter_id=hunter_id,
                                                only_slots=[1],replace_existing=True)
                                            st.rerun()
                                        except (ValueError,OSError) as error:
                                            st.error(str(error))
                                if slot in (2,3,4):
                                    with st.expander('Kivágás módosítása',expanded=False):
                                        x=st.slider('Vízszintes fókusz (%)',0,100,
                                                   62 if slot==2 else 32 if slot==3 else 68,
                                                   5,key=prefix+f'x_{slot}')
                                        y=st.slider('Függőleges fókusz (%)',0,100,
                                                   68 if slot==2 else 35 if slot==3 else 32,
                                                   5,key=prefix+f'y_{slot}')
                                        if st.button('Új képkivágás',
                                                     key=prefix+f'remake_{slot}'):
                                            try:
                                                source_photo_series.create(
                                                    pid,hunter_id=hunter_id,
                                                    only_slots=[slot],
                                                    replace_existing=True,
                                                    focuses={slot:(x/100,y/100)})
                                                st.rerun()
                                            except (ValueError,OSError) as error:
                                                st.error(str(error))
                                if st.button('Elutasítás',key=prefix+f'reject_{slot}'):
                                    source_photo_series.reject(pid,slot)
                                    st.rerun()
        st.caption('A termékhű módban nem cserélünk hátteret AI-val, '
                   'mert az megváltoztathatná a terméken lévő jelöléseket. '
                   'Az AI-illusztrációk ettől külön, manuálisan ellenőrizhetők.')
