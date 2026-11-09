"""Private Resell Agent rules for two marketplaces and thirteen suppliers.

No inferred shipping dates or realised profit are presented as facts.
Price = observed supplier price + manually confirmed costs + fixed HUF 4000.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
import re
import unicodedata

from . import db, hunter, market_intelligence, supplier_links

MARKETS=('Vinted','Jófogás')
MIN_PROFIT=4000
MAX_WORKDAYS=4
SHIPPING_TTL_HOURS=24

# Only these thirteen retailers can feed private dashboard recommendations.
SUPPLIERS=(
    ('Alza','alza.hu',('alza','alza hu')),
    ('MediaMarkt','mediamarkt.hu',('mediamarkt','media markt')),
    ('Euronics','euronics.hu',('euronics',)),
    ('REGIO JÁTÉK','regiojatek.hu',('regio jatek','regiojatek')),
    ('iPon','ipon.hu',('ipon',)),
    ('PCX','pcx.hu',('pcx',)),
    ('AQUA','aqua.hu',('aqua','aqua computer')),
    ('eMAG','emag.hu',('emag',)),
    ('JátékNet','jateknet.hu',('jateknet','jatek net')),
    ('GekkoToys','gekkotoys.hu',('gekkotoys','gekko toys')),
    ('Konzolvilág','konzolvilag.hu',('konzolvilag','konzolvilag hu')),
    ('Reflexshop','reflexshop.hu',('reflexshop',)),
    ('Notebook.hu','notebook.hu',('notebook hu','notebookhu','notebook')),
)


def normalize(value):
    word=unicodedata.normalize('NFKD',str(value or '').casefold())
    return ' '.join(''.join(c for c in word if not unicodedata.combining(c)).split())


def supplier_name(offer):
    merchant=normalize(offer.get('merchant',''))
    raw=str(offer.get('url','') or '')
    try:
        parts=urlsplit(raw)
        host=(parts.hostname or '').casefold().rstrip('.') if parts.scheme=='https' else ''
    except ValueError:
        host=''
    for name,domain,aliases in SUPPLIERS:
        if host and (host==domain or host.endswith('.'+domain)):
            return name
    # A seller claiming to be Alza on an unrelated direct domain is not Alza.
    if supplier_links.direct_url(raw):
        return None
    for name,domain,aliases in SUPPLIERS:
        if merchant in aliases or merchant in (normalize(name),normalize(domain)):
            return name
    return None


def offer_matches_scope(offer):
    return supplier_name(offer) is not None and int(offer.get('price_huf') or 0)>0


def initialize():
    hunter.initialize()
    with db.session() as conn:
        conn.executescript("""
          CREATE TABLE IF NOT EXISTS ra_private_settings(
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS ra_delivery_evidence(
            offer_id INTEGER NOT NULL REFERENCES hunter_results(id) ON DELETE CASCADE,
            postcode TEXT NOT NULL,
            max_workdays INTEGER NOT NULL CHECK(max_workdays BETWEEN 0 AND 60),
            evidence_note TEXT NOT NULL,
            checked_at TEXT NOT NULL,
            PRIMARY KEY(offer_id,postcode)
          );
          CREATE TABLE IF NOT EXISTS ra_profit_costs(
            offer_id INTEGER NOT NULL REFERENCES hunter_results(id) ON DELETE CASCADE,
            marketplace TEXT NOT NULL CHECK(marketplace IN ('Vinted','Jófogás')),
            inbound_huf INTEGER NOT NULL CHECK(inbound_huf >= 0),
            outbound_huf INTEGER NOT NULL CHECK(outbound_huf >= 0),
            packing_huf INTEGER NOT NULL CHECK(packing_huf >= 0),
            fees_huf INTEGER NOT NULL CHECK(fees_huf >= 0),
            reserve_huf INTEGER NOT NULL CHECK(reserve_huf >= 0),
            confirmed_at TEXT NOT NULL,
            PRIMARY KEY(offer_id,marketplace)
          );
        """)


def postcode():
    initialize()
    row=db.row("SELECT value FROM ra_private_settings WHERE name='pest_postcode'")
    return row['value'] if row else ''


def save_postcode(value, confirmed_pest=False):
    code=str(value or '').strip()
    if not re.fullmatch(r'\d{4}',code):
        raise ValueError('Négyjegyű irányítószámot adj meg.')
    if not confirmed_pest:
        raise ValueError('Erősítsd meg, hogy a megadott cím Pest vármegyében található.')
    initialize()
    with db.session() as conn:
        conn.execute("""INSERT INTO ra_private_settings(name,value) VALUES('pest_postcode',?)
                        ON CONFLICT(name) DO UPDATE SET value=excluded.value""",(code,))
    return code


def save_delivery(offer_id,zip_code,workdays,evidence,confirmed=False):
    initialize()
    if not re.fullmatch(r'\d{4}',str(zip_code or '')):
        raise ValueError('Előbb állítsd be a Pest vármegyei irányítószámot.')
    if not confirmed:
        raise ValueError('A konkrét termék és a célirányítószám ellenőrzését igazolni kell.')
    if not isinstance(workdays,int) or not 0<=workdays<=60:
        raise ValueError('Érvénytelen szállítási idő.')
    note=str(evidence or '').strip()
    if len(note)<5:
        raise ValueError('Add meg, hol látható a szállítási határidő.')
    if db.row('SELECT id FROM hunter_results WHERE id=?',(offer_id,)) is None:
        raise ValueError('A beszállítói ajánlat nem található.')
    with db.session() as conn:
        conn.execute("""INSERT INTO ra_delivery_evidence(
          offer_id,postcode,max_workdays,evidence_note,checked_at) VALUES(?,?,?,?,?)
          ON CONFLICT(offer_id,postcode) DO UPDATE SET
          max_workdays=excluded.max_workdays,evidence_note=excluded.evidence_note,
          checked_at=excluded.checked_at
        """,(int(offer_id),str(zip_code),workdays,note,db.utcnow()))


def delivery_state(record,zip_code,now=None):
    if not zip_code or not record:
        return 'unknown'
    if str(record.get('postcode'))!=str(zip_code):
        return 'unknown'
    try:
        checked=datetime.fromisoformat(record['checked_at'].replace('Z','+00:00'))
        if checked.tzinfo is None:
            checked=checked.replace(tzinfo=timezone.utc)
        if (now or datetime.now(timezone.utc))-checked>timedelta(hours=SHIPPING_TTL_HOURS):
            return 'stale'
    except (ValueError,TypeError,KeyError):
        return 'unknown'
    return 'ok' if int(record['max_workdays'])<=MAX_WORKDAYS else 'slow'


def delivery_records(zip_code):
    initialize()
    if not zip_code:
        return {}
    return {r['offer_id']:r for r in db.rows(
        'SELECT * FROM ra_delivery_evidence WHERE postcode=?',(zip_code,))}


def cost_records():
    initialize()
    return {(r['offer_id'],r['marketplace']):r for r in db.rows(
        'SELECT * FROM ra_profit_costs')}


def save_costs(offer_id,marketplace,inbound,outbound,packing,fees,reserve,confirmed=False):
    initialize()
    if marketplace not in MARKETS:
        raise ValueError('Csak Vinted és Jófogás használható.')
    if not confirmed:
        raise ValueError('Ellenőrizd és erősítsd meg az összes költséget.')
    values=(inbound,outbound,packing,fees,reserve)
    if any(type(v) is not int or v<0 or v>10_000_000 for v in values):
        raise ValueError('A költségek csak nemnegatív forintösszegek lehetnek.')
    if db.row('SELECT id FROM hunter_results WHERE id=?',(offer_id,)) is None:
        raise ValueError('Hiányzó beszállítói ajánlat.')
    with db.session() as conn:
        conn.execute("""INSERT INTO ra_profit_costs(
             offer_id,marketplace,inbound_huf,outbound_huf,packing_huf,
             fees_huf,reserve_huf,confirmed_at)
             VALUES(?,?,?,?,?,?,?,?)
             ON CONFLICT(offer_id,marketplace) DO UPDATE SET
             inbound_huf=excluded.inbound_huf,outbound_huf=excluded.outbound_huf,
             packing_huf=excluded.packing_huf,fees_huf=excluded.fees_huf,
             reserve_huf=excluded.reserve_huf,confirmed_at=excluded.confirmed_at
        """,(int(offer_id),marketplace,*values,db.utcnow()))


def price_quote(purchase_huf,costs):
    """No fabricated zero-cost assumptions; unverified inputs yield no quote."""
    price=int(purchase_huf or 0)
    if price<=0 or costs is None:
        return None
    needed=('inbound_huf','outbound_huf','packing_huf','fees_huf','reserve_huf')
    if any(k not in costs for k in needed):
        return None
    subtotal=price+sum(int(costs[k]) for k in needed)
    return {'costs_huf':subtotal,'sale_huf':subtotal+MIN_PROFIT,
            'profit_huf':MIN_PROFIT}


def candidates():
    """Retain real research candidate status and original model matching."""
    initialize()
    rows=market_intelligence.shortlisted()
    for item in rows:
        offers=[dict(o,registered_supplier=supplier_name(o))
                for o in market_intelligence.offers_for(item['phrase'],80)
                if offer_matches_scope(o)]
        item['private_offers']=sorted(offers,key=lambda o:int(o['price_huf']))
        item['supplier_count']=len({o['registered_supplier'] for o in offers})
        item['best_offer']=item['private_offers'][0] if offers else None
    return rows


def is_ready(item,shipping,costs,zip_code):
    for offer in item.get('private_offers',[]):
        if delivery_state(shipping.get(offer['id']),zip_code)!='ok':
            continue
        if any(price_quote(offer['price_huf'],costs.get((offer['id'],market)))
               for market in MARKETS):
            return True
    return False


def shortlist_metrics(items,shipping,costs,zip_code):
    checked=sum(bool(r['checked_at']) for r in items)
    with_offers=sum(bool(r['private_offers']) for r in items)
    fast=sum(any(delivery_state(shipping.get(o['id']),zip_code)=='ok'
                 for o in r['private_offers']) for r in items)
    ready=sum(is_ready(r,shipping,costs,zip_code) for r in items)
    return {'checked':checked,'with_offers':with_offers,'fast':fast,'ready':ready}
