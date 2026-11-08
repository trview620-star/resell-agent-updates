"""Public resale listing research using a marketplace-specific Serper search.

Organic snippets are NOT verified resale prices or completed sales.
"""
from __future__ import annotations
import re
from urllib.parse import urlsplit
import requests
from . import shopping
from .research import valid_public_url, huf_amount

DOMAIN = {
    'Vinted': 'vinted.hu', 'Facebook Marketplace': 'facebook.com',
    'Jófogás': 'jofogas.hu', 'Vatera': 'vatera.hu',
    'HardverApró': 'hardverapro.hu', 'eBay': 'ebay.com',
    'Amazon': 'amazon.de',
}
HUF_PRICE = re.compile(r'(?<![\\w])([0-9][0-9\\s\\u00a0\\u202f.,]*?)\\s*(?:Ft|HUF)\\b', re.I)


def extract_single_huf_price(text: str):
    if not isinstance(text, str) or not text.strip():
        return None
    values = []
    for hit in HUF_PRICE.finditer(text):
        price = huf_amount(hit.group(1).strip())
        if price and price >= 100:
            values.append(price)
    distinct = set(values)
    return next(iter(distinct)) if len(distinct) == 1 else None


def normalize_organic(payload: dict, phrase: str, marketplace: str):
    if marketplace not in DOMAIN:
        raise ValueError('Unknown marketplace')
    if not isinstance(payload, dict) or not isinstance(payload.get('organic'), list):
        raise ValueError('No recognizable organic search results')
    domain = DOMAIN[marketplace]
    output = []
    seen = set()
    model = shopping.model_code_from_phrase(phrase)
    for r in payload['organic'][:40]:
        if not isinstance(r, dict):
            continue
        url = r.get('link') or r.get('url')
        title = r.get('title')
        if not isinstance(url, str) or not isinstance(title, str) or not valid_public_url(url):
            continue
        host = (urlsplit(url).hostname or '').lower().rstrip('.')
        if not (host == domain or host.endswith('.' + domain)):
            continue
        if marketplace == 'Facebook Marketplace' and '/marketplace/' not in url:
            continue
        if url in seen:
            continue
        seen.add(url)
        if model:
            status, reason = shopping.classify_product_match(title, phrase)
            if status != 'Model code matches':
                continue
        else:
            status, reason = 'Keyword only', 'Verify model identity manually'
        snippet = str(r.get('snippet') or '')[:800]
        price = extract_single_huf_price(title + ' ' + snippet)
        output.append({
            'title': title[:220], 'url': url, 'snippet': snippet,
            'price_huf': price, 'model_status': status,
            'marketplace': marketplace, 'price_status':
            'Unverified snippet price' if price else 'Price unavailable or ambiguous'
        })
    return output


def search_marketplace(phrase: str, marketplace: str, api_key: str, timeout: int = 18):
    phrase = shopping._valid_phrase(phrase)
    if marketplace not in DOMAIN:
        raise ValueError('Unknown marketplace')
    if not api_key.strip():
        raise ValueError('Serper API key required')
    shopping.reserve_call()
    query = f'site:{DOMAIN[marketplace]} {phrase}'
    try:
        res = requests.post(
            'https://google.serper.dev/search',
            json={'q': query, 'gl': 'hu', 'hl': 'hu', 'num': 10},
            headers={'X-API-KEY': api_key.strip(), 'Content-Type': 'application/json'},
            timeout=(5, timeout)
        )
        res.raise_for_status()
        payload = res.json()
    except (requests.RequestException, ValueError) as exc:
        raise ValueError('Marketplace search failed. Check Serper credits and connection.') from exc
    if not isinstance(payload, dict):
        raise ValueError('Unexpected Serper response')
    if payload.get('error') or (payload.get('message') and 'organic' not in payload):
        raise ValueError('Provider error: ' + str(payload.get('error') or payload.get('message'))[:140])
    return normalize_organic(payload, phrase, marketplace)
