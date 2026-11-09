"""Single-purpose demand-first research board for the 13 approved suppliers."""
from __future__ import annotations

from html import escape
from urllib.parse import quote_plus
import os
import streamlit as st

from . import demand_workbench as work, hunter, private_research as rules, shopping, supplier_links


def money(value):
    return (f'{int(value):,} Ft'.replace(',',' ') if value is not None else '—')


def _evidence_urls(phrase):
    query=quote_plus(phrase)
    return {
      'Google Trends':'https://trends.google.com/trends/explore?geo=HU&q='+query,
      'Google Shopping':'https://www.google.com/search?tbm=shop&q='+query,
      'Vinted':'https://www.vinted.hu/catalog?search_text='+query,
      'Jófogás':'https://www.jofogas.hu/magyarorszag?q='+query,
      'eBay Sold':'https://www.ebay.de/sch/i.html?_nkw='+query+'&LH_Sold=1&LH_Complete=1',
    }


def _lead_capture():
    st.markdown('### Új keresleti jel')
    phrase=st.text_input('Mit kerestek / vettek meg?',placeholder='Például pontos márka, modell vagy EAN',key='demand_new_phrase')
    if phrase.strip():
        st.link_button('eBay Sold keresés megnyitása','https://www.ebay.de/sch/i.html?_nkw='+quote_plus(phrase.strip())+'&LH_Sold=1&LH_Complete=1')
    with st.form('demand_evidence_form'):
        a,b,c=st.columns([1,1,1.3])
        with a:sold=st.number_input('Ténylegesen eladott darab',min_value=1,max_value=100000,value=1,step=1)
        with b:days=st.number_input('Vizsgált időszak (nap)',min_value=1,max_value=365,value=30,step=1)
        with c:median=st.number_input('eBay eladási medián (HUF, ha ismert)',min_value=0,max_value=100000000,value=0,step=500)
        evidence=st.text_input('eBay Sold bizonyíték linkje',placeholder='A szűrt eladott találatok URL-je')
        verified=st.checkbox('Ellenőriztem, hogy ezek ténylegesen eladott tételek, nem aktív hirdetések')
        saved=st.form_submit_button('Keresleti jel mentése',type='primary',width='stretch')
    if saved:
        try:
            row=work.save_lead(phrase,int(sold),int(days),int(median) or None,evidence,manually_verified=verified)
            st.session_state['demand_selected_id']=int(row['id'])
            st.success('Keresleti jel elmentve. Most lekérhetjük a 13 bolt beszállítói ajánlatait.')
            st.rerun()
        except ValueError as exc:st.error(str(exc))
    st.caption('Az eBay Sold adatait itt kézzel rögzíted. Az eBay tényleges eladási adatokat adó Marketplace Insights API-ja korlátozott hozzáférésű; a radar nem talál ki eladásszámokat.')


def _lead_card(lead,selected):
    candidates=work.supplier_candidates(lead['id'])
    image=next((x['thumbnail'] for x in candidates if x.get('thumbnail')),'')
    rate=30*int(lead['sold_units'])/max(1,int(lead['period_days']))
    with st.container(border=True):
        if image:
            st.image(image,width='stretch')
        else:
            st.markdown('<div class="demand-image-empty">⌕<br><small>Kép még nincs</small></div>',unsafe_allow_html=True)
        st.markdown('**'+escape(lead['phrase'])+'**')
        st.caption(f"{lead['sold_units']} eladva · {lead['period_days']} nap · {rate:.1f} / 30 nap")
        if candidates:
            st.caption(f"{len(candidates)} bolti találat · legolcsóbb keresési ár {money(candidates[0]['price_huf'])}")
        else:st.caption('Beszállítói keresés még nem futott')
        if st.button('Részletek',key='demand_open_'+str(lead['id']),type='primary' if selected else 'secondary',width='stretch'):
            st.session_state['demand_selected_id']=int(lead['id']);st.rerun()


def _api_key():
    key=os.getenv('SERPER_API_KEY','').strip() or st.session_state.get('demand_serper_key','').strip()
    if key:return key
    return st.text_input('Serper kulcs (csak ebben a böngésző-munkamenetben)',type='password',key='demand_serper_key_input')


def _supplier_search(lead):
    key=_api_key()
    checked=rules.postcode()
    with st.container(border=True):
        st.markdown('#### 01 · Kereslet → beszállítók')
        st.caption('Egy Google Shopping lekérdezés a keresési kifejezésre. Csak a jóváhagyott 13 webshop találatai kerülnek a listába; a találat önmagában nem igazol készletet vagy szállítást.')
        usage=shopping.current_usage()
        st.caption(f'Havi Shopping-keret: {usage} / {shopping.MONTHLY_LIMIT} lekérdezés')
        if st.button('Keresés mind a 13 boltban',key='demand_scan_'+str(lead['id']),type='primary',disabled=not bool(key),width='stretch'):
            try:
                with st.spinner('Beszállítói ajánlatok keresése…'):
                    result=work.scan_suppliers(lead['id'],key)
                st.session_state['demand_scan_result']=result
                if result.get('error'):st.warning(result['error'])
                else:st.success(f"Keresés kész · {result['found']} elfogadott bolti találat · {result['used_calls']} havi lekérdezés")
                st.rerun()
            except ValueError as exc:st.error(str(exc))
        if not key:st.info('A beszállítói kereséshez Serper API-kulcs szükséges.')
    return checked


def _verified_offer_form(lead,hits,postcode):
    st.markdown('#### 03 · Ajánlat és kézbesítés igazolása')
    if not hits:
        st.info('Futtasd le a beszállítói keresést; csak az egyező, 13 boltos találatokból lehet adatot igazolni.')
        return
    options={int(x['id']):x for x in hits}
    chosen=st.selectbox('Ellenőrzendő bolti találat',list(options),
      format_func=lambda i:f"{options[i]['supplier']} · {options[i]['title'][:75]} · {money(options[i]['price_huf'])}",
      key='demand_verify_hit_'+str(lead['id']))
    hit=options[chosen]
    target,direct=supplier_links.navigable(hit['url'],hit['title'],hit['merchant'])
    st.link_button('Találat megnyitása és ellenőrzése',target)
    if not direct:st.caption('A link csak Shopping-átirányítás. A mentéshez közvetlen termékoldalt adj meg.')
    with st.form('demand_offer_check_'+str(lead['id'])+'_'+str(chosen)):
        url=st.text_input('Közvetlen termékoldal URL-je',value=hit['url'] if direct else '')
        a,b,c=st.columns(3)
        with a:price=st.number_input('Ellenőrzött termékár (Ft)',min_value=1,max_value=100000000,value=int(hit['price_huf']),step=100)
        with b:shipping=st.number_input('Beszállítói szállítás (Ft)',min_value=0,max_value=10000000,value=0,step=100,help='A 0 Ft-ot is ellenőrizd; ne feltételezd automatikusan.')
        with c:stock=st.selectbox('Készletállapot',['unknown','available','unavailable'],format_func=lambda x:{'unknown':'Nem ellenőrzött','available':'Rendelhető','unavailable':'Nem rendelhető'}[x])
        d,e,f=st.columns(3)
        with d:postal=st.text_input('Cél-irányítószám',value=postcode or work.POSTCODE_DEFAULT,max_chars=4)
        with e:method=st.text_input('Szállítási mód',placeholder='Például házhozszállítás')
        with f:days=st.number_input('Legkésőbbi munkanap',min_value=0,max_value=60,value=4,step=1)
        guaranteed=st.checkbox('A webshop kifejezetten, a fenti címre és módra legfeljebb ennyi munkanapot vállal (nem becslés)')
        exact=st.checkbox('Ellenőriztem, hogy pontosan ugyanaz a márka és modell / EAN')
        note=st.text_input('Bizonyíték: hol ellenőrizted az árat, készletet és dátumot?')
        save=st.form_submit_button('Igazolt ajánlat mentése',type='primary')
    if save:
        try:
            work.save_supplier_check(lead['id'],chosen,url=url,price_huf=int(price),shipping_huf=int(shipping),
                stock_status=stock,postcode=postal,shipping_method=method,max_workdays=int(days),
                delivery_guaranteed=guaranteed,exact_match_confirmed=exact,evidence_note=note)
            st.success('Időbélyegzett beszállítói ellenőrzés mentve.')
            st.rerun()
        except ValueError as exc:st.error(str(exc))


def _detail(lead):
    st.markdown('### Kiválasztott keresleti termék')
    st.markdown('## '+escape(lead['phrase']))
    velocity=30*int(lead['sold_units'])/max(1,int(lead['period_days']))
    a,b,c=st.columns(3)
    a.metric('Tényleges eladások',str(lead['sold_units']),f"{lead['period_days']} nap alatt")
    b.metric('30 napra vetítve',f'{velocity:.1f}')
    c.metric('eBay sold medián',money(lead['ebay_median_huf']))
    st.link_button('eBay eladási bizonyíték megnyitása',lead['evidence_url'])
    st.caption('A 30 napos érték a rögzített eladásszámból számolt tempó, nem jövőbeli eladási ígéret.')
    links=_evidence_urls(lead['phrase'])
    st.markdown('#### 02 · Keresési diagnosztikák')
    st.caption('A kép- és adatkártyák ötletet adnak, de az aktív hirdetési árak nem bizonyítanak eladást.')
    panels=[('Google Trends','Keresési érdeklődés és trend','Google Trends'),
            ('Google Shopping','A 13 bolti ajánlat lekérése','Google Shopping'),
            ('Vinted','Aktív hirdetések és kínálati árak','Vinted'),
            ('Jófogás','Kiegészítő piaci összehasonlítás','Jófogás'),
            ('eBay Sold','Tényleges eladások, ha elérhetők','eBay Sold'),
            ('Ártörténet','Korábban kézzel igazolt ajánlatok','Ártörténet')]
    for offset in range(0,len(panels),2):
        cols=st.columns(2,gap='small')
        for col,(title,sub,key) in zip(cols,panels[offset:offset+2]):
            with col:
                if key=='Ártörténet':st.markdown('<div class="demand-diagnostic"><b>'+title+'</b><br><span>'+sub+'</span></div>',unsafe_allow_html=True)
                else:
                    st.link_button(title+' · '+sub,links[key],width='stretch')
    if lead['ebay_median_huf']:
        st.caption('eBay Sold medián: '+money(lead['ebay_median_huf'])+' · az eBay forrásoldaláról kézzel rögzítve.')

    postcode=_supplier_search(lead)
    hits=work.supplier_candidates(lead['id'])
    verified=work.verified_supplier_offers(lead['id'],postcode or work.POSTCODE_DEFAULT)
    st.markdown('#### 04 · Beszállítói ajánlatok')
    if verified:
        best=verified[0]
        st.success(f"Legalacsonyabb igazolt, rendelhető ajánlat: {best['supplier']} · {money(best['unit_price_huf'])} + {money(best['shipping_huf'])} szállítás = {money(best['total_huf'])} · vállalt {best['max_workdays']} munkanap")
    else:
        st.info('Még nincs friss, pontos modellre és irányítószámra igazolt, legfeljebb 4 munkanapos ajánlat.')
    if hits:
        for hit in hits:
            with st.container(border=True):
                pic,info=st.columns([.65,2.35],gap='small')
                with pic:
                    if hit.get('thumbnail'):st.image(hit['thumbnail'],width='stretch')
                    else:st.markdown('<div class="demand-image-empty">Kép<br><small>nincs adat</small></div>',unsafe_allow_html=True)
                with info:
                    st.markdown('**'+escape(hit['title'])+'**')
                    st.caption(f"{hit['supplier']} · {money(hit['price_huf'])} · {hit['confidence']} · Shopping-találat, készlet és szállítás nincs igazolva")
                    st.caption(hit['found_at'])
                    dest,direct=supplier_links.navigable(hit['url'],hit['title'],hit['merchant'])
                    st.link_button('Közvetlen termékoldal' if direct else 'Shopping-találat megnyitása',dest)
    else:
        st.caption('Ehhez a kereslethez még nincs megfelelő 13 boltos találat. Indíts Shopping-keresést.')
    _verified_offer_form(lead,hits,postcode or work.POSTCODE_DEFAULT)
    checks=work.recent_checks(lead['id'])
    if checks:
        with st.expander('Ellenőrzési és ártörténet',expanded=False):
            st.dataframe([{'Bolt':x['supplier'],'Ár':money(x['unit_price_huf']),'Szállítás':money(x['shipping_huf']),
                'Készlet':x['stock_status'],'Ígért munkanap':x['max_workdays'] if x['delivery_guaranteed'] else 'Nem igazolt',
                'Ellenőrizve':x['checked_at']} for x in checks],hide_index=True,width='stretch')


def render():
    work.initialize()
    st.markdown('<div class="demand-eyebrow">RESSELL AGENT · DEMAND RADAR</div>',unsafe_allow_html=True)
    st.title('A keresletből indulunk.')
    st.caption('Előbb bizonyítsd, mit vesznek meg. Utána keressük meg ugyanazt a 13 ellenőrzött beszállítónál.')
    with st.expander('Keresleti jel rögzítése az eBay Sold alapján',expanded=not bool(work.leads())):
        _lead_capture()
    all_leads=work.leads()
    left,right=st.columns([.92,1.65],gap='large')
    with left:
        st.markdown('### Keresleti radar')
        if not all_leads:
            st.markdown('<div class="demand-empty"><span>01</span><h3>Még nincs keresleti adat</h3><p>Nyiss meg egy eBay Sold keresést, rögzítsd a tényleges eladásokat, majd indíts beszállítói keresést.</p></div>',unsafe_allow_html=True)
        else:
            selected=st.session_state.get('demand_selected_id')
            if selected not in {int(x['id']) for x in all_leads}:
                selected=int(all_leads[0]['id']);st.session_state['demand_selected_id']=selected
            for lead in all_leads:
                _lead_card(lead,int(lead['id'])==int(selected))
    with right:
        if all_leads:
            selected=st.session_state.get('demand_selected_id',int(all_leads[0]['id']))
            lead=next((x for x in all_leads if int(x['id'])==int(selected)),all_leads[0])
            _detail(lead)
        else:
            st.markdown('<div class="demand-empty-side"><div class="orbit">↗</div><h3>Értékes termékek, valódi jelek alapján</h3><p>Rögzíts egy ellenőrzött eladási mintát, és a rendszer a 13 bolt készletében keres hozzá egyezést.</p><div class="demand-steps"><span>01 · Kereslet</span><span>02 · Termékegyezés</span><span>03 · Rendelhetőség</span></div></div>',unsafe_allow_html=True)
