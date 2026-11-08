"""Integrated operations dashboard. All external publishing is explicit/authorized."""
from __future__ import annotations
import json
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus
import streamlit as st
from . import db, opportunities, event_radar, publisher, local_ai, photo_studio
from .backup import make_backup

def money(n):
    return f"{int(n or 0):,} Ft".replace(',', ' ')

def selector(products, key):
    if not products:
        st.info('Add or import a product first.')
        return None
    choices={p['id']:p for p in products}
    selected=st.selectbox('Product',list(choices),
        format_func=lambda i:f"#{i} · {choices[i]['title']}",key=key)
    return choices[selected]

def _research(products):
    st.subheader('Opportunity intelligence')
    st.caption('Combines saved supplier quotes, manually verified resale comparisons and costs. No fabricated market prices.')
    m1,m2,m3=st.columns(3)
    min_profit=m1.number_input('Minimum profit (HUF)',0,1000000,3000,step=500)
    margin=m2.slider('Minimum margin (%)',0,80,15)
    all_results=opportunities.rank_database(min_profit=int(min_profit),min_margin_pct=int(margin))
    m3.metric('Qualified for review',sum(r['status']=='Qualified for review' for r in all_results))
    if not all_results:
        st.info('There are no products yet. Start in Product finder or Live shopping search.')
        return
    selected_status=st.multiselect('Show statuses',[
        'Qualified for review','Needs evidence','Reject / pause'],
        default=['Qualified for review','Needs evidence','Reject / pause'])
    filtered=[r for r in all_results if r['status'] in selected_status]
    if filtered:
        st.dataframe([{'ID':r['product_id'],'Product':r['title'],'Score':r['score'],
            'Decision':r['status'],'Supplier cost':money(r['supplier_total_huf']),
            'Market estimate':money(r['suggested_price_huf']) if r['suggested_price_huf'] else 'Unverified',
            'Profit estimate':money(r['projected_profit_huf']),
            'Margin':f"{r['margin_pct']}%",'Completed-sale comps':r['completed_comps'],
            'Stock':r['stock_status'],'Warnings':len(r['warnings'])} for r in filtered],
            hide_index=True,use_container_width=True)
        by_id={r['product_id']:r for r in filtered}
        identifier=st.selectbox('Inspect scoring evidence',list(by_id),
            format_func=lambda i:f"#{i} · {by_id[i]['title']}")
        item=by_id[identifier]
        st.write('**Evidence:** '+item['evidence'])
        if item['warnings']:
            st.warning('\n'.join('• '+w for w in item['warnings']))
        else:st.success('Minimum evidence and profit checks passed. Review product and marketplace requirements before listing.')
        if item['supplier_url']:
            st.markdown(f"[Inspect supplier link]({item['supplier_url']})")
        events=db.rows('SELECT * FROM events ORDER BY event_date')
        product=next(p for p in products if p['id']==identifier)
        matches=event_radar.candidate_event_matches(product,events)
        if matches:
            st.info('Upcoming event keyword matches (not measured demand): '+', '.join(e['name'] for e in matches))
    st.divider()
    st.subheader('Workflow overview')
    st.write('Supplier research → resale evidence → profit screening → listing drafts → verified publication → order tracking.')
    st.caption('Shopping and resale searches remain in their dedicated pages. This screen unifies evidence without extra paid API calls.')

def _studio(products):
    st.subheader('Photo studio and local AI')
    p=selector(products,'hub_studio_product')
    if p is None:return
    photos=db.rows('SELECT * FROM photos WHERE product_id=? ORDER BY id DESC',(p['id'],))
    if photos:
        photo=st.selectbox('Original photo',photos,format_func=lambda x:x['original_name'],
            key='hub_studio_photo')
        path=db.PHOTOS/photo['filename']
        if path.is_file():
            st.image(str(path),caption='Original photo preserved',width=420)
            a,b,c=st.columns(3)
            bright=a.slider('Brightness',0.80,1.40,1.10,0.01)
            contrast=b.slider('Contrast',0.80,1.30,1.06,0.01)
            sharp=c.slider('Sharpness',0.80,1.40,1.03,0.01)
            if st.button('Save an enhanced copy'):
                try:
                    output=photo_studio.improve_light(photo['id'],bright,contrast,sharp)
                    st.success('Enhanced version saved without changing original')
                    st.image(str(output),caption='Separate enhanced copy',width=420)
                except (ValueError,OSError) as e:st.error(str(e))
    else:st.info('Upload an original photo from Add product.')
    st.divider()
    status=local_ai.model_status()
    st.write('**Local Ollama:** '+'Connected' if status['connected'] else '**Local Ollama:** Not connected')
    st.caption('The GTX 1080 has 8 GB VRAM. Choose a compact compatible vision model; monitor system memory.')
    if status['connected']:
        st.caption('Available models: '+(', '.join(status['models'][:12]) or 'none'))
    model=st.text_input('Ollama model',value=local_ai.MODEL)
    if p['brand'] or p['model']:
        query=quote_plus(' '.join(filter(None,[p['brand'],p['model'],p['title']])))
        st.markdown('[Find model reference photos](https://www.google.com/search?tbm=isch&q='+query+')')
    if photos and st.button('Analyze original photo',disabled=not status['connected']):
        try:
            st.json(local_ai.analyze_photo(db.PHOTOS/photo['filename'],model))
            st.caption('AI claims are suggestions. Verify before publishing.')
        except ValueError as e:st.error(str(e))
    facts=st.text_area('Verified product facts',value=p['description'] or p['title'],
        key='hub_verified_facts')
    if st.button('Generate natural Hungarian description',disabled=not status['connected']):
        try:st.session_state['hub_generated_description']=local_ai.draft_description(facts,model)
        except ValueError as e:st.error(str(e))
    if st.session_state.get('hub_generated_description'):
        draft=st.text_area('Review generated description',value=st.session_state['hub_generated_description'],height=180)
        if st.button('Save reviewed text to product'):
            db.update_product(p['id'],description=draft)
            st.success('Description saved')

def _publish(products):
    st.subheader('Multi-marketplace publishing center')
    st.caption('One product → seven tailored listing drafts and portable ZIP export. Live publishing requires a configured official integration.')
    st.dataframe([{'Marketplace':m,'Available publishing mode':publisher.MODES[m]} for m in db.PLATFORMS],
        use_container_width=True,hide_index=True)
    p=selector(products,'hub_publish_product')
    if p is None:return
    markets=st.multiselect('Create packages for',list(db.PLATFORMS),default=list(db.PLATFORMS))
    st.warning('Review product facts, condition, rights to product images and supplier availability before publication.')
    if st.button('Prepare listing drafts',disabled=not bool(markets)):
        result=publisher.prepare_drafts(p['id'],markets)
        st.success(f'Prepared {len(result)} listing records; existing records reused.')
    if markets:
        content=publisher.listing_package(p['id'],markets)
        st.download_button('Download all chosen listing packets (ZIP)',content,
            file_name=f'resell_product_{p["id"]}.zip',mime='application/zip')
    with st.expander('Optional eBay official Inventory API — advanced, manual submission'):
        st.info('Requires eBay OAuth user token, active merchant location, business policies and HTTPS images. Use sandbox first.')
        listing=db.row('SELECT * FROM listings WHERE product_id=? AND marketplace="eBay" ORDER BY id DESC LIMIT 1',(p['id'],))
        if not listing:st.caption('Prepare an eBay draft above first.')
        else:
            with st.form('hub_ebay_form'):
                env=st.selectbox('API environment',['sandbox','production'])
                token=st.text_input('OAuth seller token',type='password')
                col1,col2=st.columns(2)
                with col1:
                    sku=st.text_input('SKU',value=f'rs-{p["id"]}')
                    category=st.text_input('Category ID')
                    condition=st.text_input('Condition',value='NEW')
                    location=st.text_input('Merchant location key')
                    marketplace=st.text_input('Marketplace ID',value='EBAY_DE')
                with col2:
                    currency=st.text_input('Currency',value='EUR')
                    price=st.text_input('Price in selected currency')
                    payment=st.text_input('Payment policy ID')
                    returns=st.text_input('Return policy ID')
                    fulfillment=st.text_input('Fulfillment policy ID')
                images=st.text_area('Public image URLs (one per line)')
                aspects=st.text_area('Category aspects JSON',value='{"Brand": ["Example"]}')
                checked=st.checkbox('I verified all fields, seller account permissions, photos, price and availability')
                submit=st.form_submit_button('Submit to eBay API',disabled=not checked)
            if submit:
                try:
                    response=publisher.EbayInventory(token,env).publish(
                        sku=sku,title=listing['title'],description=listing['description'],
                        price=price,currency=currency,category_id=category,condition=condition,
                        merchant_location_key=location,marketplace_id=marketplace,
                        payment_policy_id=payment,return_policy_id=returns,
                        fulfillment_policy_id=fulfillment,
                        image_urls=[x.strip() for x in images.splitlines() if x.strip()],
                        aspects=json.loads(aspects))
                    st.success('eBay API response received')
                    st.json(response)
                    st.info('Verify the live eBay listing URL before marking the listing published.')
                except (ValueError,TypeError) as e:st.error(str(e))

def _operations(products):
    st.subheader('Orders, account capacity and reliability')
    active=db.rows('SELECT * FROM orders WHERE status NOT IN ("delivered","cancelled","refunded") ORDER BY created_at DESC')
    listings=db.rows('SELECT * FROM listings ORDER BY created_at DESC')
    alerts=opportunities.fulfillment_flags(active,listings)
    urgent=[a for a in alerts if a['severity']=='urgent']
    cols=st.columns(3)
    cols[0].metric('Open orders',len(active))
    cols[1].metric('Urgent actions',len(urgent))
    cols[2].metric('Cross-list / delivery warnings',len(alerts))
    if alerts:st.dataframe(alerts,hide_index=True,use_container_width=True)
    else:st.success('No order deadline or cross-list warnings in saved records.')
    accounts=db.rows('SELECT * FROM accounts ORDER BY marketplace,label')
    if accounts:
        result=[]
        for a in accounts:
            live=sum(1 for l in listings if l['account_id']==a['id'] and l['status']=='published')
            capacity=a['max_active']
            result.append({'Marketplace':a['marketplace'],'Account':a['label'],
                'Status':a['status'],'Active':live,
                'Known limit':capacity if capacity is not None else 'Not entered',
                'Remaining':max(0,capacity-live) if capacity is not None else 'Unknown'})
        st.subheader('Account capacity')
        st.dataframe(result,use_container_width=True,hide_index=True)
    st.divider()
    st.subheader('Event radar')
    upcoming=[]
    for ev in db.rows('SELECT * FROM events ORDER BY event_date'):
        try:days=(date.fromisoformat(ev['event_date'])-date.today()).days
        except (TypeError,ValueError):continue
        if 0<=days<=90:
            upcoming.append({'Event':ev['name'],'Date':ev['event_date'],'Days away':days,
                             'Product ideas':ev['product_ideas']})
    if upcoming:st.dataframe(upcoming,hide_index=True,use_container_width=True)
    else:st.caption('No upcoming events recorded. Add events in the Event Radar page.')
    if st.button('Create complete backup now'):
        try:st.success('Created '+make_backup().name)
        except (OSError,ValueError) as e:st.error(str(e))
    st.divider()
    st.subheader('Integration status')
    st.dataframe([
        {'Capability':'Supplier feeds / scheduled monitoring','Status':'Implemented for configured compatible sources'},
        {'Capability':'Serper Shopping / public resale leads','Status':'Connected only when API key supplied'},
        {'Capability':'Profitability ranking / evidence','Status':'Implemented; verified sold comparisons required'},
        {'Capability':'Seven tailored listing packets','Status':'Implemented'},
        {'Capability':'Local photo enhancement and Ollama','Status':'Optional on-device tools'},
        {'Capability':'eBay Inventory API','Status':'Opt-in; requires authorized seller OAuth/configuration'},
        {'Capability':'Other marketplace automatic publication','Status':'Not connected'},
        {'Capability':'Automatic order detection / supplier purchasing','Status':'Not connected'},
    ],use_container_width=True,hide_index=True)

def render_hub(products):
    st.title('Resell Agent — Command Center')
    tabs=st.tabs(['Opportunities','Photo + AI','Listing publisher','Operations + Events'])
    with tabs[0]:_research(products)
    with tabs[1]:_studio(products)
    with tabs[2]:_publish(products)
    with tabs[3]:_operations(products)
