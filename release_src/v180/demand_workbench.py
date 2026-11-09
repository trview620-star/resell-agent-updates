"""Demand-led discovery records and supplier verification workflow."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
import re
import unicodedata

from . import db, hunter, market_intelligence, private_research, shopping

POSTCODE_DEFAULT='2600'
CHECK_TTL_HOURS=24


def initialize():
    db.initialize()
    hunter.initialize()
    market_intelligence.initialize()
    with db.session() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS demand_leads(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          phrase TEXT NOT NULL UNIQUE,
          sold_units INTEGER CHECK(sold_units IS NULL OR sold_units>0),
          period_days INTEGER CHECK(period_days IS NULL OR period_days BETWEEN 1 AND 365),
          ebay_median_huf INTEGER CHECK(ebay_median_huf IS NULL OR ebay_median_huf>0),
          evidence_url TEXT NOT NULL DEFAULT '',
          manually_verified INTEGER NOT NULL CHECK(manually_verified IN (0,1)),
          checked_at TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
          ,CHECK(manually_verified=0 OR (sold_units IS NOT NULL AND period_days IS NOT NULL AND evidence_url<>''))
        );
        CREATE TABLE IF NOT EXISTS demand_supplier_checks(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          lead_id INTEGER NOT NULL REFERENCES demand_leads(id) ON DELETE CASCADE,
          source_result_id INTEGER NOT NULL REFERENCES hunter_results(id) ON DELETE CASCADE,
          supplier TEXT NOT NULL,
          title TEXT NOT NULL,
          url TEXT NOT NULL,
          unit_price_huf INTEGER NOT NULL CHECK(unit_price_huf>0),
          shipping_huf INTEGER NOT NULL CHECK(shipping_huf>=0),
          stock_status TEXT NOT NULL CHECK(stock_status IN ('available','unavailable','unknown')),
          postcode TEXT NOT NULL,
          shipping_method TEXT NOT NULL,
          max_workdays INTEGER CHECK(max_workdays IS NULL OR max_workdays BETWEEN 0 AND 60),
          delivery_guaranteed INTEGER NOT NULL CHECK(delivery_guaranteed IN (0,1)),
          exact_match_confirmed INTEGER NOT NULL CHECK(exact_match_confirmed IN (0,1)),
          evidence_note TEXT NOT NULL,
          checked_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_demand_checks_lead ON demand_supplier_checks(lead_id,checked_at);
        """)
    _migrate_optional_sold_evidence()


def _migrate_optional_sold_evidence():
    """Allow a search term without fake eBay sales, preserving child records."""
    sql=db.row("SELECT sql FROM sqlite_master WHERE type='table' AND name='demand_leads'")
    if not sql or 'sold_units INTEGER NOT NULL' not in str(sql['sql']):return
    con=db.connect()
    try:
        con.execute('PRAGMA foreign_keys=OFF')
        con.execute('BEGIN IMMEDIATE')
        parent=[dict(r) for r in con.execute('SELECT * FROM demand_leads')]
        children=[];indexes=[]
        for row in con.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            name=row['name']
            if name=='demand_leads':continue
            refs=con.execute(f'PRAGMA foreign_key_list("{name}")').fetchall()
            if any(fk['table']=='demand_leads' for fk in refs):
                create=con.execute('SELECT sql FROM sqlite_master WHERE type=\'table\' AND name=?',(name,)).fetchone()['sql']
                rows=[dict(x) for x in con.execute(f'SELECT * FROM "{name}"')]
                children.append((name,create,rows))
        child_names={name for name,_,_ in children}|{'demand_leads'}
        for row in con.execute("SELECT tbl_name,sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"):
            if row['tbl_name'] in child_names:indexes.append(row['sql'])
        for name,_,_ in children:con.execute(f'DROP TABLE "{name}"')
        con.execute('DROP TABLE demand_leads')
        con.execute('''CREATE TABLE demand_leads(
          id INTEGER PRIMARY KEY AUTOINCREMENT,phrase TEXT NOT NULL UNIQUE,
          sold_units INTEGER CHECK(sold_units IS NULL OR sold_units>0),
          period_days INTEGER CHECK(period_days IS NULL OR period_days BETWEEN 1 AND 365),
          ebay_median_huf INTEGER CHECK(ebay_median_huf IS NULL OR ebay_median_huf>0),
          evidence_url TEXT NOT NULL DEFAULT '',manually_verified INTEGER NOT NULL CHECK(manually_verified IN (0,1)),
          checked_at TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
          CHECK(manually_verified=0 OR (sold_units IS NOT NULL AND period_days IS NOT NULL AND evidence_url<>'')))''')
        for row in parent:
            columns=list(row);con.execute('INSERT INTO demand_leads('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')',[row[c] for c in columns])
        for name,create,rows in children:
            con.execute(create)
            for row in rows:
                columns=list(row);con.execute(f'INSERT INTO "{name}"('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')',[row[c] for c in columns])
        for statement in indexes:con.execute(statement)
        con.commit()
    except Exception:
        con.rollback();raise
    finally:con.close()


def save_lead(phrase, sold_units=None, period_days=None, ebay_median_huf=None, evidence_url='',
              *, manually_verified=False):
    initialize()
    phrase=' '.join(str(phrase or '').split())
    if not 3<=len(phrase)<=120:
        raise ValueError('Adj meg 3–120 karakteres terméknevet vagy modellt.')
    if manually_verified and (type(sold_units) is not int or not 1<=sold_units<=100000):
        raise ValueError('Az ellenőrzött eladásszám 1 és 100 000 közötti egész szám legyen.')
    if manually_verified and (type(period_days) is not int or not 1<=period_days<=365):
        raise ValueError('Az ellenőrzött időszak 1–365 nap legyen.')
    if not manually_verified and (sold_units is not None or period_days is not None or ebay_median_huf is not None):
        raise ValueError('eBay-eladási adatot csak forrásoldali ellenőrzés után ments.')
    if ebay_median_huf is not None and (type(ebay_median_huf) is not int or ebay_median_huf<=0):
        raise ValueError('Az eBay mediánár forintban megadott, pozitív egész szám legyen.')
    url=str(evidence_url or '').strip()
    parts=None
    try:
        parts=urlsplit(url)
        host=(parts.hostname or '').lower()
    except ValueError:
        host=''
    ebay_domains=('ebay.com','ebay.de','ebay.co.uk','ebay.fr','ebay.it','ebay.es','ebay.nl','ebay.at','ebay.pl')
    if manually_verified and (not parts or parts.scheme not in ('https','http') or not host or not any(host==domain or host.endswith('.'+domain) for domain in ebay_domains)):
        raise ValueError('Az eladási bizonyíték linkje egy eBay Sold oldal legyen.')
    now=db.utcnow()
    existing=db.row('SELECT * FROM demand_leads WHERE phrase=?',(phrase,))
    if existing and not manually_verified and existing['manually_verified']:
        return existing
    with db.session() as con:
        con.execute("""INSERT INTO demand_leads(phrase,sold_units,period_days,ebay_median_huf,
             evidence_url,manually_verified,checked_at,created_at,updated_at)
             VALUES(?,?,?,?,?,?,?,?,?)
             ON CONFLICT(phrase) DO UPDATE SET sold_units=excluded.sold_units,
             period_days=excluded.period_days,ebay_median_huf=excluded.ebay_median_huf,
             evidence_url=excluded.evidence_url,manually_verified=excluded.manually_verified,
             checked_at=excluded.checked_at,updated_at=excluded.updated_at""",
             (phrase,sold_units,period_days,ebay_median_huf,url,int(bool(manually_verified)),now,now,now))
    return db.row('SELECT * FROM demand_leads WHERE phrase=?',(phrase,))


def leads():
    initialize()
    values=db.rows('SELECT * FROM demand_leads')
    return sorted(values,key=lambda r:(-float(r['sold_units'] or 0)/max(1,int(r['period_days'] or 1)),r['phrase'].casefold()))


def scan_suppliers(lead_id, api_key):
    initialize()
    lead=db.row('SELECT * FROM demand_leads WHERE id=?',(int(lead_id),))
    if not lead:
        raise ValueError('A keresleti jel nem található.')
    return market_intelligence.scan_keyword(api_key,lead['phrase'],'Keresletvezérelt radar')


def _tokens(value):
    raw=unicodedata.normalize('NFKD',str(value or '').casefold())
    raw=''.join(ch for ch in raw if not unicodedata.combining(ch))
    stop={'the','and','for','with','new','set','from','pcs','piece','pieces','darab','db','hasznalt'}
    return {x for x in re.findall(r'[a-z0-9]{2,}',raw) if x not in stop}


def supplier_candidates(lead_id):
    initialize()
    lead=db.row('SELECT * FROM demand_leads WHERE id=?',(int(lead_id),))
    if not lead:return []
    rows=db.rows('SELECT * FROM hunter_results WHERE phrase=? ORDER BY found_at DESC,price_huf ASC',(lead['phrase'],))
    output=[]
    code=shopping.model_code_from_phrase(lead['phrase'])
    wanted=_tokens(lead['phrase'])
    for row in rows:
        if not private_research.offer_matches_scope(row):
            continue
        supplier=private_research.supplier_name(row)
        if not supplier:continue
        match,reason=shopping.classify_product_match(row['title'],lead['phrase'])
        title_tokens=_tokens(row['title'])
        overlap=len(wanted & title_tokens)/max(1,len(wanted))
        if code:
            if match!='Model code matches':continue
            confidence='Modellszám egyezik'
        else:
            if overlap<0.5:continue
            confidence='Hasonló névegyezés – ellenőrizd'
        output.append(dict(row,supplier=supplier,confidence=confidence,
                           match_note=reason,token_overlap=overlap))
    # De-duplicate repeat results for a retailer and normalized item title; retain cheapest.
    grouped={}
    for row in output:
        norm=' '.join(sorted(_tokens(row['title'])))
        key=(row['supplier'],norm)
        if key not in grouped or int(row['price_huf'])<int(grouped[key]['price_huf']):
            grouped[key]=row
    return sorted(grouped.values(),key=lambda x:(int(x['price_huf']),x['supplier'],x['title'].casefold()))


def save_supplier_check(lead_id,source_result_id,*,url,price_huf,shipping_huf,
        stock_status,postcode,shipping_method,max_workdays,delivery_guaranteed,
        exact_match_confirmed,evidence_note):
    initialize()
    lead=db.row('SELECT * FROM demand_leads WHERE id=?',(int(lead_id),))
    hit=db.row('SELECT * FROM hunter_results WHERE id=?',(int(source_result_id),))
    if not lead or not hit or hit['phrase']!=lead['phrase']:
        raise ValueError('A keresleti jelhez tartozó beszállítói találat nem található.')
    supplier=private_research.supplier_name(hit)
    if not supplier:
        raise ValueError('A találat nem tartozik a 13 engedélyezett beszállítóhoz.')
    url=str(url or '').strip()
    if private_research.supplier_name(dict(hit,url=url))!=supplier or not private_research.supplier_links.direct_url(url):
        raise ValueError('A közvetlen termékoldalnak a kiválasztott beszállító domainjére kell mutatnia.')
    if type(price_huf) is not int or price_huf<=0 or type(shipping_huf) is not int or shipping_huf<0:
        raise ValueError('A termékár pozitív, a szállítási díj nemnegatív forintösszeg legyen.')
    if stock_status not in ('available','unavailable','unknown'):
        raise ValueError('Érvénytelen készletállapot.')
    if not re.fullmatch(r'\d{4}',str(postcode or '')):
        raise ValueError('Négyjegyű irányítószám szükséges.')
    if not str(shipping_method or '').strip():
        raise ValueError('Add meg az ellenőrzött szállítási módot.')
    if max_workdays is not None and (type(max_workdays) is not int or not 0<=max_workdays<=60):
        raise ValueError('Érvénytelen szállítási munkanap.')
    note=' '.join(str(evidence_note or '').split())
    if len(note)<8:
        raise ValueError('Írd le, hol ellenőrizted az árat, készletet és kézbesítési ígéretet.')
    if not exact_match_confirmed:
        raise ValueError('A termék pontos modellazonosságát meg kell erősíteni.')
    if delivery_guaranteed and (max_workdays is None or max_workdays>4):
        raise ValueError('A legfeljebb 4 munkanapos, kifejezett vállalást kell igazolni.')
    with db.session() as con:
        con.execute("""INSERT INTO demand_supplier_checks(lead_id,source_result_id,supplier,title,url,
            unit_price_huf,shipping_huf,stock_status,postcode,shipping_method,max_workdays,
            delivery_guaranteed,exact_match_confirmed,evidence_note,checked_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (int(lead_id),int(source_result_id),supplier,hit['title'],url,int(price_huf),
             int(shipping_huf),stock_status,str(postcode),str(shipping_method).strip()[:100],
             max_workdays,int(bool(delivery_guaranteed)),1,note[:600],db.utcnow()))


def verified_supplier_offers(lead_id,postcode,*,now=None):
    initialize()
    rows=db.rows('SELECT * FROM demand_supplier_checks WHERE lead_id=? ORDER BY checked_at DESC,id DESC',(int(lead_id),))
    latest={}
    for row in rows:
        key=(row['supplier'],row['url'])
        if key not in latest:latest[key]=row
    now=now or datetime.now(timezone.utc)
    ready=[]
    for row in latest.values():
        try:
            checked=datetime.fromisoformat(str(row['checked_at']).replace('Z','+00:00'))
            if checked.tzinfo is None:checked=checked.replace(tzinfo=timezone.utc)
            fresh=timedelta(0)<=now-checked<=timedelta(hours=CHECK_TTL_HOURS)
        except (TypeError,ValueError):fresh=False
        eligible=(fresh and row['postcode']==str(postcode) and row['stock_status']=='available'
                  and row['exact_match_confirmed'] and row['delivery_guaranteed']
                  and row['max_workdays'] is not None and int(row['max_workdays'])<=4)
        if eligible:ready.append(dict(row,total_huf=int(row['unit_price_huf'])+int(row['shipping_huf'])))
    return sorted(ready,key=lambda r:(r['total_huf'],r['supplier']))


def recent_checks(lead_id):
    initialize()
    return db.rows('SELECT * FROM demand_supplier_checks WHERE lead_id=? ORDER BY checked_at DESC,id DESC LIMIT 30',(int(lead_id),))
