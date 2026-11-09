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

def hungarian_title():
    """Buyer-facing title: no internal SKU or technical metadata."""
    return 'Piros adventi koszorú – 25 cm'


def hungarian_draft():
    """Short, natural Hungarian sales copy based only on verified catalog facts."""
    return (
        'Natúr hatású adventi koszorú piros díszítéssel, 25 cm-es méretben. '
        'Jól mutat az ünnepi asztalon vagy egy komódon, és egy kis karácsonyi '
        'hangulatot visz a lakásba.\n\n'
        'Ha kérdésed van, írj nyugodtan.\n\n'
        'Hasonló termékekért nézd meg a többi hirdetésemet.'
    )


def photo_prompt(reference_used=False):
    """Favor an unpolished phone photo; a product image makes it more accurate."""
    if reference_used:
        return (
            'Use image 0 as the EXACT subject reference. Create ONE real-looking '
            'handheld phone photo of this SAME product resting on a plain, slightly '
            'used wooden table in an everyday Hungarian living room. '
            'Keep the wreath shape, size, decoration arrangement, red accent '
            'colors, materials and number of objects as close to the reference '
            'as possible. Change ONLY the white/catalog surroundings and adapt '
            'natural light and contact shadows. Do not add candles or accessories '
            'that are not in the reference. It must look like a normal person '
            'took a quick, reasonably sharp listing photo on a phone: natural '
            'ordinary daylight, slight framing imperfection, modest sharpness, '
            'a little sensor grain, ordinary room background gently out of focus. '
            'NO glossy commercial product render, NO cinematic lighting, NO '
            'perfect symmetry, NO extreme bokeh, NO artificial-looking sparkle, '
            'NO watermark, NO collage, NO caption.'
        )
    return (
        'Create ONE realistic casual smartphone photo, not a product advertisement. '
        'Subject: a modest 25 cm natúr-style Advent wreath with understated red '
        'Christmas decoration, placed on a real wooden dining table in an ordinary '
        'home, window daylight, slightly uneven lighting, believable contact shadows, '
        'a natural everyday room visible softly in the background. '
        'The wreath should look like a real simple shop-bought decoration, NOT a '
        'perfectly symmetrical luxurious AI fantasy. Keep realistic twig and '
        'foliage textures, small imperfections, subdued saturation, normal phone '
        'sharpness, subtle camera grain. NO shiny plastic render, NO dramatic '
        'cinematic lighting, NO fake candle glow, NO candles, NO studio backdrop, '
        'NO oversaturated red ornaments, NO extra sold accessories, NO montage, '
        'NO collage, NO text or watermark. This is a concept illustration only.'
    )


def _reference_for_cloudflare(reference_image):
    """Resize optional uploaded reference in memory; don't save or publish it."""
    if reference_image is None:
        return None
    if not isinstance(reference_image,bytes) or len(reference_image)>12_000_000:
        raise ValueError('A feltöltött kép túl nagy (maximum 12 MB).')
    from PIL import Image, ImageOps, UnidentifiedImageError
    try:
        with Image.open(io.BytesIO(reference_image)) as im:
            if im.width*im.height>30_000_000:
                raise ValueError('A kép mérete túl nagy.')
            im=ImageOps.exif_transpose(im).convert('RGB')
            im.thumbnail((480,480),resample=Image.Resampling.LANCZOS)
            out=io.BytesIO()
            im.save(out,format='PNG',optimize=True)
            return out.getvalue()
    except (OSError,UnidentifiedImageError,Image.DecompressionBombError) as e:
        raise ValueError('A feltöltött fájl nem érvényes kép.') from e


def generate_one_photo(account_id,token,model_label='FLUX.2 Klein 4B (more free generations)',
                       reference_image=None):
    import requests as _requests
    import re as _re
    if not isinstance(account_id,str) or not _re.fullmatch(r'[a-fA-F0-9]{32}',account_id.strip()):
        raise ValueError('Add meg a 32 karakteres Cloudflare Account ID-t.')
    if not isinstance(token,str) or len(token.strip())<10:
        raise ValueError('Add meg a Cloudflare API-tokent.')
    if model_label not in cloudflare_photos.MODELS:
        raise ValueError('Ismeretlen képgeneráló modell.')
    source=_reference_for_cloudflare(reference_image)
    url=cloudflare_photos.BASE+account_id.strip()+'/ai/run/'+cloudflare_photos.MODELS[model_label]
    fields={'prompt':(None,photo_prompt(reference_used=source is not None)),
            'width':(None,'1024'),'height':(None,'768')}
    if source is not None:
        fields['input_image_0']=('reference.png',source,'image/png')
    try:
        response=_requests.post(url,headers={'Authorization':'Bearer '+token.strip()},
                     files=fields,timeout=(10,180))
    except _requests.RequestException as e:
        raise ValueError('Nem sikerült elérni a Cloudflare-t.') from e
    if response.status_code in (401,403):raise ValueError('A Cloudflare visszautasította a tokent vagy a hozzáférést.')
    if response.status_code==429:raise ValueError('Elérted a Cloudflare napi keretét vagy sebességkorlátját.')
    if response.status_code in (402,409):raise ValueError('A modellhez aktiválás vagy számlázás szükséges lehet.')
    if response.status_code==400:
        raise ValueError('Cloudflare HTTP 400: '+cloudflare_photos._safe_provider_error(response,account_id,token))
    if not response.ok:raise ValueError('Cloudflare képgenerálási hiba (HTTP '+str(response.status_code)+').')
    return cloudflare_photos._decode_response(response)


def purchase_cost_known(offer):
    price=offer.get('price_huf')
    shipping=offer.get('shipping_huf')
    if not isinstance(price,int) or price<=0:return None
    if not isinstance(shipping,int):return None
    return price+shipping
