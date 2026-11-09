"""Persistent selection, price planning and AI image packs for supplier candidates."""
from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path

import requests
from . import db, auto_stock_photo, cloudflare_photos, demand_workbench, private_research, product_copy

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
        """)

def candidates():
    initialize(); result=[]
    leads={int(x['id']):x for x in demand_workbench.leads()}
    for lead in leads.values():
        for hit in demand_workbench.supplier_candidates(lead['id']):
            hit=dict(hit); hit['lead']=lead
            hit['pace']=30*int(lead['sold_units'])/max(1,int(lead['period_days']))
            hit['verified']=[x for x in demand_workbench.verified_supplier_offers(
                lead['id'],demand_workbench.POSTCODE_DEFAULT) if int(x['source_result_id'])==int(hit['id'])]
            hit['selected']=bool(db.row('SELECT 1 FROM studio_selections WHERE lead_id=? AND source_result_id=?',(lead['id'],hit['id'])))
            result.append(hit)
    return sorted(result,key=lambda x:(not bool(x['verified']),-x['pace'],int(x['price_huf'])))

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
                    FROM studio_selections s JOIN hunter_results h ON h.id=s.source_result_id
                    JOIN demand_leads l ON l.id=s.lead_id''')
    for row in rows:
        # Checks are explicitly confirmed against the same demand phrase/model;
        # use the lowest qualifying offer across the full approved retailer set.
        verified=demand_workbench.verified_supplier_offers(row['lead_id'],demand_workbench.POSTCODE_DEFAULT)
        row['verified_offer']=verified[0] if verified else None
        row['pace']=30*int(row['sold_units'])/max(1,int(row['period_days']))
        row['target_price']=suggested_price(row['vinted_reference_huf'],row['verified_offer']['total_huf'] if row['verified_offer'] else None)
        row['images']=images(row['lead_id'],row['source_result_id'])
        out.append(row)
    return sorted(out,key=lambda r:(-r['pace'],int(r['verified_offer']['total_huf'] if r['verified_offer'] else 10**12),str(r['title']).casefold()))

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
            text+=f"Keresleti jel: {row['sold_units']} eBay-eladás / {row['period_days']} nap; ellenőrizd a forrásoldalon.\n"
            if offer:text+=f"Beszállító: {offer['supplier']} · termék+szállítás: {offer['total_huf']:,} Ft · 4 munkanapon belüli kézbesítés ellenőrizve.\n".replace(',',' ')
            else:text+='Beszállítói készlet és kézbesítés még nem igazolt.\n'
            text+='Megjegyzés: a mellékelt AI-képek illusztrációk, nem a tényleges termékállapot fotói.\n'
            z.writestr(folder+'/00_hirdetesszoveg.txt',text)
            for image in row['images']:z.writestr(folder+f'/{image["slot"]:02d}_AI_ILLUSZTRACIO.png',image['bytes'])
    return out.getvalue()
