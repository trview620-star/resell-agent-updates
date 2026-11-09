"""Clean Top 50 research workspace and a separate one-query custom search."""
from __future__ import annotations
from html import escape
from urllib.parse import quote_plus
import streamlit as st
from . import market_intelligence as intelligence, supplier_links, hunter, shopping, db, radar_previews

def money(value):
    return f'{int(value):,} Ft'.replace(',',' ') if value else 'Még nincs adat'

def _diagnostics(phrase):
    col1,col2,col3=st.columns(3,gap='small')
    with col1:
        st.link_button('Google Trends · HU',
             'https://trends.google.com/trends/explore?geo=HU&q='+quote_plus(phrase),
             use_container_width=True)
    with col2:
        st.link_button('eBay · eladott termékek',
            'https://www.ebay.de/sch/i.html?_nkw='+quote_plus(phrase)+'&LH_Sold=1&LH_Complete=1',
            use_container_width=True)
    with col3:
        st.link_button('Vinted · keresés',
            'https://www.vinted.hu/catalog?search_text='+quote_plus(phrase),
            use_container_width=True)
    st.caption('Ezek ellenőrzési lehetőségek. Az alkalmazás nem állítja, hogy '
               'lekérte a Vinted belső keresésszámait vagy az eBay eladott darabszámait.')

def _merchant_rows(offers,markets,cloud_id,cloud_token,use_ai,prefix):
    if not offers:
        st.info('Ehhez a kereséshez még nincs forintáras, modellhez illeszkedő ajánlat.')
        return
    st.caption(f'{len(offers)} tárolt kereskedői ajánlat. Ár és készlet vásárlás előtt ellenőrizendő.')
    for o in offers[:20]:
        thumbnail=radar_previews.normalize_thumbnail(o.get('thumbnail'))
        label, is_direct=supplier_links.navigable(
            o.get('url'),o.get('title'),o.get('merchant'))
        with st.container(border=True):
            photo,a,b=st.columns([.8,3.35,1.45],gap='medium')
            with photo:
                if thumbnail:
                    st.image(thumbnail,width='stretch')
                    st.caption('Katalóguskép')
                else:
                    st.caption('Nincs kép')
            with a:
                st.markdown('**'+escape(o['title'][:140])+'**')
                st.caption(escape(o['merchant'])+' · '+money(o['price_huf']))
                if is_direct:
                    st.link_button('Kereskedő termékoldala ↗',label)
                else:
                    st.link_button('Termék keresése a kereskedőnél ↗',label)
                    st.caption('Nem találtunk közvetlen termékoldalt. '
                               'Ez Google-keresés, nem ellenőrzött beszállítói ajánlat.')
            with b:
                if o['status']=='new':
                    if st.button('Kiválasztom',key=prefix+'_'+str(o['id']),
                                 use_container_width=True,type='primary'):
                        try:
                            hunter.prepare(o['id'],markets,account=cloud_id,
                                           token=cloud_token,use_ai=use_ai)
                            st.success('Piszkozatok előkészítve.')
                            st.rerun()
                        except (ValueError,RuntimeError) as e:
                            st.error(str(e))
                else:
                    st.caption('Már elmentve')

def render_top50(key,cloud_id,cloud_token,markets,use_ai):
    items=intelligence.shortlisted()
    checked=sum(bool(x['checked_at']) for x in items)
    with st.container(border=True):
        st.markdown('### Piaci lehetőségek · Top 50')
        st.caption('50 konkrét kutatási jelölt magyar vásárlási és keresési '
                   'kategóriaadatok alapján. A pontos modellek eladásai NINCSENEK '
                   'automatikusan igazolva. Az élő beszállítói adatok külön jelennek meg.')
        a,b,c,d=st.columns(4)
        a.metric('Kutatási jelöltek','50')
        b.metric('Ellenőrzött kulcsszavak',f'{checked}/50')
        c.metric('Kereskedői árakat mutató',sum(bool(x['offers']) for x in items))
        d.metric('API-keret',f'{shopping.current_usage()}/{shopping.MONTHLY_LIMIT}')
        st.progress(checked/50)
    st.markdown('#### Termékfigyelés')
    actions=st.columns([1,1,1.25,1.8])
    count=actions[0].selectbox('Keresések száma',[5,10,20,50],
                               index=1,key='radar_batch_size')
    expensive=actions[1].checkbox('50 lekérés engedélyezése',
                                   value=False,key='radar_allow50') if count==50 else True
    if actions[2].button('Következő jelöltek ellenőrzése',
                          disabled=not key or not expensive,
                          type='primary',use_container_width=True):
        chosen=intelligence.next_unchecked(count)
        progress=st.progress(0)
        report=[]
        for i,item in enumerate(chosen):
            report.append(intelligence.scan_keyword(key,item['phrase'],item['category']))
            progress.progress((i+1)/len(chosen))
            if shopping.current_usage()>=shopping.MONTHLY_LIMIT:break
        st.session_state['radar_last_batch']=report
        st.rerun()
    with actions[3]:
        st.caption('Egy ellenőrzés = egy Serper Shopping lekérés / modell. '
                   'A Google Trends, Vinted és eBay adatait nem találja ki a rendszer.')
    if not key:
        st.info('Az élő árakhoz add meg a Serper API-kulcsot a Beállításokban. '
                'A 50 kutatási jelölt addig is böngészhető.')
    if st.session_state.get('radar_last_batch'):
        report=st.session_state['radar_last_batch']
        st.caption(f'Legutóbbi ellenőrzés: {len(report)} kifejezés · '
                   f'{sum(x.get("found",0) for x in report)} ár- és linktalálat.')
        errors=[x['phrase']+': '+x['error'] for x in report if x.get('error')]
        if errors:
            with st.expander('Keresési problémák'):
                st.write(' | '.join(errors[:10]))
    filters=st.columns([1,2])
    categories=['Mind']+list(intelligence.SOURCES)
    category=filters[0].selectbox('Kategória',categories,key='radar_category')
    query=filters[1].text_input('Szűrés termék alapján',key='radar_filter',
              placeholder='Pl. LEGO, AirPods, Nintendo…')
    view=[p for p in items if
          (category=='Mind' or p['category']==category) and
          (not query or query.casefold() in p['phrase'].casefold())]
    display=st.radio('Termékek megjelenítése',
                     ['Táblázat képekkel','Képes termékkártyák'],
                     horizontal=True,key='radar_display_mode')
    if display=='Táblázat képekkel':
        st.dataframe([{
            'Kép':row.get('thumbnail') or None,
            'Pont':row['score'],'Termék':row['phrase'],
            'Kategória':row['category'],
            'Kereskedő':row['retailers'],
            'Beszerzési ár (Ft)':row['lowest_huf'],
            'Ellenőrzés':row['checked_at'][:10] if row['checked_at'] else 'Még nem'
        } for row in view],
        column_config={
            'Kép':st.column_config.ImageColumn(
                'Kép',help='Beszállítói Shopping-katalóguskép, nem saját fotó',
                width='small'),
            'Termék':st.column_config.TextColumn('Termék',width='large'),
            'Pont':st.column_config.NumberColumn('Pont',width='small'),
            'Beszerzési ár (Ft)':st.column_config.NumberColumn(
                'Beszerzési ár (Ft)',format='%d Ft')
        },
        hide_index=True,use_container_width=True,height=535,row_height=82)
    else:
        if view:
            per_page=12
            total_pages=(len(view)+per_page-1)//per_page
            page=st.number_input('Képes oldal',min_value=1,max_value=total_pages,
                                 value=1,key='radar_photo_page')
            visible=view[(page-1)*per_page:page*per_page]
            for offset in range(0,len(visible),4):
                columns=st.columns(4,gap='small')
                for column,item in zip(columns,visible[offset:offset+4]):
                    with column:
                        with st.container(border=True):
                            if item.get('thumbnail'):
                                st.image(item['thumbnail'],width='stretch')
                            else:
                                st.caption('Nincs még ellenőrzött termékkép.')
                            st.markdown('**'+escape(item['phrase'])+'**')
                            st.caption(item['category']+' · Pont: '+str(item['score']))
                            st.caption('Legolcsóbb ajánlat: '+money(item['lowest_huf']))
                            if st.button('Részletek',key='radar_photo_open_'+str(item['id']),
                                         width='stretch'):
                                st.session_state['radar_chosen_product']=item
                                st.rerun()
    st.caption('A képek a beszállítói keresési találatokból származnak, '
               'nem a saját termékfotóid. A még nem ellenőrzött termékeknél '
               'a Kép mező üres maradhat; futtasd a termékellenőrzést.')
    st.caption('A „Pont” kutatási prioritás, NEM várható eladási esély. '
               'A 2025/2026-os kutatások kategóriaadatok; a legolcsóbb '
               'megjelenített ár nem bizonyítottan nyereséges beszerzés.')
    if not view:return
    chosen=st.selectbox('Termék részletei',view,format_func=lambda x:x['phrase'],
                         key='radar_chosen_product')
    with st.container(border=True):
        photo,details=st.columns([1.1,3.4],gap='medium')
        with photo:
            if chosen.get('thumbnail'):
                st.image(chosen['thumbnail'],width='stretch')
                st.caption('Beszállítói termékkép – előnézet')
            else:
                st.info('Ehhez a termékhez még nincs képes ajánlat.')
        with details:
            st.markdown('### '+escape(chosen['phrase']))
            c1,c2,c3=st.columns(3)
            c1.metric('Kutatási pont',chosen['score'])
            c2.metric('Kereskedők',chosen['retailers'])
            c3.metric('Legolcsóbb találat',money(chosen['lowest_huf']))
        st.caption('Alátámasztás: '+chosen['source'])
        st.link_button('Kategóriaadat forrása ↗',chosen['source_url'])
        if chosen['error']:st.warning('Utolsó ellenőrzés hibája: '+chosen['error'])
        if chosen['offers']<2:
            st.info('A kereslet/verseny/árrés még nem bizonyított. '
                    'Eladási összehasonlítás és több ajánlat kell a döntéshez.')
        else:
            st.caption('A különböző kereskedők ajánlatai árversenyt jeleznek, '
                       'nem bizonyítják, hogy milyen áron kel el a termék.')
        _diagnostics(chosen['phrase'])
        found_offers=intelligence.offers_for(chosen['phrase'])
        images=radar_previews.offer_images(found_offers,limit=4)
        if images:
            with st.expander('Kereskedői termékfotók ('+str(len(images))+')',
                             expanded=False):
                photo_cols=st.columns(len(images),gap='small')
                for col,image in zip(photo_cols,images):
                    with col:
                        st.image(image['image'],width='stretch')
                        st.caption(image['merchant'][:45])
                st.caption('Ezek katalógusfotók; az állapotot és tartozékokat '
                           'külön ellenőrizd.')
        st.markdown('**Beszállítói árak és termékoldalak**')
        _merchant_rows(found_offers,markets,
                       cloud_id,cloud_token,use_ai,'radar_select')

def render_custom(key,cloud_id,cloud_token,markets,use_ai):
    st.markdown('### Saját termékötlet keresése')
    st.caption('Bármikor beírhatsz egy saját modellt vagy kulcsszót. '
               'Ez nem cseréli le a Top 50 listát, csak 1 új keresést indít.')
    phrase=st.text_input('Termék vagy modell',placeholder='pl. LEGO Ideas 21366',
                          key='radar_custom_keyword')
    if st.button('Saját keresés indítása',type='primary',
                 disabled=not bool(key and phrase.strip()),
                 key='radar_custom_search'):
        try:
            response=intelligence.scan_keyword(key,phrase,'Saját keresés')
            st.session_state['radar_custom_last']=response['phrase']
            if response['error']:st.error(response['error'])
            else:st.success(f"{response['found']} termékajánlat mentve.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    active=st.session_state.get('radar_custom_last')
    if active:
        st.markdown('#### '+escape(active))
        _diagnostics(active)
        _merchant_rows(intelligence.offers_for(active),markets,
                       cloud_id,cloud_token,use_ai,'custom_select')
