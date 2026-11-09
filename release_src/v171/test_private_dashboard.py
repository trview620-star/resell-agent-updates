"""Private UI data rules: thirteen suppliers, four workdays, fixed 4000 Ft."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

from agent import db, hunter, private_research as rules, market_intelligence


class PrivateWorkspaceRulesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        root=Path(self.tmp.name)
        self.patches=[
            patch.object(db,'ROOT',root),
            patch.object(db,'DATA',root/'data'),
            patch.object(db,'DB_PATH',root/'data'/'db.sqlite3'),
            patch.object(db,'PHOTOS',root/'data'/'photos')
        ]
        for p in self.patches:p.start()
        rules.initialize()
        with db.session() as con:
            self.offer_id=int(con.execute("""
                INSERT INTO hunter_results(
                    url,title,merchant,price_huf,thumbnail,phrase,topic,
                    link_type,found_at,status)
                VALUES (?,?,?,?,?,?,?,?,?,'new')""",
                ('https://www.alza.hu/lego-botanicals-10328',
                 'LEGO Botanicals 10328 Rózsacsokor','Alza.hu',13990,
                 'https://assets.example.com/lego.png',
                 'LEGO Botanicals 10328 Rózsacsokor',
                 'LEGO','direct',db.utcnow())).lastrowid)

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()

    def test_exactly_thirteen_suppliers_and_two_markets(self):
        self.assertEqual(len(rules.SUPPLIERS),13)
        self.assertEqual(rules.MARKETS,('Vinted','Jófogás'))
        self.assertEqual(rules.MIN_PROFIT,4000)
        self.assertEqual(rules.MAX_WORKDAYS,4)
        self.assertEqual(len({s[0] for s in rules.SUPPLIERS}),13)

    def test_supplier_must_match_owned_site_or_known_merchant(self):
        self.assertEqual(rules.supplier_name({'merchant':'Alza.hu',
                         'url':'https://www.alza.hu/lego'}),'Alza')
        self.assertEqual(rules.supplier_name({'merchant':'MediaMarkt',
                         'url':'https://www.google.com/search?q=media+markt'}),'MediaMarkt')
        self.assertIsNone(rules.supplier_name({'merchant':'Alza',
                         'url':'https://fake.example.com/lego'}))
        self.assertIsNone(rules.supplier_name({'merchant':'Amazon',
                         'url':'https://www.amazon.de/dp/123'}))
        self.assertIsNone(rules.supplier_name({'merchant':'Facebook Marketplace',
                         'url':'https://www.facebook.com/marketplace'}))

    def test_static_four_thousand_after_every_cost(self):
        self.assertIsNone(rules.price_quote(12000,None))
        costs={'inbound_huf':990,'outbound_huf':1500,
               'packing_huf':300,'fees_huf':210,'reserve_huf':500}
        result=rules.price_quote(12000,costs)
        self.assertEqual(result['costs_huf'],15500)
        self.assertEqual(result['sale_huf'],19500)
        self.assertEqual(result['profit_huf'],4000)
        # Market comparisons must not invalidate the price.
        self.assertEqual(result['sale_huf'],19500)

    def test_postcode_required_and_persisted(self):
        self.assertEqual(rules.postcode(),'')
        with self.assertRaises(ValueError):
            rules.save_postcode('2112',False)
        with self.assertRaises(ValueError):
            rules.save_postcode('bad',True)
        self.assertEqual(rules.save_postcode('2112',True),'2112')
        self.assertEqual(rules.postcode(),'2112')

    def test_delivery_requires_manual_product_specific_confirmation(self):
        rules.save_postcode('2112',True)
        with self.assertRaises(ValueError):
            rules.save_delivery(self.offer_id,'2112',3,'Kosárban 3 nap',False)
        rules.save_delivery(self.offer_id,'2112',4,
                            'Kosárban visszaigazolt 4 munkanap',True)
        record=rules.delivery_records('2112')[self.offer_id]
        self.assertEqual(rules.delivery_state(record,'2112'),'ok')
        self.assertEqual(rules.delivery_state(record,'2600'),'unknown')
        self.assertEqual(rules.delivery_state(
            record,'2112',now=datetime.now(timezone.utc)+timedelta(hours=25)),
            'stale')
        rules.save_delivery(self.offer_id,'2112',5,
                            'Kosárban igazolt 5 munkanap',True)
        self.assertEqual(rules.delivery_state(
            rules.delivery_records('2112')[self.offer_id],'2112'),'slow')

    def test_cost_save_needs_explicit_confirmation_per_market(self):
        with self.assertRaises(ValueError):
            rules.save_costs(self.offer_id,'Vinted',990,0,300,0,200,False)
        with self.assertRaises(ValueError):
            rules.save_costs(self.offer_id,'eBay',990,0,300,0,200,True)
        rules.save_costs(self.offer_id,'Vinted',990,0,300,0,200,True)
        found=rules.cost_records()
        self.assertIsNone(found.get((self.offer_id,'Jófogás')))
        self.assertEqual(rules.price_quote(13990,found[(self.offer_id,'Vinted')])['sale_huf'],19480)

    def test_candidate_filter_from_real_shopping_results_only(self):
        items=rules.candidates()
        row=next(x for x in items if x['phrase']=='LEGO Botanicals 10328 Rózsacsokor')
        self.assertEqual(len(row['private_offers']),1)
        self.assertEqual(row['supplier_count'],1)
        self.assertEqual(row['best_offer']['registered_supplier'],'Alza')
        counts=rules.shortlist_metrics(items,{},rules.cost_records(),'')
        self.assertEqual(counts['fast'],0)
        self.assertEqual(counts['ready'],0)

    def test_fixed_price_applied_only_to_unpriced_private_drafts(self):
        with db.session() as conn:
            pid=int(conn.execute(
                'INSERT INTO products(title,created_at,updated_at) VALUES(?,?,?)',
                ('LEGO Botanicals 10328',db.utcnow(),db.utcnow())).lastrowid)
        vid=db.insert_listing(pid,'Vinted','LEGO 10328','Draft',0)
        jid=db.insert_listing(pid,'Jófogás','LEGO 10328','Draft',0)
        db.update_listing(jid,price=24000)
        rules.save_costs(self.offer_id,'Vinted',990,0,300,0,200,True)
        quote={'id':self.offer_id,'product_id':pid,'price_huf':13990}
        modified=rules.apply_draft_prices([
            {'listing_id':vid,'marketplace':'Vinted'},
            {'listing_id':jid,'marketplace':'Jófogás'},
        ],quote,rules.cost_records())
        self.assertEqual(modified,['Vinted'])
        self.assertEqual(db.row('SELECT price FROM listings WHERE id=?',(vid,))['price'],19480)
        self.assertEqual(db.row('SELECT price FROM listings WHERE id=?',(jid,))['price'],24000)
        self.assertEqual(rules.apply_draft_prices(
            [{'listing_id':vid,'marketplace':'Vinted'}],quote,rules.cost_records()),[])
        db.update_listing(vid,status='published',url='https://www.vinted.hu/items/abc')
        self.assertEqual(rules.apply_draft_prices(
            [{'listing_id':vid,'marketplace':'Vinted'}],quote,rules.cost_records()),[])

    def test_unverified_supplier_result_not_auto_recommended(self):
        with db.session() as conn:
            conn.execute("""INSERT INTO hunter_results(
              url,title,merchant,price_huf,thumbnail,phrase,topic,
              link_type,found_at,status)
              VALUES(?,?,?,?,?,?,?,?,?,'new')""",
              ('https://some-other-shop.example/lego',
               'LEGO Botanicals 10328 Rózsacsokor','Other Shop',12990,'',
               'LEGO Botanicals 10328 Rózsacsokor','LEGO','direct',db.utcnow()))
        row=next(x for x in rules.candidates() if x['phrase']=='LEGO Botanicals 10328 Rózsacsokor')
        self.assertEqual(len(row['private_offers']),1)


if __name__=='__main__':
    unittest.main()
