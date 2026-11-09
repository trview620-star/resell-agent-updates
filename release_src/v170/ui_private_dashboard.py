"""Personal dark workspace for Resell Agent. Real records, no marketing and no fake KPIs."""
from __future__ import annotations

from html import escape
from urllib.parse import quote_plus
import streamlit as st

from . import (db, hunter, market_intelligence, shopping, supplier_links,
               listing_previews, private_research as rules)


def money(value):
    return (f"{int(value):,} Ft".replace(',',' ') if value is not None else '—')


def navigate(page):
    # Sidebar widget state cannot be changed after the widget is instantiated.
    st.session_state['_resell_next_page']=page
    st.rerun()


def _post_settings(zip_code):
    with st.expander('Pest vármegyei szállítási cím beállítása',expanded=not bool(zip_code)):
        with st.form('private_postcode_form'):
            chosen=st.text_input('Kiszállítási irányítószám',value=zip_code,
                                 max_chars=4,placeholder='pl. 2112')
            confirmed=st.checkbox('A megadott cím Pest vármegyében van')
            submit=st.form_submit_button('Irányítószám mentése',type='primary')
        if submit:
            try:
                rules.save_postcode(chosen,confirmed)
                st.success('Célirányítószám elmentve.')
                st.rerun()
            except ValueError as err:
                st.error(str(err))


def _top_controls(zip_code):
    st.markdown('<div class="private-heading">'
                '<div><div class="private-overline">SAJÁT MUNKATERÜLET</div>'
                '<h1>Resell Agent <span>Dashboard</span></h1>'
                '<p>13 beszállító · Vinted és Jófogás · tényleges keresési eredmények</p></div>'
                '</div>',unsafe_allow_html=True)
    a,b,c,d=st.columns([3.2,1.2,1.5,1.1],gap='small')
    with a:
        st.text_input('Termék, márka, modell',placeholder='Pl. LEGO, Sony, Nintendo…',
                      key='private_search',label_visibility='collapsed')
    with b:
        st.markdown('<div class="private-chip">📍 Pest: '+escape(zip_code or 'nincs beállítva')+'</div>',
                    unsafe_allow_html=True)
    with c:
        st.markdown('<div class="private-chip">🚚 Max. 4 munkanap</div>',
                    unsafe_allow_html=True)
    with d:
        if st.button('Frissítés',key='private_data_refresh',width='stretch'):
            st.rerun()
    st.markdown('<div class="private-kicker">Minimum tervezett profit: '
                '<strong>+4 000 Ft</strong> minden igazolt költség után'
                '</div>',unsafe_allow_html=True)


def _metrics(items,ship,costs,code,listings):
    metrics=rules.shortlist_metrics(items,ship,costs,code)
    vinted=sum(x['marketplace']=='Vinted' for x in listings)
    jofogas=sum(x['marketplace']=='Jófogás' for x in listings)
    rows=[
       ('Kutatási jelöltek',str(len(items)),'Vizsgálható termékmodellek'),
       ('Ellenőrzött keresések',str(metrics['checked']),'Serper Shopping'),
       ('13 boltos ajánlat',str(metrics['with_offers']),'Legalább egy ajánlat'),
       ('4 napos igazolás',str(metrics['fast']),'24 órán belüli ellenőrzés'),
       ('Kész ajánlat',str(metrics['ready']),'Szállítás + összes költség'),
       ('Hirdetésrekordok',f'{vinted} / {jofogas}','Vinted / Jófogás')
    ]
    cols=st.columns(6,gap='small')
    for col,(title,value,caption) in zip(cols,rows):
        with col:
            with st.container(border=True):
                st.caption(title)
                st.markdown('<div class="private-kpi">'+escape(value)+'</div>',
                            unsafe_allow_html=True)
                st.caption(caption)


def _status(item,shipping,costs,code):
    if rules.is_ready(item,shipping,costs,code):
        return 'Költség + szállítás ellenőrizve'
    offers=item['private_offers']
    if not offers:return 'Még nincs beszállítói ajánlat'
    if any(rules.delivery_state(shipping.get(o['id']),code)=='slow' for o in offers):
        return '4 munkanapnál hosszabb ajánlat'
    if any(rules.delivery_state(shipping.get(o['id']),code)=='ok' for o in offers):
        return 'Költségellenőrzés szükséges'
    return 'Szállítás ellenőrizendő'


def _listing_row(item,selected,shipping,costs,code):
    offer=item.get('best_offer')
    with st.container(border=True):
        c1,c2,c3,c4=st.columns([.85,2.45,1.55,.7],gap='small',
                               vertical_alignment='center')
        with c1:
            image=item.get('thumbnail')
            if image:
                st.image(image,width='stretch')
            else:
                st.caption('Nincs katalóguskép')
        with c2:
            st.markdown('**'+escape(item['phrase'][:95])+'**')
            st.caption(item['category']+' · '+_status(item,shipping,costs,code))
        with c3:
            st.caption(offer['registered_supplier'] if offer else 'Nincs ár')
            st.markdown('**'+money(offer['price_huf']) if offer else '**Beszerzés: —**')
            if offer:
                proof=rules.delivery_state(shipping.get(offer['id']),code)
                st.caption({'ok':'✓ 4 munkanapon belül',
                            'slow':'Kiszállítás >4 munkanap',
                            'stale':'Lejárt szállítási adat',
                            'unknown':'Szállítás nem igazolt'}[proof])
        with c4:
            if st.button('Részletek',key='private_item_'+str(item['id']),
                         type='primary' if selected else 'secondary',
                         width='stretch'):
                st.session_state['private_selected_phrase']=item['phrase']
                st.rerun()


def _market_links(phrase):
    query=quote_plus(phrase)
    st.markdown('**Keresési diagnosztikák**')
    rows=st.columns(2,gap='small')
    links=[
      ('Google Trends','https://trends.google.com/trends/explore?geo=HU&q='+query),
      ('Vinted árak','https://www.vinted.hu/catalog?search_text='+query),
      ('Jófogás kínálat','https://www.jofogas.hu/magyarorszag?q='+query),
      ('eBay Sold','https://www.ebay.de/sch/i.html?_nkw='+query+'&LH_Sold=1&LH_Complete=1'),
    ]
    for i,(label,url) in enumerate(links):
        with rows[i%2]:
            st.link_button(label,url,width='stretch')
    st.caption('Ezek közvetlen ellenőrzési linkek. '
               'Nem jelentik azt, hogy a piacterek eladási vagy keresési számait '
               'a rendszer automatikusan lekérte.')


def _quote_details(offer,costs,shipping,code):
    if not offer:
        return
    st.markdown('**Fix 4 000 Ft-os árazás**')
    quote_v=rules.price_quote(offer['price_huf'],costs.get((offer['id'],'Vinted')))
    quote_j=rules.price_quote(offer['price_huf'],costs.get((offer['id'],'Jófogás')))
    a,b=st.columns(2)
    with a:
        st.caption('Vinted · számított hirdetési ár')
        st.markdown('### '+money(quote_v['sale_huf'] if quote_v else None))
    with b:
        st.caption('Jófogás · számított hirdetési ár')
        st.markdown('### '+money(quote_j['sale_huf'] if quote_j else None))
    if not quote_v and not quote_j:
        st.info('Az eladási ár az összes költség ellenőrzése után számítható. '
                'Nem használunk feltételezett 0 Ft-os szállítást.')
    else:
        st.caption('Az árban a pontosan 4 000 Ft tervezett, adózás előtti '
                   'profit szerepel, a rögzített költségek alapján.')
    proof=rules.delivery_state(shipping.get(offer['id']),code)
    colors={'ok':'green','slow':'red','stale':'orange','unknown':'gray'}
    captions={'ok':'Igazolt: legfeljebb 4 munkanap',
              'slow':'Nem teljesíti a 4 munkanapos célt',
              'stale':'A szállítási bizonyíték elavult',
              'unknown':'Termékenkénti szállítás nincs igazolva'}
    st.caption(captions[proof])


def _detail_panel(item,shipping,costs,code):
    if not item:
        st.info('Válassz egy terméket a listából.')
        return
    offer=item.get('best_offer')
    with st.container(border=True):
        st.caption('KIVÁLASZTOTT TERMÉK')
        if item.get('thumbnail'):
            colpic,coltitle=st.columns([1,2.4],gap='small',
                                       vertical_alignment='center')
            with colpic:st.image(item['thumbnail'],width='stretch')
            with coltitle:
                st.markdown('### '+escape(item['phrase']))
                st.caption(item['category']+' · '+str(item['score'])+' kutatási pont')
        else:
            st.markdown('### '+escape(item['phrase']))
            st.caption('A pontos termékfotó még nem érhető el.')
        st.divider()
        a,b=st.columns(2)
        a.metric('Kereskedők a 13-ból',item['supplier_count'])
        b.metric('Legalacsonyabb ajánlat',money(offer['price_huf'] if offer else None))
        if offer:
            st.caption('Beszállító: '+escape(offer['registered_supplier']))
            dest,is_direct=supplier_links.navigable(
                offer['url'],offer['title'],offer['merchant'])
            st.link_button('Beszállítói oldal megnyitása' if is_direct
                           else 'Beszállító keresése',dest,width='stretch')
            if not is_direct:
                st.caption('A találat csak keresési hivatkozás, nem ellenőrzött termékoldal.')
            _quote_details(offer,costs,shipping,code)
            if st.button('Költség + szállítás ellenőrzése',
                         key='private_go_delivery',width='stretch'):
                st.session_state['private_selected_offer']=offer['id']
                navigate('Szállítási ellenőrzés')
        else:
            st.warning('A 13 kiválasztott beszállító egyikétől sincs még '
                       'elfogadott Shopping-ajánlat. A kutatási pont nem eladási statisztika.')
        st.divider()
        _market_links(item['phrase'])
        if offer:
            markets=st.multiselect('Piszkozat készítése',list(rules.MARKETS),
                                   default=list(rules.MARKETS),
                                   key='private_draft_markets')
            if st.button('Mentés a kiválasztottakhoz és piszkozatok',
                         key='private_prepare',type='primary',
                         disabled=not bool(markets),width='stretch'):
                try:
                    result=hunter.prepare(offer['id'],markets,
                                          use_ai=False,auto_photo=False)
                    st.success('Mentve: '+str(len(result['drafts']))+' helyi piszkozat.')
                    st.rerun()
                except (ValueError,RuntimeError) as err:
                    st.error(str(err))
            st.caption('A piszkozatkészítés nem vásárol és nem tesz közzé hirdetést.')


def _selection(items):
    chosen=st.session_state.get('private_selected_phrase','')
    if any(i['phrase']==chosen for i in items):
        return next(i for i in items if i['phrase']==chosen)
    return items[0] if items else None


def _research_workspace(items,shipping,costs,code,ready_only=False):
    tab=st.radio('Termékcsoport',('Összes jelölt','Szállítás ellenőrzött',
                                'Teljesen előkészített','Még nincs bolti ajánlat'),
                 horizontal=True,key='private_group')
    left,right=st.columns([1.9,1],gap='medium')
    query=st.session_state.get('private_search','').casefold().strip()
    offers=[i for i in items if not query or query in i['phrase'].casefold()]
    with left:
        st.markdown('#### '+('Ajánlott termékek' if ready_only else 'Termékfigyelés'))
        f1,f2=st.columns([1,1],gap='small')
        cats=['Mind']+list(market_intelligence.SOURCES)
        with f1:cat=st.selectbox('Kategória',cats,key='private_cat')
        with f2:
            store=st.selectbox('Beszállító',['Mind']+[s[0] for s in rules.SUPPLIERS],
                               key='private_store')
        offers=[i for i in offers if (cat=='Mind' or i['category']==cat)]
        if store!='Mind':
            offers=[i for i in offers if
                    any(o['registered_supplier']==store for o in i['private_offers'])]
        if ready_only or tab=='Teljesen előkészített':
            offers=[i for i in offers if rules.is_ready(i,shipping,costs,code)]
        elif tab=='Szállítás ellenőrzött':
            offers=[i for i in offers if
                    any(rules.delivery_state(shipping.get(o['id']),code)=='ok'
                        for o in i['private_offers'])]
        elif tab=='Még nincs bolti ajánlat':
            offers=[i for i in offers if not i['private_offers']]
        st.caption(f'{len(offers)} termék · kizárólag 13 beszállító · '
                   'az adatok nem jelentenek automatikusan eladási bizonyítékot')
        if not offers:
            st.info('A választott szűrőhöz még nincs megfelelő, igazolt adat. '
                    'Indíts keresést a Termékfigyelés oldalon, vagy módosítsd a szűrőt.')
        pages=max(1,(len(offers)+7)//8)
        page=st.number_input('Találati oldal',1,pages,1,key='private_list_page')
        selected=_selection(offers)
        for item in offers[(page-1)*8:page*8]:
            _listing_row(item,selected and item['phrase']==selected['phrase'],
                         shipping,costs,code)
    with right:
        st.markdown('#### Termék részletei')
        _detail_panel(_selection(offers),shipping,costs,code)


def _delivery_page(items,shipping,costs,code):
    st.title('Szállítási ellenőrzés')
    st.caption('Csak konkrét termékhez és megadott Pest vármegyei irányítószámhoz '
               'ellenőrzött határidőt fogadunk el. A 4 nap munkanap.')
    _post_settings(code)
    alloffers=[(it,o) for it in items for o in it['private_offers']]
    if not alloffers:
        st.info('Nincsenek mentett ajánlatok a 13 beszállítótól. '
                'Előbb ellenőrizz termékeket a Termékfigyelés fülön.')
        return
    choices={o['id']:(it,o) for it,o in alloffers}
    ids=list(choices)
    selected_default=st.session_state.pop('private_selected_offer',None)
    if selected_default in choices:
        st.session_state['private_delivery_choice']=selected_default
    chosen=st.selectbox('Termék és beszállító',ids,
                        format_func=lambda x:choices[x][0]['phrase'][:60]+' · '+
                        str(choices[x][1]['registered_supplier']),
                        key='private_delivery_choice')
    item,offer=choices[chosen]
    dest,direct=supplier_links.navigable(offer['url'],offer['title'],offer['merchant'])
    st.link_button('Termékoldal / szállítási ígéret megnyitása',dest)
    if not direct:st.caption('Nem közvetlen termékoldal; ellenőrizd a pontos változatot.')
    current=shipping.get(chosen)
    state=rules.delivery_state(current,code)
    st.caption('Legutóbbi státusz: '+{
        'ok':'4 munkanapon belül, manuálisan igazolva',
        'slow':'4 munkanapnál hosszabb',
        'stale':'Lejárt az ellenőrzés (24 óránál régebbi)',
        'unknown':'Nincs megfelelő bizonyíték'}[state])
    if not code:
        st.warning('Előbb mentsd a célirányítószámot.')
    with st.form('private_delivery_form'):
        days=st.number_input('Termékhez vállalt maximum munkanap',
                             min_value=0,max_value=60,
                             value=int(current['max_workdays']) if current else 4)
        evidence=st.text_input('Bizonyíték: kosárban látott dátum vagy kézbesítési feltétel',
                               value=current['evidence_note'] if current else '')
        checked=st.checkbox('A pontos terméket, irányítószámot és szállítási módot ellenőriztem')
        save=st.form_submit_button('Ellenőrzés mentése',type='primary')
    if save:
        try:
            rules.save_delivery(chosen,code,int(days),evidence,checked)
            st.success('Kézbesítési ellenőrzés rögzítve.')
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    st.markdown('#### Összes költség és fix hirdetési ár')
    market=st.radio('Piactér',rules.MARKETS,horizontal=True,key='private_pricing_market')
    saved=costs.get((chosen,market)) or {}
    defaults=(saved.get('inbound_huf',0),saved.get('outbound_huf',0),
              saved.get('packing_huf',0),saved.get('fees_huf',0),
              saved.get('reserve_huf',0))
    with st.form('private_costs_form'):
        cols=st.columns(3)
        inbound=cols[0].number_input('Beszállítói szállítás (Ft)',min_value=0,value=defaults[0])
        outbound=cols[1].number_input('Általunk fizetett továbbküldés (Ft)',
                                      min_value=0,value=defaults[1])
        packing=cols[2].number_input('Csomagolás (Ft)',min_value=0,value=defaults[2])
        d,e=st.columns(2)
        fees=d.number_input('Platformdíj (Ft)',min_value=0,value=defaults[3])
        reserve=e.number_input('Egyéb költség és tartalék (Ft)',min_value=0,value=defaults[4])
        confirmed=st.checkbox('Minden minket terhelő költséget ellenőriztem '
                              '(a 0 Ft is tudatosan megadott érték)')
        submit=st.form_submit_button('Költségek mentése és ár számítása',type='primary')
    if submit:
        try:
            rules.save_costs(chosen,market,int(inbound),int(outbound),
                             int(packing),int(fees),int(reserve),confirmed)
            st.success('Ár: '+money(
                rules.price_quote(offer['price_huf'],{
                    'inbound_huf':inbound,'outbound_huf':outbound,
                    'packing_huf':packing,'fees_huf':fees,
                    'reserve_huf':reserve})['sale_huf']))
            st.rerun()
        except ValueError as exc:st.error(str(exc))
    _quote_details(offer,costs,shipping,code)
    st.caption('A webshopoknál megjelenő szállítási dátumok automatikus, '
               'irányítószám-függő kiolvasása még nem egységes. '
               'Ez a modul ellenőrizhető, kézzel jóváhagyott adatokat tárol; '
               'nem állítja, hogy a webshop élő kosarát lekérte.')


def _suppliers_page(items):
    st.title('Beszállítók · 13 webshop')
    st.caption('Csak ezeknek a kereskedőknek az ajánlatait rangsoroljuk a '
               'személyes munkaterületen. A raktárkészletet és a kézbesítést '
               'mindig a pontos terméknél kell ellenőrizni.')
    count={name:0 for name,_,_ in rules.SUPPLIERS}
    for item in items:
        for offer in item['private_offers']:
            count[offer['registered_supplier']]+=1
    for start in range(0,len(rules.SUPPLIERS),3):
        cols=st.columns(3,gap='small')
        for col,(name,domain,_) in zip(cols,rules.SUPPLIERS[start:start+3]):
            with col:
                with st.container(border=True):
                    st.markdown('### '+escape(name))
                    st.caption(str(count[name])+' mentett ajánlat a Top 50 modellhez')
                    st.link_button('Webshop megnyitása','https://www.'+domain,width='stretch')


def _diagnostics_page(items):
    st.title('Keresési diagnosztikák')
    st.caption('Ellenőrzési linkek és valós, mentett kereskedői árak. '
               'Nincs kitalált keresésszám, eladás vagy piacrészesedés.')
    chosen=_selection(items)
    if not chosen:
        st.info('Még nincsenek termékjelöltek.')
        return
    opts={i['phrase']:i for i in items}
    phrase=st.selectbox('Termék',list(opts),index=list(opts).index(chosen['phrase']))
    item=opts[phrase]
    _market_links(phrase)
    st.markdown('**Google Shopping – mentett ajánlatok a 13 webshopból**')
    if not item['private_offers']:
        st.info('Ehhez a modellhez még nincs kereskedői ajánlat.')
    for offer in item['private_offers'][:12]:
        supplier=escape(offer['registered_supplier'])
        st.markdown('• '+supplier+' · '+money(offer['price_huf'])+
                    ' · '+escape(offer['title'][:105]))
    st.caption('A Vinted/Jófogás hirdetési adatait és az eBay Sold eredményeit '
               'külön ellenőrizd; az aktív hirdetés nem bizonyított eladás.')


def _saved_page():
    st.title('Kiválasztott termékek')
    rows=db.rows("""SELECT h.*,p.title AS product_title
                    FROM hunter_results h JOIN products p ON p.id=h.product_id
                    WHERE h.status IN ('selected','prepared')
                    ORDER BY h.selected_at DESC,h.id DESC LIMIT 120""")
    if not rows:
        st.info('Még nincs kiválasztott termék. Nyiss meg egy ajánlatot a Dashboardon.')
        return
    for r in rows[:36]:
        with st.container(border=True):
            a,b,c=st.columns([1,3,1.2],gap='medium')
            with a:
                img=listing_previews.primary(r['product_id'],hunter_id=r['id'])
                if img:st.image(img['image'],width='stretch')
            with b:
                st.markdown('**'+escape(r['product_title'])+'**')
                st.caption(escape(r['merchant'])+' · '+r['status'])
            with c:
                if st.button('Részletes szerkesztés',key='private_selected_'+str(r['id'])):
                    st.session_state['hunter_selected_id']=r['id']
                    st.session_state['hunter_active_view']='Kiválasztottak'
                    navigate('Termékfigyelés')


def _market_page(market,listings):
    st.title(market+' · hirdetések')
    subset=[x for x in listings if x['marketplace']==market]
    st.caption('A saját mentett piszkozatok és hirdetésrekordok. '
               'Az adatok nem igazolják az élő piactéri közzétételt.')
    if not subset:
        st.info('Nincs még '+market+'-hirdetési rekord.')
        if st.button('Termékfigyelés megnyitása',key='private_market_hunt'):
            navigate('Termékfigyelés')
    else:
        for row in subset[:40]:
            with st.container(border=True):
                a,b,c=st.columns([.75,3,1.25],gap='small')
                with a:
                    img=listing_previews.primary(row['product_id'])
                    if img:st.image(img['image'],width='stretch')
                with b:
                    st.markdown('**'+escape(row['product_name'])+'**')
                    st.caption(row['status']+' · '+money(row['price']))
                with c:
                    if st.button('Szerkesztés',key='private_market_edit_'+str(row['id']),
                                 width='stretch'):
                        st.session_state['listing_edit_id']=row['id']
                        navigate('Listing manager')


def render(page,products=None,listings=None):
    rules.initialize()
    items=rules.candidates()
    zip_code=rules.postcode()
    shipping=rules.delivery_records(zip_code)
    costs=rules.cost_records()
    listings=listings if listings is not None else []
    if page in ('Dashboard','Ajánlott termékek'):
        _top_controls(zip_code)
        _metrics(items,shipping,costs,zip_code,listings)
        if not zip_code:
            st.warning('Add meg a Pest vármegyei célirányítószámot, hogy '
                       'a beszállítói szállítási feltételeket hozzá lehessen kötni.')
            _post_settings(zip_code)
        _research_workspace(items,shipping,costs,zip_code,
                            ready_only=page=='Ajánlott termékek')
        st.caption('A fix 4 000 Ft profit kalkulált, adózás előtti eredmény; '
                   'nem garantált eladás. A kutatási pont nem keresleti darabszám.')
    elif page=='Beszállítók':
        _suppliers_page(items)
    elif page=='Szállítási ellenőrzés':
        _delivery_page(items,shipping,costs,zip_code)
    elif page=='Keresési diagnosztikák':
        _diagnostics_page(items)
    elif page=='Kiválasztott termékek':
        _saved_page()
    elif page in rules.MARKETS:
        _market_page(page,listings)
    else:
        raise ValueError('Ismeretlen személyes munkaterület: '+str(page))
