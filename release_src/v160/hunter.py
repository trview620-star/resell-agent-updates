"""Real shopping discovery → seller-selected product → reliable draft pipeline.

No fabricated resale margins or stock. Live publishing only through explicit,
authorized official marketplace APIs. No background spending.
"""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlsplit
import json
import re

import requests
from . import db, shopping

TOPICS = {
    "Karácsony": [
        "karácsonyi LED fényfüzér beltéri",
        "karácsonyi asztali dekoráció",
        "adventi koszorú piros",
        "karácsonyi ajándék társasjáték",
        "karácsonyi vetítő projektor",
        "karácsonyi dísz készlet",
        "karácsonyi ajándék gyermekeknek",
        "karácsonyi ajtódísz",
        "karácsonyi dekoráció ablak",
    ],
    "Elektronika": [
        "vezeték nélküli fejhallgató",
        "bluetooth hangszóró",
        "webkamera full hd",
        "mechanikus billentyűzet",
        "usb c dokkoló",
        "vezeték nélküli egér",
        "hordozható monitor",
        "okosotthon szenzor",
        "led asztali lámpa",
    ],
    "Gaming": [
        "LEGO Technic készlet",
        "játékkonzol kontroller",
        "gaming headset",
        "gamer billentyűzet",
        "Nintendo Switch játék",
        "szimulátor kormány",
        "gamer egér",
        "gaming mikrofon",
        "retro videojáték",
    ],
    "Otthon": [
        "konyhai rendszerező",
        "akkumulátoros csavarozó",
        "asztali lámpa",
        "dekorációs képkeret",
        "fürdőszobai tároló",
        "robotporszívó",
        "kávéfőző",
        "telefontartó",
        "polcrendszerező",
    ],
    "Játékok": [
        "LEGO készlet",
        "társasjáték családi",
        "távirányítós autó",
        "puzzle 1000 darab",
        "kreatív gyerekjáték",
        "plüss figura",
        "építőjáték",
        "rubik kocka",
        "kártyajáték",
    ],
}

MAX_SEARCHES=9
MAX_DB_RESULTS=2500


def initialize():
    db.initialize()
    shopping.initialize()
    with db.session() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS hunter_results(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          url TEXT NOT NULL UNIQUE,
          title TEXT NOT NULL,
          merchant TEXT NOT NULL,
          price_huf INTEGER NOT NULL CHECK(price_huf>0),
          thumbnail TEXT NOT NULL DEFAULT '',
          phrase TEXT NOT NULL,
          topic TEXT NOT NULL,
          link_type TEXT NOT NULL DEFAULT '',
          found_at TEXT NOT NULL,
          selected_at TEXT,
          product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
          status TEXT NOT NULL DEFAULT 'new' CHECK(status IN ('new','selected','prepared','ignored')),
          last_error TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS ix_hunter_status ON hunter_results(status,found_at);
        CREATE TABLE IF NOT EXISTS hunter_runs(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          topic TEXT NOT NULL,
          searched INTEGER NOT NULL,
          found INTEGER NOT NULL,
          errors TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS hunter_preparations(
          hunter_id INTEGER PRIMARY KEY REFERENCES hunter_results(id) ON DELETE CASCADE,
          product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
          marketplaces TEXT NOT NULL DEFAULT '[]',
          description_source TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'drafts',
          updated_at TEXT NOT NULL
        );
        """)


def safe_thumbnail(value):
    if not isinstance(value,str) or len(value)>1200: return ''
    try:
        url=urlsplit(value)
        if url.scheme!='https' or not url.hostname or url.username or url.password:
            return ''
        from .research import valid_public_url
        return value if valid_public_url(value) else ''
    except (ValueError, TypeError):
        return ''


def _thumbnails(payload):
    """Match the original Shopping thumbnails by title + retailer, never use as listing assets."""
    normalized={}
    source=payload.get('shopping_results',[])
    if not isinstance(source,list):return normalized
    for row in source:
        if not isinstance(row,dict):continue
        name=str(row.get('title') or row.get('name') or '').strip().casefold()
        seller=str(row.get('source') or row.get('merchant') or row.get('seller') or '').strip().casefold()
        img=safe_thumbnail(row.get('imageUrl') or row.get('thumbnailUrl') or row.get('thumbnail') or '')
        if name and img:normalized[(name,seller)]=img
    return normalized


def scan(serper_key,topic="Karácsony",searches=6,extra_phrase=''):
    """At most 9 Serper calls, billed against existing app cap. Errors not hidden."""
    initialize()
    if topic not in TOPICS:raise ValueError('Ismeretlen témakör.')
    key=str(serper_key or '').strip()
    if not key:raise ValueError('Előbb add meg a Serper API-kulcsot.')
    if not isinstance(searches,int) or searches not in (3,6,9):
        raise ValueError('Egyszerre 3, 6 vagy 9 keresés indítható.')
    phrases=list(TOPICS[topic][:searches])
    if extra_phrase.strip():
        phrases[-1]=shopping._valid_phrase(extra_phrase)
    total=0;errors=[];accepted_count=0
    for phrase in phrases:
        try:
            payload=shopping.fetch_serper_results(phrase,key)
            matches,skipped,meta=shopping.analyze_results(payload)
            matching,_=shopping.select_matching_results(matches,phrase)
            pictures=_thumbnails(payload)
            for item in matching:
                title=item['title']
                seller=item['merchant']
                img=pictures.get((title.strip().casefold(),seller.strip().casefold()),'')
                with db.session() as con:
                    con.execute("""
                      INSERT INTO hunter_results(url,title,merchant,price_huf,thumbnail,phrase,topic,link_type,found_at)
                      VALUES(?,?,?,?,?,?,?,?,?)
                      ON CONFLICT(url) DO UPDATE SET
                        title=excluded.title,merchant=excluded.merchant,
                        price_huf=excluded.price_huf,
                        thumbnail=CASE WHEN excluded.thumbnail<>'' THEN excluded.thumbnail ELSE hunter_results.thumbnail END,
                        phrase=excluded.phrase,topic=excluded.topic,link_type=excluded.link_type,
                        found_at=excluded.found_at
                    """,(item['url'],title,seller,int(item['price_huf']),img,phrase,topic,
                         item['kind'],db.utcnow()))
                accepted_count+=1
        except (ValueError,requests.RequestException) as error:
            errors.append(phrase+': '+str(error)[:140])
        total+=1
        if shopping.current_usage()>=shopping.MONTHLY_LIMIT:
            errors.append('Elérted a havi Serper keresési védelmi keretet.')
            break
    with db.session() as con:
        con.execute('INSERT INTO hunter_runs(topic,searched,found,errors,created_at) VALUES(?,?,?,?,?)',
                    (topic,total,accepted_count,' | '.join(errors)[:1900],db.utcnow()))
        # Keep selected data; prune only old unselected.
        con.execute("""DELETE FROM hunter_results WHERE id IN (
          SELECT id FROM hunter_results WHERE status='new'
          ORDER BY found_at DESC,id DESC LIMIT -1 OFFSET ?
        )""",(MAX_DB_RESULTS,))
    return {'queries':total,'offers':accepted_count,'errors':errors}


def offers(*,topic='',status='all',query='',max_price=1_000_000,limit=250):
    initialize()
    filters=['price_huf<=?'];args=[int(max_price)]
    if topic and topic!='Mind':filters.append('topic=?');args.append(topic)
    if status and status!='all':filters.append('status=?');args.append(status)
    if query.strip():
        filters.append('(title LIKE ? OR merchant LIKE ?)')
        args.extend(['%'+query.strip()+'%']*2)
    where=' AND '.join(filters)
    return db.rows(f"""SELECT * FROM hunter_results WHERE {where}
       ORDER BY CASE status WHEN 'selected' THEN 0 WHEN 'prepared' THEN 0 ELSE 1 END,
                found_at DESC,id DESC LIMIT ?""",tuple(args+[max(1,min(500,int(limit)))]))


def select_offer(hunter_id,route=None):
    """Idempotently select real result as local product. No automatic sales price."""
    initialize()
    route=route or db.FULFILLMENT[0]
    if route not in db.FULFILLMENT:raise ValueError('Ismeretlen teljesítési mód.')
    row=db.row('SELECT * FROM hunter_results WHERE id=?',(hunter_id,))
    if row is None:raise ValueError('Nincs ilyen terméktalálat.')
    if row['status']=='ignored':raise ValueError('Ez a termék el lett vetve.')
    if row.get('product_id'):return int(row['product_id'])
    # A Shopping search result is neither a stock check nor an authorized product photograph.
    record={
        'title':row['title'],'brand':'','model':'','category':row['topic'],
        'condition_text':'Unknown / verify','description':'',
        'supplier':row['merchant'],'supplier_url':row['url'],
        'supplier_price':row['price_huf'],'inbound_shipping':0,'outbound_shipping':0,
        'packaging':0,'marketplace_fees':0,'risk_buffer':0,'target_price':0,
        'stock_status':'unknown','stock_verified_at':None,'eta_days':0,
        'fulfillment':route,'status':'candidate',
        'notes':'Termékvadász találat. Nincs ellenőrizve a készlet, szállítás, árazás, '
               'értékesítési kereslet és eredeti fényképek. '
               '0 Ft kiszállítási mező = nincs még adat, NEM igazolt ingyenes szállítás.'}
    pid=db.insert_product(record)
    with db.session() as con:
        con.execute("""UPDATE hunter_results SET product_id=?,status='selected',
                         selected_at=? WHERE id=? AND product_id IS NULL""",
                     (pid,db.utcnow(),hunter_id))
    return pid


def ignore(hunter_id):
    initialize()
    with db.session() as con:
        con.execute("UPDATE hunter_results SET status='ignored' WHERE id=? AND status='new'",(hunter_id,))


def plain_description(title):
    """Conservative non-AI fallback. No unverified specs or availability."""
    short=' '.join(str(title or '').strip().split())[:160]
    if not short:return ''
    return (f'{short}.\n\nA termékkel kapcsolatos kérdéseket szívesen fogadom. '
            'A részleteket üzenetben egyeztetjük.\n\n'
            'Hasonló termékekért nézd meg a többi hirdetésemet.')


TEXT_MODEL='@cf/google/gemma-4-26b-a4b-it'


def ai_description(product,account,token):
    """One optional Cloudflare text generation request, without saving credentials."""
    if not isinstance(account,str) or not re.fullmatch('[0-9a-fA-F]{32}',account.strip()):
        raise ValueError('Cloudflare Account ID szükséges a szöveggeneráláshoz.')
    if not isinstance(token,str) or len(token.strip())<10:
        raise ValueError('Cloudflare API token szükséges a szöveggeneráláshoz.')
    prompt=(
        'Csak a következő hitelesített információkat használhatod: '
        +str(product.get('title',''))[:180]+'; '
        +str(product.get('description',''))[:900]+'. '
        'Írj nagyon természetes, tömör magyar online apróhirdetési leírást '
        '2-4 mondatban, egyszerűen, emberszerűen. '
        'Ne szerepeljen cikkszám, felsorolás, marketing sablon, emoji, AI, '
        'ellenőrzési megjegyzés, állapot, készlet, próba, garancia, elérhetőség '
        'vagy eredetiség, hacsak ez az adatokban nincs igazolva. '
        'Ne találj ki színt, méretet, alkatrészt vagy használatot. '
        'Végére pontosan írd: Hasonló termékekért nézd meg a többi hirdetésemet.'
    )
    try:
        response=requests.post(
            'https://api.cloudflare.com/client/v4/accounts/'+account.strip()+'/ai/run/'+TEXT_MODEL,
            headers={'Authorization':'Bearer '+token.strip()},
            json={'messages':[
                {'role':'system','content':'Magyar apróhirdetés-író vagy. Ne találj ki tényeket.'},
                {'role':'user','content':prompt}],
                'max_completion_tokens':350,'temperature':0.4},
            timeout=(5,65))
    except requests.RequestException as e:
        raise ValueError('A szöveges AI nem érhető el.') from e
    if not response.ok:
        raise ValueError('A szöveges AI kérés sikertelen (HTTP '+str(response.status_code)+').')
    try:
        data=response.json()
        result=data.get('result') or {}
        text=result.get('response') or ''
        if not text and isinstance(result.get('choices'),list):
            text=result['choices'][0].get('message',{}).get('content','')
        text=str(text).strip()
        if not 35<=len(text)<=2000:raise ValueError('Nem megfelelő hosszúságú szöveg')
        return text[:1700]
    except (ValueError,AttributeError,KeyError,IndexError,TypeError) as e:
        raise ValueError('A szöveges AI nem adott használható leírást.') from e


def prepare(hunter_id,marketplaces,*,account='',token='',use_ai=True):
    """Prepare all requested marketplace drafts automatically after user selection."""
    from . import listing
    initialize()
    markets=list(dict.fromkeys(marketplaces))
    if not markets or any(m not in db.PLATFORMS for m in markets):
        raise ValueError('Válassz legalább egy támogatott piacteret.')
    pid=select_offer(hunter_id)
    product=db.row('SELECT * FROM products WHERE id=?',(pid,))
    if not product:raise ValueError('A termék nem található.')
    # Do not overwrite a seller-reviewed description with generic generation.
    previous=db.row('SELECT * FROM hunter_preparations WHERE hunter_id=?',(hunter_id,))
    if previous and previous['description_source']=='AI':
        desc=product['description']
        origin='AI'
    else:
        desc=product['description'] or plain_description(product['title'])
        origin='Tényalapú szöveg'
        if use_ai and token and account and not product['description']:
            try:
                desc=ai_description(product,account,token)
                origin='AI'
            except ValueError:
                origin='Tényalapú szöveg (AI nem elérhető)'
        if not product['description']:
            db.update_product(pid,description=desc)
    ready=[]
    for market in markets:
        # Never auto-invent price or mark a listing as ready to publish.
        title=product['title'][:80]
        body=desc
        if market in ('eBay','Amazon'):
            body=body.replace('\n\nHasonló termékekért nézd meg a többi hirdetésemet.','')
        lid=db.insert_listing(pid,market,title,body,int(product.get('target_price') or 0))
        existing=db.row('SELECT * FROM listings WHERE id=?',(lid,))
        if existing and existing['status'] in ('draft','ready'):
            db.update_listing(lid,title=title,description=body)
        ready.append({'marketplace':market,'listing_id':lid})
    with db.session() as con:
        con.execute("""INSERT INTO hunter_preparations
          (hunter_id,product_id,marketplaces,description_source,status,updated_at)
          VALUES(?,?,?,?,?,?)
          ON CONFLICT(hunter_id) DO UPDATE SET
          product_id=excluded.product_id,marketplaces=excluded.marketplaces,
          description_source=excluded.description_source,status=excluded.status,
          updated_at=excluded.updated_at""",
          (hunter_id,pid,json.dumps(markets,ensure_ascii=False),origin,'drafts',db.utcnow()))
        con.execute("UPDATE hunter_results SET status='prepared',last_error='' WHERE id=?",(hunter_id,))
    return {'product_id':pid,'drafts':ready,'description_source':origin}


def publish_ebay(hunter_id,oauth_token,profile):
    """Live posting only on authorized eBay Inventory API; never fabricate readiness."""
    from .publisher import EbayInventory
    initialize()
    row=db.row('SELECT * FROM hunter_results WHERE id=?',(hunter_id,))
    if not row or not row.get('product_id'):
        raise ValueError('Előbb készítsd elő a terméket.')
    pid=int(row['product_id'])
    product=db.row('SELECT * FROM products WHERE id=?',(pid,))
    listing=db.row("""SELECT * FROM listings WHERE product_id=? AND marketplace='eBay'
                       ORDER BY id DESC LIMIT 1""",(pid,))
    if not listing:raise ValueError('Előbb készíts eBay hirdetéspiszkozatot.')
    if listing['status']=='published':
        raise ValueError('A hirdetés már publikált. Ismételt posztolás tiltva.')
    if product['stock_status']!='available' or not product['stock_verified_at']:
        raise ValueError('A készletet és ellenőrzésének dátumát előbb igazolni kell.')
    checked=datetime.fromisoformat(product['stock_verified_at'].replace('Z','+00:00'))
    if checked.tzinfo is None:checked=checked.replace(tzinfo=timezone.utc)
    if (datetime.now(timezone.utc)-checked).total_seconds()>48*3600:
        raise ValueError('A készletellenőrzés 48 óránál régebbi.')
    if int(listing['price'] or 0)<=0:
        raise ValueError('Hiányzik az ellenőrzött, forintban megadott belső eladási ár.')
    try:
        platform_price=float(str(profile.get('market_price','')).replace(',','.'))
        if not 0<platform_price<=1_000_000: raise ValueError()
    except (TypeError,ValueError):
        raise ValueError('Add meg az eBay pénznemében a külön eladási árat.')
    if not isinstance(profile,dict) or not profile.get('confirmed_source_photo'):
        raise ValueError('A valódi és jogszerű termékfotó nincs jóváhagyva.')
    required=['currency','category_id','condition','merchant_location_key',
              'marketplace_id','payment_policy_id','return_policy_id',
              'fulfillment_policy_id','sku','image_urls','aspects']
    for name in required:
        if not profile.get(name):raise ValueError('Hiányzó eBay beállítás: '+name)
    # Seller-provided external HTTPS images; never Google Shopping thumbnails or AI guesses.
    images=profile['image_urls']
    if not isinstance(images,list) or any(not isinstance(u,str) or not u.startswith('https://') for u in images):
        raise ValueError('Valódi, nyilvános HTTPS termékfotók szükségesek.')
    client=EbayInventory(oauth_token,profile.get('environment','sandbox'))
    result=client.publish(sku=profile['sku'],title=listing['title'],
        description=listing['description'],price=profile['market_price'],
        currency=profile['currency'],category_id=profile['category_id'],
        condition=profile['condition'],merchant_location_key=profile['merchant_location_key'],
        marketplace_id=profile['marketplace_id'],
        payment_policy_id=profile['payment_policy_id'],
        return_policy_id=profile['return_policy_id'],
        fulfillment_policy_id=profile['fulfillment_policy_id'],
        image_urls=images,aspects=profile['aspects'])
    if not result.get('listing_id'):
        raise ValueError('Az eBay nem adott vissza megerősített listing ID-t.')
    if profile.get('environment','sandbox')=='production':
        db.update_listing(listing['id'],status='published',
            url='https://www.ebay.com/itm/'+str(result['listing_id']))
        result['mode']='production'
    else:
        result['mode']='sandbox'
    return result
