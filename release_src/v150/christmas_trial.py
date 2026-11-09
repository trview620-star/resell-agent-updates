"""Single-product Christmas trial: one offer, one illustration, one draft.

No publishing, purchasing, stock claims, fabricated resale values, or recurring tasks.
"""
from __future__ import annotations
from datetime import date
import io
import re
from pathlib import Path
from urllib.parse import urlsplit
import requests
from . import cloudflare_photos, shopping

PRODUCT={
    'brand':'MagicHome',
    'model':'8090234',
    'name':'MagicHome natúr adventi koszorú, piros, 25 cm (8090234)',
    'category':'Karácsonyi dekoráció',
    'source':'Grand Kupon',
    'source_url':'https://www.grandkupon.hu/magichome-natur-adventi-koszoru-piros-25-cm-8090234-147855',
    'price_huf_snapshot':2890,
    'shipping_huf_snapshot':2990,
    'snapshot_date':'2026-11-09',
}

def huf_price(value, currency=''):
    """Accept only explicitly HUF prices; never infer currency from a bare number."""
    if isinstance(value,(float,int)) and not isinstance(value,bool):
        if str(currency).upper() != 'HUF':return None
        return int(value) if 100<=value<=1_000_000 else None
    if not isinstance(value,str) or not re.search(r'(?i)\b(?:ft|huf)\b',value):
        return None
    m=re.search(r'(\d[\d .\u00a0\u202f,]*)(?:\s*)(?:ft|huf)\b',value,re.I)
    if not m:return None
    amount=m.group(1).strip().replace('\u00a0','').replace('\u202f','').replace(' ','')
    if re.search(r'[,.]\d\d$',amount):
        amount=re.sub(r'[,.]\d\d$','',amount)
    amount=re.sub(r'[.,]','',amount)
    if not amount.isdigit():return None
    parsed=int(amount)
    return parsed if 100<=parsed<=1_000_000 else None

def select_one_offer(payload):
    """Only an exact SKU match; other wreaths are not interchangeable products."""
    if not isinstance(payload,dict):return None
    results=payload.get('shopping') or payload.get('shopping_results') or []
    if not isinstance(results,list):return None
    choices=[]
    for result in results:
        if not isinstance(result,dict):continue
        title=str(result.get('title') or '')
        if not re.search(r'(?<!\d)8090234(?!\d)',title):continue
        if 'koszor' not in title.casefold() and 'wreath' not in title.casefold():continue
        link=result.get('link') or result.get('product_link')
        if not isinstance(link,str):continue
        parsed=urlsplit(link)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:continue
        try:
            from .research import valid_public_url
            if not valid_public_url(link):continue
        except ImportError:continue
        displayed=result.get('price')
        price=huf_price(displayed, result.get('currency',''))
        if price is None:
            currency=str(result.get('currency',''))
            # Bare numeric extracted price allowed ONLY when response explicitly says HUF.
            price=huf_price(result.get('extractedPrice'),currency)
        if price is None:continue
        store=str(result.get('source') or result.get('merchant') or parsed.hostname)[:100]
        choices.append({'title':PRODUCT['name'],'merchant':store,'url':link,
             'price_huf':price,'shipping_huf':None,'source_status':'Google Shopping search result — verify checkout price and shipping'})
    return min(choices,key=lambda x:x['price_huf']) if choices else None

def reference_offer():
    return {'title':PRODUCT['name'],'merchant':PRODUCT['source'],
      'url':PRODUCT['source_url'],'price_huf':PRODUCT['price_huf_snapshot'],
      'shipping_huf':PRODUCT['shipping_huf_snapshot'],
      'source_status':'Historical example from '+PRODUCT['snapshot_date']+
        ' — not a live quote. Check seller page before purchasing.'}

def find_one_offer(serper_key=''):
    key=str(serper_key or '').strip()
    if not key:
        return reference_offer(),'No Serper API key: using a dated example quote, not current price.'
    shopping.reserve_call()
    try:
        r=requests.post('https://google.serper.dev/shopping',
            headers={'X-API-KEY':key,'Content-Type':'application/json'},
            json={'q':'MagicHome 8090234 adventi koszorú piros 25 cm','gl':'hu','hl':'hu','num':10},
            timeout=(5,20))
        r.raise_for_status()
        result=select_one_offer(r.json())
    except (requests.RequestException,ValueError):
        result=None
    if result:
        return result,'Live shopping search result found, but stock, delivery and checkout price are unverified.'
    return reference_offer(),'No exact-code HUF result from Serper: showing the dated source example instead.'

def photo_prompt():
    return (
        'Produce ONE realistic photograph as a visual Christmas-decor concept, not a '
        'collage, not multiple products, no caption or overlay. Subject: a natural '
        '25 cm red-themed Advent wreath decoration with evergreen-looking natural '
        'elements, small red ornaments and warm festive details, resting on an ordinary '
        'wood kitchen table near soft daylight in a lived-in Hungarian home. Casual '
        'human smartphone photograph, slight background blur, realistic shadows and '
        'non-studio composition. Do not show candles, lights, extra packaged products '
        'or accessories unless necessarily part of a basic wreath. Do not attempt to '
        'fabricate exact MagicHome 8090234 branding, labels or authenticity. '
        'This is an illustrative concept, not a photo of the retailer SKU.'
    )

def generate_one_photo(account_id,token,model_label='FLUX.2 Klein 4B (more free generations)'):
    import requests as _requests
    import re as _re
    if not isinstance(account_id,str) or not _re.fullmatch(r'[a-fA-F0-9]{32}',account_id.strip()):
        raise ValueError('Enter your Cloudflare Account ID (32 hex characters).')
    if not isinstance(token,str) or len(token.strip())<10:
        raise ValueError('Enter a Cloudflare Workers AI API token.')
    if model_label not in cloudflare_photos.MODELS:
        raise ValueError('Unknown model.')
    url=cloudflare_photos.BASE+account_id.strip()+'/ai/run/'+cloudflare_photos.MODELS[model_label]
    # Even text-only Klein requests MUST be multipart/form-data.
    fields={'prompt':(None,photo_prompt()),'width':(None,'1024'),'height':(None,'768')}
    try:
        response=_requests.post(url,headers={'Authorization':'Bearer '+token.strip()},
                     files=fields,timeout=(10,180))
    except _requests.RequestException as e:
        raise ValueError('Could not contact Cloudflare.') from e
    if response.status_code in (401,403):raise ValueError('Cloudflare rejected the API token or account permissions.')
    if response.status_code==429:raise ValueError('Cloudflare rate limit or daily free allowance exceeded.')
    if response.status_code in (402,409):raise ValueError('Cloudflare model may require billing or account activation.')
    if response.status_code==400:
        raise ValueError('Cloudflare HTTP 400: '+cloudflare_photos._safe_provider_error(response,account_id,token))
    if not response.ok:raise ValueError('Cloudflare image generation failed (HTTP '+str(response.status_code)+').')
    return cloudflare_photos._decode_response(response)

def hungarian_draft():
    return (
       'MagicHome natúr adventi koszorú, piros, 25 cm (8090234)\n\n'
       'Hagyományos, natúr jellegű karácsonyi dekoráció piros díszítéssel, '
       '25 cm-es méretben. Ünnepi hangulatú asztali vagy ajtódísz. '
       'Cikkszám: 8090234.\n\n'
       'Megjegyzés: tervezet. A konkrét termék állapota, készlete, '
       'tartozékai, szállítási ideje és végső ára ellenőrzendő. '
       'Az AI-kép szemléltető illusztráció, nem a tényleges eladó termék fotója.'
    )

def purchase_cost_known(offer):
    price=offer.get('price_huf')
    shipping=offer.get('shipping_huf')
    if not isinstance(price,int) or price<=0:return None
    if not isinstance(shipping,int):return None
    return price+shipping
