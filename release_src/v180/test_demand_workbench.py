"""Evidence and supplier-scope tests for the demand-first workbench."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from agent import db, hunter, demand_workbench as work


class DemandWorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();root=Path(self.tmp.name)
        self.patches=[patch.object(db,'ROOT',root),patch.object(db,'DATA',root/'data'),
                      patch.object(db,'DB_PATH',root/'data'/'db.sqlite3'),
                      patch.object(db,'PHOTOS',root/'data'/'photos')]
        for p in self.patches:p.start()
        work.initialize()
        with db.session() as con:
            con.execute("""INSERT INTO hunter_results(url,title,merchant,price_huf,thumbnail,
              phrase,topic,link_type,found_at) VALUES(?,?,?,?,?,?,?,?,?)""",
              ('https://www.alza.hu/gta-figure','GTA 6 LEGO Minifigura','Alza.hu',8990,'',
               'GTA 6 LEGO figura','Keresletvezérelt radar','direct',db.utcnow()))
            con.execute("""INSERT INTO hunter_results(url,title,merchant,price_huf,thumbnail,
              phrase,topic,link_type,found_at) VALUES(?,?,?,?,?,?,?,?,?)""",
              ('https://www.randomshop.example/gta','GTA 6 LEGO figura','RandomShop',7990,'',
               'GTA 6 LEGO figura','Keresletvezérelt radar','direct',db.utcnow()))

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()

    def create_lead(self):
        return work.save_lead('GTA 6 LEGO figura',10,30,12000,
            'https://www.ebay.de/sch/i.html?_nkw=gta+6&LH_Sold=1&LH_Complete=1',
            manually_verified=True)

    def test_actual_sold_data_is_optional_but_requires_evidence_when_supplied(self):
        with self.assertRaises(ValueError):
            work.save_lead('GTA 6 LEGO figura',10,30,12000,'',manually_verified=True)
        with self.assertRaises(ValueError):
            work.save_lead('GTA 6 LEGO figura',10,30,12000,'https://example.com/',manually_verified=True)
        search=work.save_lead('GTA 6 LEGO figura')
        self.assertIsNone(search['sold_units'])
        self.assertFalse(search['manually_verified'])
        lead=self.create_lead()
        self.assertEqual(lead['sold_units'],10)
        self.assertEqual(work.leads()[0]['phrase'],'GTA 6 LEGO figura')

    def test_only_thirteen_approved_suppliers_are_returned(self):
        lead=self.create_lead()
        results=work.supplier_candidates(lead['id'])
        self.assertEqual(len(results),1)
        self.assertEqual(results[0]['supplier'],'Alza')
        self.assertEqual(results[0]['price_huf'],8990)

    def test_only_fresh_confirmed_exact_four_day_delivery_qualifies(self):
        lead=self.create_lead()
        hit=db.row('SELECT * FROM hunter_results WHERE merchant=?',('Alza.hu',))
        work.save_supplier_check(lead['id'],hit['id'],url=hit['url'],price_huf=8990,shipping_huf=500,
            stock_status='available',postcode='2600',shipping_method='Házhozszállítás',max_workdays=4,
            delivery_guaranteed=True,exact_match_confirmed=True,evidence_note='Kosárban vállalt dátum ellenőrizve.')
        best=work.verified_supplier_offers(lead['id'],'2600')
        self.assertEqual(best[0]['total_huf'],9490)
        self.assertEqual(work.verified_supplier_offers(lead['id'],'2112'),[])
        with db.session() as con:
            con.execute('UPDATE demand_supplier_checks SET checked_at=?',(db.utcnow(),))
        stale=work.verified_supplier_offers(lead['id'],'2600',now=datetime.now(timezone.utc)+timedelta(hours=25))
        self.assertEqual(stale,[])

    def test_legacy_database_migration_preserves_sales_and_supplier_checks(self):
        hit=db.row('SELECT * FROM hunter_results WHERE merchant=?',('Alza.hu',))
        with db.session() as con:
            con.execute('PRAGMA foreign_keys=OFF')
            con.execute('DROP TABLE demand_supplier_checks')
            con.execute('DROP TABLE demand_leads')
            con.execute('''CREATE TABLE demand_leads(
              id INTEGER PRIMARY KEY AUTOINCREMENT,phrase TEXT NOT NULL UNIQUE,
              sold_units INTEGER NOT NULL CHECK(sold_units>0),
              period_days INTEGER NOT NULL CHECK(period_days BETWEEN 1 AND 365),
              ebay_median_huf INTEGER,evidence_url TEXT NOT NULL,
              manually_verified INTEGER NOT NULL,checked_at TEXT NOT NULL,
              created_at TEXT NOT NULL,updated_at TEXT NOT NULL)''')
            con.execute('''INSERT INTO demand_leads VALUES(1,?,?,?,?,?,?,?,?,?)''',
              ('Korábbi termék',4,30,10000,'https://www.ebay.de/sch/i.html?LH_Sold=1',1,
               db.utcnow(),db.utcnow(),db.utcnow()))
            con.execute('''CREATE TABLE demand_supplier_checks(
              id INTEGER PRIMARY KEY AUTOINCREMENT,lead_id INTEGER NOT NULL REFERENCES demand_leads(id) ON DELETE CASCADE,
              source_result_id INTEGER NOT NULL REFERENCES hunter_results(id) ON DELETE CASCADE,
              supplier TEXT NOT NULL,title TEXT NOT NULL,url TEXT NOT NULL,unit_price_huf INTEGER NOT NULL,
              shipping_huf INTEGER NOT NULL,stock_status TEXT NOT NULL,postcode TEXT NOT NULL,
              shipping_method TEXT NOT NULL,max_workdays INTEGER,delivery_guaranteed INTEGER NOT NULL,
              exact_match_confirmed INTEGER NOT NULL,evidence_note TEXT NOT NULL,checked_at TEXT NOT NULL)''')
            con.execute('''CREATE TABLE studio_selections(
              lead_id INTEGER NOT NULL REFERENCES demand_leads(id) ON DELETE CASCADE,
              source_result_id INTEGER NOT NULL REFERENCES hunter_results(id) ON DELETE CASCADE,
              vinted_reference_huf INTEGER,description TEXT NOT NULL DEFAULT '',selected_at TEXT NOT NULL,
              PRIMARY KEY(lead_id,source_result_id))''')
            con.execute('''CREATE TABLE studio_image_packs(
              lead_id INTEGER NOT NULL,source_result_id INTEGER NOT NULL,slot INTEGER NOT NULL,
              filename TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(lead_id,source_result_id,slot),
              FOREIGN KEY(lead_id,source_result_id) REFERENCES studio_selections(lead_id,source_result_id) ON DELETE CASCADE)''')
            con.execute('CREATE INDEX ix_demand_checks_lead ON demand_supplier_checks(lead_id,checked_at)')
            con.execute('''INSERT INTO demand_supplier_checks(lead_id,source_result_id,supplier,title,url,
              unit_price_huf,shipping_huf,stock_status,postcode,shipping_method,max_workdays,
              delivery_guaranteed,exact_match_confirmed,evidence_note,checked_at)
              VALUES(1,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
              (hit['id'],'Alza',hit['title'],hit['url'],8990,500,'available','2600','Házhoz',4,1,1,
               'Ellenőrzött régi adat',db.utcnow()))
            con.execute('INSERT INTO studio_selections VALUES(1,?,14900,?,?)',
                        (hit['id'],'Régi leírás',db.utcnow()))
            con.execute('INSERT INTO studio_image_packs VALUES(1,?,1,?,?)',
                        (hit['id'],'AI_ILLUSZTRACIO_01.png',db.utcnow()))
        work.initialize()
        self.assertEqual(db.row('SELECT sold_units FROM demand_leads WHERE id=1')['sold_units'],4)
        self.assertEqual(db.row('SELECT evidence_note FROM demand_supplier_checks WHERE lead_id=1')['evidence_note'],'Ellenőrzött régi adat')
        self.assertEqual(db.row('SELECT description FROM studio_selections WHERE lead_id=1')['description'],'Régi leírás')
        self.assertEqual(db.row('SELECT filename FROM studio_image_packs WHERE lead_id=1')['filename'],'AI_ILLUSZTRACIO_01.png')
        self.assertEqual(len(work.verified_supplier_offers(1,'2600')),1)
        with db.connect() as con:self.assertEqual(con.execute('PRAGMA foreign_key_check').fetchall(),[])
        self.assertIsNone(work.save_lead('Keresési adat eBay nélkül')['sold_units'])


if __name__=='__main__':unittest.main()
