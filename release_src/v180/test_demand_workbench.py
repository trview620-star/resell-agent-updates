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

    def test_demand_lead_requires_manual_completed_sale_evidence(self):
        with self.assertRaises(ValueError):
            work.save_lead('GTA 6 LEGO figura',10,30,12000,'https://www.ebay.de/',manually_verified=False)
        with self.assertRaises(ValueError):
            work.save_lead('GTA 6 LEGO figura',10,30,12000,'https://example.com/',manually_verified=True)
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


if __name__=='__main__':unittest.main()
