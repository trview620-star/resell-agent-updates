"""Review public listing leads before saving as asking-price comparables."""
from __future__ import annotations
import os
import streamlit as st
from . import db, resale_search
from .research import valid_public_url


def render_resale_search(products):
    st.title('Resale marketplace search')
    st.caption('Look for publicly indexed listings on our seven marketplaces using Serper. Results are leads, not verified completed sales.')
    st.info('Search snippets may contain outdated, missing or unrelated prices. Open the original listing before using a price.')
    key = os.getenv('SERPER_API_KEY', '').strip() or st.session_state.get('serper_shopping_api_key', '')
    if not key:
        key = st.text_input('Serper API key', type='password', key='resale_api_key')
    product_by_id = {p['id']: p for p in products}
    selected_id = st.selectbox('Attach comparables to product',
        [0] + list(product_by_id),
        format_func=lambda i: 'Search without saving' if i == 0 else f"#{i} — {product_by_id[i]['title']}")
    with st.form('search_public_resale'):
        phrase = st.text_input('Exact product/model search',
            value=(product_by_id[selected_id]['title'] if selected_id else ''),
            placeholder='LEGO Technic 42154')
        market = st.selectbox('Marketplace', list(resale_search.DOMAIN))
        go = st.form_submit_button('Search listings', disabled=not bool(key))
    if go:
        try:
            with st.spinner('Searching public listings...'):
                results = resale_search.search_marketplace(phrase, market, key)
            st.session_state['resale_market_leads'] = results
            st.session_state['resale_search_identity'] = (phrase, market)
            st.success(f'Found {len(results)} possible listing leads. This is not proof of a sale.')
        except ValueError as exc:
            st.session_state['resale_market_leads'] = []
            st.error(str(exc))
    results = st.session_state.get('resale_market_leads', [])
    if not results:
        return
    active_phrase, active_market = st.session_state.get('resale_search_identity', ('', ''))
    st.caption(f'Searched: {active_phrase} · {active_market}')
    st.dataframe([{
        'Title': r['title'], 'Marketplace': r['marketplace'],
        'Possible asking price': f"{r['price_huf']:,} Ft" if r['price_huf'] else 'Unknown',
        'Evidence': r['price_status'], 'URL': r['url']
    } for r in results], use_container_width=True, hide_index=True)
    idx = st.selectbox('Inspect listing', range(len(results)),
        format_func=lambda i: f"{results[i]['title'][:70]} · {results[i]['marketplace']}")
    item = results[idx]
    st.markdown(f"[Open original listing to verify condition and price]({item['url']})")
    st.write(item['snippet'] or 'No snippet provided')
    st.warning('Web search cannot verify current availability, the final checkout price, or whether any buyer paid this amount.')
    if selected_id == 0:
        st.info('Select a saved product above if you want to save a verified comparable.')
        return
    with st.form('save_public_asking_comp'):
        amount = st.number_input('Price verified on the original listing (HUF)',
            min_value=0, max_value=100000000, value=int(item['price_huf'] or 0), step=100)
        condition = st.text_input('Verified condition and exact variant',
            placeholder='LEGO 42154 full set, complete, used')
        notes = st.text_input('Verification notes',
            value='Public search lead; manually verified asking price, not a completed sale.')
        confirm = st.checkbox('I opened the original link and verified product, condition and asking price')
        save = st.form_submit_button('Save as asking-price comparable')
    if save:
        if not confirm:
            st.error('Please open and verify the original listing before saving.')
        elif not amount or not condition.strip():
            st.error('Enter a verified price and condition.')
        elif not valid_public_url(item['url']):
            st.error('Invalid public listing URL.')
        else:
            db.add_resale_comparable(selected_id, marketplace=item['marketplace'],
                url=item['url'], price_huf=int(amount), completed_sale=False,
                condition_text=condition.strip(), notes=notes)
            st.success('Asking-price comparable saved to Product research lab. It is NOT a completed sale.')
    st.caption('For verified completed sales, use the Product research lab with documented sale evidence.')
