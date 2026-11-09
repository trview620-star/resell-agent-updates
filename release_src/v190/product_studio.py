"""Persistent selection, price planning and AI image packs for supplier candidates."""
from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path

import requests
from concurrent.futures import ThreadPoolExecutor,as_completed
from . import db, auto_stock_photo, cloudflare_photos, demand_workbench, private_research, product_copy, shopping

MIN_PROFIT_HUF=4900
IMAGE_SLOTS=(
    ('front_three_quarter','01_fototermekkep'),
    ('straight_front','02_reszlet'),
    ('side_profile','03_otthoni_kep'),
    ('rear_three_quarter','04_kozelibb_nezet'),
)

def initialize():
    demand_workbench.initialize()
    with db.session() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS studio_selections(
          lead_id INTEGER NOT NULL REFERENCES demand_leads(id) ON DELETE CASCADE,
          source_result_id INTEGER NOT NULL REFERENCES hunter_results(id) ON DELETE CASCADE,
          vinted_reference_huf INTEGER,
          description TEXT NOT NULL DEFAULT '',
          selected_at TEXT NOT NULL,
          PRIMARY KEY(lead_id,source_result_id));
        CREATE TABLE IF NOT EXISTS studio_image_packs(
          lead_id INTEGER NOT NULL,
          source_result_id INTEGER NOT NULL,
          slot INTEGER NOT NULL CHECK(slot BETWEEN 1 AND 4),
          filename TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY(lead_id,source_result_id,slot),
          FOREIGN KEY(lead_id,source_result_id)
            REFERENCES studio_selections(lead_id,source_result_id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS studio_market_search_runs(
          lead_id INTEGER NOT NULL REFERENCES demand_leads(id) ON DELETE CASCADE,
          source TEXT NOT NULL CHECK(source IN ('trends','vinted','jofogas','ebay_sold')),
          query TEXT NOT NULL,
          checked_at TEXT NOT NULL,
          result_count INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL CHECK(status IN ('ok','no_results','error')),
          error TEXT NOT NULL DEFAULT '',
          PRIMARY KEY(lead_id,source));
        CREATE TABLE IF NOT EXISTS studio_market_search_results(
          lead_id INTEGER NOT NULL,
          source TEXT NOT NULL,
          url TEXT NOT NULL,
          title TEXT NOT NULL,
          snippet TEXT NOT NULL DEFAULT '',
          result_date TEXT NOT NULL DEFAULT '',
          checked_at TEXT NOT NULL,
          PRIMARY KEY(lead_id,source,url),
          FOREIGN KEY(lead_id,source) REFERENCES studio_market_search_runs(lead_id,source) ON DELETE CASCADE);
        """)

def market_diagnostics(lead_id):
    initialize()
    lead=db.row('SELECT * FROM demand_leads WHERE id=?',(int(lead_id),))
    if not lead:return None
    runs={r['source']:r for r in db.rows('SELECT * FROM studio_market_search_runs WHERE lead_id=?',(int(lead_id),))}
    results=db.rows('SELECT * FROM studio_market_search_results WHERE lead_id=? ORDER BY source,title',(int(lead_id),))
    grouped={source:[] for source in ('trends','vinted','jofogas','ebay_sold')}
    for result in results:grouped.setdefault(result['source'],[]).append(result)
    hits=demand_workbench.supplier_candidates(lead_id)
    history=demand_workbench.recent_checks(lead_id)
    by_offer={}
    for record in history:
        key=(record['supplier'],record['url'])
        by_offer.setdefault(key,[]).append(record)
    price_moves=[]
    for records in by_offer.values():
        newest=records[0]
        previous=next((r for r in records[1:] if r['unit_price_huf']!=newest['unit_price_huf']),None)
        if previous:
            price_moves.append({'supplier':newest['supplier'],'old':int(previous['unit_price_huf']),
                                'new':int(newest['unit_price_huf']),'checked_at':newest['checked_at']})
    suppliers=sorted({row['supplier'] for row in hits})
    return {'lead':lead,'runs':runs,'results':grouped,'shopping_count':len(hits),'shopping_suppliers':suppliers,
            'shopping_lowest':min((int(x['price_huf']) for x in hits),default=None),
            'history_count':len(history),'price_moves':sorted(price_moves,key=lambda x:x['checked_at'],reverse=True)[:6]}

def _serper_search(source,query,api_key):
    try:
        shopping.reserve_call()
        response=requests.post('https://google.serper.dev/search',
            headers={'X-API-KEY':api_key.strip(),'Content-Type':'application/json'},
            json={'q':query,'gl':'hu','hl':'hu','num':5},timeout=(5,18))
        response.raise_for_status(); payload=response.json()
        if payload.get('message') or payload.get('error'):
            raise ValueError(str(payload.get('message') or payload.get('error'))[:160])
        organic=payload.get('organic')
        if not isinstance(organic,list):raise ValueError('A kereső nem adott szerves találatlistát.')
        safe=[]
        for item in organic[:5]:
            if not isinstance(item,dict):continue
            url=str(item.get('link') or '').strip()
            if not url.startswith(('https://','http://')):continue
            safe.append({'url':url,'title':str(item.get('title') or '')[:250],
                         'snippet':str(item.get('snippet') or '')[:650],
                         'date':str(item.get('date') or '')[:80]})
        return source,{'results':safe,'status':'ok' if safe else 'no_results','error':''}
    except (requests.RequestException,ValueError,TypeError) as exc:
        return source,{'results':[],'status':'error','error':str(exc)[:200]}

def scan_market_diagnostics(lead_id,api_key):
    """One click, four source-specific indexed web searches; snippets aren't counts or sales."""
    initialize();lead=db.row('SELECT * FROM demand_leads WHERE id=?',(int(lead_id),))
    if not lead:raise ValueError('A keresleti jel nem található.')
    if not str(api_key or '').strip():raise ValueError('A korábban megadott keresőkulcs szükséges.')
    phrase=' '.join(str(lead['phrase']).split())
    queries={
      'trends':f'site:trends.google.com/trends/explore {phrase} Hungary interest',
      'vinted':f'site:vinted.hu {phrase}',
      'jofogas':f'site:jofogas.hu {phrase}',
      'ebay_sold':f'site:ebay.de/itm {phrase} sold completed',
    }
    outcomes={}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(_serper_search,source,query,api_key) for source,query in queries.items()]
        for future in as_completed(futures):
            source,result=future.result();outcomes[source]=result
    now=db.utcnow()
    with db.session() as con:
        for source,query in queries.items():
            result=outcomes[source]
            con.execute('''INSERT INTO studio_market_search_runs(lead_id,source,query,checked_at,result_count,status,error)
              VALUES(?,?,?,?,?,?,?) ON CONFLICT(lead_id,source) DO UPDATE SET query=excluded.query,
              checked_at=excluded.checked_at,result_count=excluded.result_count,status=excluded.status,error=excluded.error''',
              (int(lead_id),source,query,now,len(result['results']),result['status'],result['error']))
            con.execute('DELETE FROM studio_market_search_results WHERE lead_id=? AND source=?',(int(lead_id),source))
            for item in result['results']:
                con.execute('''INSERT INTO studio_market_search_results(lead_id,source,url,title,snippet,result_date,checked_at)
                  VALUES(?,?,?,?,?,?,?)''',(int(lead_id),source,item['url'],item['title'],item['snippet'],item['date'],now))
    return {'searched':len(queries),'found':sum(len(x['results']) for x in outcomes.values()),
            'errors':[source for source,x in outcomes.items() if x['status']=='error']}

def diagnostic_links(phrase):
    from urllib.parse import quote_plus
    query=quote_plus(str(phrase or ''))
    return {
      'Google Trends':'https://trends.google.com/trends/explore?geo=HU&q='+query,
      'Google Shopping':'https://www.google.com/search?tbm=shop&q='+query,
      'Vinted':'https://www.vinted.hu/catalog?search_text='+query,
      'Jófogás':'https://www.jofogas.hu/magyarorszag?q='+query,
      'eBay Sold':'https://www.ebay.de/sch/i.html?_nkw='+query+'&LH_Sold=1&LH_Complete=1',
    }

def priority_key(lead_id):
    """Transparent ordering: cross-source evidence coverage, sold pace, verified cost."""
    data=market_diagnostics(lead_id); lead=data['lead']
    coverage=sum(1 for source in ('trends','vinted','jofogas','ebay_sold')
                 if data['runs'].get(source) and data['runs'][source]['status']=='ok')
    pace=(30*int(lead['sold_units'])/max(1,int(lead['period_days']))
          if lead['manually_verified'] and lead['sold_units'] and lead['period_days'] else 0.0)
    return (-coverage,-pace,str(lead['phrase']).casefold())

def candidates():
    initialize(); result=[]
    leads={int(x['id']):x for x in demand_workbench.leads()}
    priorities={lead_id:priority_key(lead_id) for lead_id in leads}
    for lead in leads.values():
        for hit in demand_workbench.supplier_candidates(lead['id']):
            hit=dict(hit); hit['lead']=lead
            hit['pace']=(30*int(lead['sold_units'])/max(1,int(lead['period_days']))
                         if lead['manually_verified'] and lead['sold_units'] and lead['period_days'] else 0.0)
            hit['verified']=[x for x in demand_workbench.verified_supplier_offers(
                lead['id'],demand_workbench.POSTCODE_DEFAULT) if int(x['source_result_id'])==int(hit['id'])]
            hit['selected']=bool(db.row('SELECT 1 FROM studio_selections WHERE lead_id=? AND source_result_id=?',(lead['id'],hit['id'])))
            result.append(hit)
    return sorted(result,key=lambda x:(priorities[int(x['lead']['id'])],not bool(x['verified']),int(x['price_huf'])))

def toggle(lead_id,source_result_id,selected):
    initialize(); lead=db.row('SELECT * FROM demand_leads WHERE id=?',(int(lead_id),))
    hit=db.row('SELECT * FROM hunter_results WHERE id=?',(int(source_result_id),))
    if not lead or not hit or hit['phrase']!=lead['phrase'] or not private_research.offer_matches_scope(hit):
        raise ValueError('A termék nem tartozik a kiválasztott kereslethez és a 13 bolt egyikéhez.')
    if selected:
        title=str(hit['title'] or '').strip()
        description=product_copy.fallback(title)
        with db.session() as con:
            con.execute('INSERT OR IGNORE INTO studio_selections(lead_id,source_result_id,description,selected_at) VALUES(?,?,?,?)',(int(lead_id),int(source_result_id),description,db.utcnow()))
    else:
        with db.session() as con:con.execute('DELETE FROM studio_selections WHERE lead_id=? AND source_result_id=?',(int(lead_id),int(source_result_id)))

def selected():
    initialize(); out=[]
    rows=db.rows('''SELECT s.*,h.title,h.merchant,h.price_huf,h.thumbnail,h.url,h.found_at,l.phrase,
                    l.sold_units,l.period_days,l.ebay_median_huf
                    ,l.manually_verified
                    FROM studio_selections s JOIN hunter_results h ON h.id=s.source_result_id
                    JOIN demand_leads l ON l.id=s.lead_id''')
    for row in rows:
        # Checks are explicitly confirmed against the same demand phrase/model;
        # use the lowest qualifying offer across the full approved retailer set.
        verified=demand_workbench.verified_supplier_offers(row['lead_id'],demand_workbench.POSTCODE_DEFAULT)
        row['verified_offer']=verified[0] if verified else None
        row['pace']=(30*int(row['sold_units'])/max(1,int(row['period_days']))
                     if row['sold_units'] and row['period_days'] else 0.0)
        row['target_price']=suggested_price(row['vinted_reference_huf'],row['verified_offer']['total_huf'] if row['verified_offer'] else None)
        row['images']=images(row['lead_id'],row['source_result_id'])
        out.append(row)
    return sorted(out,key=lambda r:(priority_key(r['lead_id']),int(r['verified_offer']['total_huf'] if r['verified_offer'] else 10**12),str(r['title']).casefold()))

def suggested_price(vinted_reference_huf,landed_cost_huf):
    if landed_cost_huf is None:return None
    floor=int(landed_cost_huf)+MIN_PROFIT_HUF
    return max(floor,int(vinted_reference_huf or 0))

def save_posting(lead_id,source_result_id,reference,description):
    reference=int(reference or 0)
    if reference<0:raise ValueError('Az összehasonlító Vinted-ár nem lehet negatív.')
    description='\n'.join(str(description or '').splitlines()).strip()[:2500]
    if not description:raise ValueError('Adj meg egy hirdetésszöveget.')
    with db.session() as con:
        con.execute('UPDATE studio_selections SET vinted_reference_huf=?,description=? WHERE lead_id=? AND source_result_id=?',(reference or None,description,int(lead_id),int(source_result_id)))

def _image_dir(lead_id,source_result_id):
    return db.DATA/'listing_studio'/str(int(lead_id))/str(int(source_result_id))

def images(lead_id,source_result_id):
    initialize(); rows=db.rows('SELECT slot,filename FROM studio_image_packs WHERE lead_id=? AND source_result_id=? ORDER BY slot',(int(lead_id),int(source_result_id)))
    folder=_image_dir(lead_id,source_result_id); result=[]
    for row in rows:
        name=Path(str(row['filename'])).name
        file=(folder/name).resolve()
        if file.parent==folder.resolve() and file.is_file() and file.stat().st_size<=25_000_000:
            result.append({'slot':int(row['slot']),'filename':name,'bytes':file.read_bytes()})
    return result

def generate_pack(lead_id,source_result_id,account,token,model):
    initialize(); hit=db.row('SELECT * FROM hunter_results WHERE id=?',(int(source_result_id),))
    chosen=db.row('SELECT 1 FROM studio_selections WHERE lead_id=? AND source_result_id=?',(int(lead_id),int(source_result_id)))
    if not chosen or not hit or not hit.get('thumbnail'):raise ValueError('Válassz ki egy képes termékajánlatot először.')
    raw=auto_stock_photo.download_catalog_image(hit['thumbnail'])
    folder=_image_dir(lead_id,source_result_id); folder.mkdir(parents=True,exist_ok=True)
    source=folder/'supplier_reference.png'; source.write_bytes(raw)
    existing={x['slot'] for x in images(lead_id,source_result_id)}
    for slot,(angle,_) in enumerate(IMAGE_SLOTS,1):
        if slot in existing:continue
        data=cloudflare_photos.generate(source,angle,account,token,model,hit['title'])
        name=f'AI_ILLUSZTRACIO_{slot:02d}.png'; temp=folder/(name+'.tmp'); target=folder/name
        temp.write_bytes(data);temp.replace(target)
        with db.session() as con:
            con.execute('INSERT OR REPLACE INTO studio_image_packs(lead_id,source_result_id,slot,filename,created_at) VALUES(?,?,?,?,?)',(int(lead_id),int(source_result_id),slot,name,db.utcnow()))
    source.unlink(missing_ok=True)
    return images(lead_id,source_result_id)

def posting_zip():
    rows=selected()
    if not rows:raise ValueError('Nincs kiválasztott termék.')
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for order,row in enumerate(rows,1):
            folder=f'{order:02d}_{re.sub(r"[^a-zA-Z0-9]+","_",str(row["title"]).strip()).strip("_")[:50]}'
            offer=row['verified_offer']
            text=(f"{row['title']}\n\n{row['description']}\n\n"
                  f"Irányár: {row['target_price']:,} Ft\n".replace(',',' ') if row['target_price'] else f"{row['title']}\n\n{row['description']}\n\nÁr: ellenőrzés szükséges\n")
            if row['manually_verified'] and row['sold_units']:
                text+=f"Keresleti jel: {row['sold_units']} ellenőrzött eBay-eladás / {row['period_days']} nap.\n"
            else:text+='Keresleti jelek: Google Trends, piactéri keresési találatok és árhistorika az alkalmazásban ellenőrizendő; eBay-eladásszám nincs megadva.\n'
            if offer:text+=f"Beszállító: {offer['supplier']} · termék+szállítás: {offer['total_huf']:,} Ft · 4 munkanapon belüli kézbesítés ellenőrizve.\n".replace(',',' ')
            else:text+='Beszállítói készlet és kézbesítés még nem igazolt.\n'
            text+='Megjegyzés: a mellékelt AI-képek illusztrációk, nem a tényleges termékállapot fotói.\n'
            z.writestr(folder+'/00_hirdetesszoveg.txt',text)
            for image in row['images']:z.writestr(folder+f'/{image["slot"]:02d}_AI_ILLUSZTRACIO.png',image['bytes'])
    return out.getvalue()
