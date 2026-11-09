"""Clean Top 50 research workspace and a separate one-query custom search."""
from __future__ import annotations
from html import escape
from urllib.parse import quote_plus
import streamlit as st
from . import market_intelligence as intelligence, supplier_links, hunter, shopping, db

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
        label, is_direct=supplier_links.navigable(
            o.get('url'),o.get('title'),o.get('merchant'))
        with st.container(border=True):
            a,b=st.columns([4,1.45],gap='medium')
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
    st.dataframe([{
        'Pont':row['score'],'Termék':row['phrase'],'Kategória':row['category'],
        'Kereskedő':row['retailers'],'Beszerzési ár (Ft)':row['lowest_huf'],
        'Ellenőrzés':row['checked_at'][:10] if row['checked_at'] else 'Még nem'
    } for row in view],hide_index=True,use_container_width=True,height=405)
    st.caption('A „Pont” kutatási prioritás, NEM várható eladási esély. '
               'A 2025/2026-os kutatások kategóriaadatok; a legolcsóbb '
               'megjelenített ár nem bizonyítottan nyereséges beszerzés.')
    if not view:return
    chosen=st.selectbox('Termék részletei',view,format_func=lambda x:x['phrase'],
                         key='radar_chosen_product')
    with st.container(border=True):
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
        st.markdown('**Beszállítói árak és termékoldalak**')
        _merchant_rows(intelligence.offers_for(chosen['phrase']),markets,
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
