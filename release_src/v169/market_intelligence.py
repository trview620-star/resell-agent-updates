"""Evidence-labelled Top 50 research radar, using the already-configured Serper feed.

50 concrete research targets. A category study is not evidence of sales of
a particular model; live asking prices are not completed-sale comparisons.
"""
from __future__ import annotations
from datetime import datetime,timezone
from . import db,shopping,supplier_links,radar_previews
import requests

SOURCES={
    'LEGO':('Google HU / DataForSEO, LEGO keresési szezon (kategória, 2025)',
            'https://karacsonymost.hu/karacsony/legkeresettebb-karacsonyi-ajandekok',44),
    'Társasjáték':('Google HU / DataForSEO, társasjáték keresések (kategória, 2025)',
             'https://karacsonymost.hu/karacsony/legkeresettebb-karacsonyi-ajandekok',40),
    'Gaming':('Europion / MediaMarkt, műszaki vásárlási szándék (kategória, 2026)',
             'https://bonline.hu/cikk/166709/',37),
    'Audio':('NMHH 2025, online szórakoztatóelektronikai vásárlások (kategória)',
             'https://nmhh.hu/cikk/258932',34),
    'Számítástechnika':('NMHH 2025, online számítástechnikai vásárlások (kategória)',
             'https://nmhh.hu/cikk/258932',33),
    'Háztartási kisgép':('Europion / MediaMarkt 2026, háztartási kisgép vásárlási szándék',
             'https://bonline.hu/cikk/166709/',39),
    'Ruházat':('NMHH 2025, ruházat/cipő online vásárlások (kategória)',
             'https://nmhh.hu/cikk/258932',42)
}
# A research queue, NOT a claim that these individual models are trending.
SEEDS=[
('LEGO','LEGO Botanicals 10328 Rózsacsokor'),
('LEGO','LEGO Botanicals 10329 Apró növények'),
('LEGO','LEGO Botanicals 10342 Rózsaszín virágcsokor'),
('LEGO','LEGO Botanicals 10343 Mini orchidea'),
('LEGO','LEGO Speed Champions 76934 Ferrari F40'),
('LEGO','LEGO Technic 42171 Mercedes F1'),
('LEGO','LEGO Icons 10331 Jégmadár'),
('LEGO','LEGO Ideas 21366 Úszkáló vidrák'),
('Társasjáték','Dobble társasjáték'),
('Társasjáték','Dixit társasjáték'),
('Társasjáték','Azul társasjáték'),
('Társasjáték','Catan társasjáték'),
('Társasjáték','Ticket to Ride Europe társasjáték'),
('Társasjáték','Hitster társasjáték'),
('Társasjáték','Exploding Kittens kártyajáték'),
('Gaming','PlayStation 5 DualSense kontroller'),
('Gaming','Xbox Wireless Controller'),
('Gaming','Nintendo Switch Pro Controller'),
('Gaming','Nintendo Switch OLED konzol'),
('Gaming','Mario Kart 8 Deluxe Nintendo Switch'),
('Gaming','The Legend of Zelda Tears of the Kingdom Switch'),
('Gaming','8BitDo Ultimate 2C kontroller'),
('Gaming','Logitech G29 kormány'),
('Gaming','Razer DeathAdder V3 egér'),
('Audio','JBL Flip 6 hangszóró'),
('Audio','JBL Charge 5 hangszóró'),
('Audio','Sony WH-CH720N fejhallgató'),
('Audio','Sony WH-1000XM5 fejhallgató'),
('Audio','Apple AirPods 4'),
('Audio','Samsung Galaxy Buds FE'),
('Audio','Anker Soundcore Life Q30 fejhallgató'),
('Számítástechnika','Logitech MX Master 3S egér'),
('Számítástechnika','Logitech G502 X egér'),
('Számítástechnika','HyperX Cloud III headset'),
('Számítástechnika','Logitech C920 HD Pro webkamera'),
('Számítástechnika','Samsung T7 1TB SSD'),
('Számítástechnika','Crucial P3 Plus 1TB SSD'),
('Számítástechnika','Kingston Fury Beast 16GB DDR4 RAM'),
('Számítástechnika','Elgato Stream Deck Mini'),
('Háztartási kisgép','Philips Airfryer HD9252'),
('Háztartási kisgép','Ninja Air Fryer AF180'),
('Háztartási kisgép','DeLonghi Dedica EC685 kávéfőző'),
('Háztartási kisgép','Nespresso Essenza Mini'),
('Háztartási kisgép','Xiaomi Robot Vacuum S20 robotporszívó'),
('Háztartási kisgép','Oral-B iO Series 3 elektromos fogkefe'),
('Háztartási kisgép','Philips Sonicare 3100 elektromos fogkefe'),
('Ruházat','Nike Air Force 1 07 cipő'),
('Ruházat','adidas Gazelle cipő'),
('Ruházat','New Balance 530 cipő'),
('Ruházat','Levis 501 Original farmer'),
]
assert len(SEEDS)==50 and len({p for _,p in SEEDS})==50

def initialize():
    db.initialize()
    shopping.initialize()
    with db.session() as conn:
        conn.executescript("""
          CREATE TABLE IF NOT EXISTS demand_radar_runs(
            phrase TEXT PRIMARY KEY,
            checked_at TEXT NOT NULL,
            accepted INTEGER NOT NULL DEFAULT 0,
            rejected INTEGER NOT NULL DEFAULT 0,
            error TEXT NOT NULL DEFAULT ''
          );
        """)

def _save_results(phrase,topic,payload):
    from . import hunter
    matches,skipped,_=shopping.analyze_results(payload)
    matching,_=shopping.select_matching_results(matches,phrase)
    thumbnails=hunter._thumbnails(payload)
    for hit in payload.get('shopping_results',[]):
        if not isinstance(hit,dict):
            continue
        title=str(hit.get('title') or hit.get('name') or '').strip().casefold()
        seller=str(hit.get('source') or hit.get('merchant') or hit.get('seller') or '').strip().casefold()
        pic=radar_previews.url_from_hit(hit)
        if title and pic:
            thumbnails.setdefault((title,seller),pic)
    count=0
    for item in matching:
        url,kind=supplier_links.offer_url(item,payload)
        title=item['title']
        merchant=item['merchant']
        pic=thumbnails.get((title.strip().casefold(),merchant.strip().casefold()),'')
        with db.session() as conn:
            conn.execute("""
             INSERT INTO hunter_results(url,title,merchant,price_huf,
               thumbnail,phrase,topic,link_type,found_at)
             VALUES(?,?,?,?,?,?,?,?,?)
             ON CONFLICT(url) DO UPDATE SET title=excluded.title,
               merchant=excluded.merchant,price_huf=excluded.price_huf,
               thumbnail=CASE WHEN excluded.thumbnail<>'' THEN excluded.thumbnail
                              ELSE hunter_results.thumbnail END,
               phrase=excluded.phrase,topic=excluded.topic,
               link_type=excluded.link_type,found_at=excluded.found_at
             """,(url,title,merchant,int(item['price_huf']),
                  pic,phrase,topic,kind,db.utcnow()))
        count+=1
    return count,skipped

def scan_keyword(key,phrase,topic='Saját keresés'):
    """Exactly one charged Google Shopping query; no silent 3-query expansion."""
    from . import hunter
    initialize()
    hunter.initialize()
    phrase=shopping._valid_phrase(phrase)
    if not str(key or '').strip():
        raise ValueError('Serper API-kulcs szükséges.')
    try:
        payload=shopping.fetch_serper_results(phrase,key)
        count,rejected=_save_results(phrase,topic,payload)
        error=''
    except (ValueError,requests.RequestException) as exc:
        count=0;rejected=0;error=str(exc)[:250]
    with db.session() as conn:
        conn.execute("""INSERT INTO demand_radar_runs(
            phrase,checked_at,accepted,rejected,error) VALUES(?,?,?,?,?)
            ON CONFLICT(phrase) DO UPDATE SET checked_at=excluded.checked_at,
                accepted=excluded.accepted,rejected=excluded.rejected,
                error=excluded.error
        """,(phrase,db.utcnow(),count,rejected,error))
    return {'phrase':phrase,'found':count,'skipped':rejected,
            'error':error,'used_calls':shopping.current_usage()}

def offers_for(phrase,limit=20):
    from . import hunter
    return hunter.offers(topic='',status='all',query='',max_price=10_000_000,limit=500) if not phrase else db.rows(
        """SELECT * FROM hunter_results WHERE phrase=?
           ORDER BY price_huf ASC,found_at DESC LIMIT ?""",
        (phrase,max(1,min(80,int(limit)))))

def shortlisted():
    initialize()
    logs={r['phrase']:r for r in db.rows('SELECT * FROM demand_radar_runs')}
    output=[]
    for idx,(category,phrase) in enumerate(SEEDS,1):
        source,url,base=SOURCES[category]
        offers=offers_for(phrase)
        sellers={x['merchant'].strip().casefold() for x in offers if x['merchant'].strip()}
        direct=sum(supplier_links.direct_url(o['url']) for o in offers)
        prices=[int(x['price_huf']) for x in offers if int(x['price_huf'])>0]
        thumbnail=radar_previews.preview_for(phrase,offers)
        # Opportunity research score, NOT an observed product search volume or sell-through.
        # No false margin/profit: verified completed sales are not automatically available.
        score=min(85,base + (8 if offers else 0) + min(12,3*len(sellers)) +
                        (5 if direct else 0))
        log=logs.get(phrase)
        output.append({'id':idx,'category':category,'phrase':phrase,
            'source':source,'source_url':url,'score':score,
            'checked_at':log['checked_at'] if log else '',
            'error':log['error'] if log else '',
            'retailers':len(sellers),'direct':direct,
            'offers':len(offers),'thumbnail':thumbnail,
            'lowest_huf':min(prices) if prices else None,
            'highest_huf':max(prices) if prices else None,
            'confidence':'Kereskedői árak ismertek' if prices else 'Kategóriaadat – modell még nem ellenőrzött'})
    return sorted(output,key=lambda x:(-x['score'],-x['retailers'],x['id']))

def next_unchecked(limit=10):
    results=shortlisted()
    # Unchecked candidates first; then oldest refreshed.
    ordered=sorted(results,key=lambda x:(bool(x['checked_at']),x['checked_at'] or '',-x['score']))
    return ordered[:max(1,min(50,int(limit)))]

def scan_batch(key,limit=10):
    if limit not in (5,10,20,50):
        raise ValueError('Érvénytelen szkennelési méret.')
    chosen=next_unchecked(limit)
    output=[]
    for item in chosen:
        if shopping.current_usage()>=shopping.MONTHLY_LIMIT:
            output.append({'phrase':item['phrase'],'found':0,
                           'error':'Elérted a havi API-keretet.'})
            break
        output.append(scan_keyword(key,item['phrase'],item['category']))
    return output
