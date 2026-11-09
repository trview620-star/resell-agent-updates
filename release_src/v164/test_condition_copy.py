import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from agent import db,hunter,condition_copy as copy

class VerifiedConditionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.patches=[patch.object(db,'ROOT',self.root),
                      patch.object(db,'DATA',self.root/'data'),
                      patch.object(db,'DB_PATH',self.root/'data'/'test.sqlite3'),
                      patch.object(db,'PHOTOS',self.root/'data'/'photos')]
        for p in self.patches:p.start()
        hunter.initialize()
        self.product=db.insert_product({
            'title':'LEGO Ideas 21366 Úszkáló vidrák',
            'brand':'LEGO','model':'21366','category':'Játékok',
            'condition_text':'Unknown / verify',
            'description':hunter.plain_description('LEGO Ideas 21366 Úszkáló vidrák'),
            'supplier':'Store','supplier_url':'https://shop.example.com/lego',
            'supplier_price':19990,'inbound_shipping':0,'outbound_shipping':0,
            'packaging':0,'marketplace_fees':0,'risk_buffer':0,
            'target_price':0,'stock_status':'unknown',
            'stock_verified_at':None,'eta_days':0,
            'fulfillment':db.FULFILLMENT[0],'status':'candidate','notes':''})
        self.lid=db.insert_listing(self.product,'Vinted','LEGO Ideas 21366 Úszkáló vidrák',
                                   hunter.plain_description('LEGO Ideas 21366 Úszkáló vidrák'),0)
        self.ebay=db.insert_listing(self.product,'eBay','LEGO Ideas 21366 Úszkáló vidrák',
                                   hunter.plain_description('LEGO Ideas 21366 Úszkáló vidrák'),0)
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()

    def test_no_unverified_factory_sealed_claim(self):
        with self.assertRaises(ValueError):
            copy.confirm_condition(self.product,'sealed',verified=False)
        p=db.row('SELECT * FROM products WHERE id=?',(self.product,))
        self.assertEqual(copy.state_of(p),'unknown')
        self.assertNotIn('bontatlan',db.row('SELECT * FROM listings WHERE id=?',(self.lid,))['title'])

    def test_confirmed_sealed_goes_in_title_and_description(self):
        copy.confirm_condition(self.product,'sealed',verified=True)
        l=db.row('SELECT * FROM listings WHERE id=?',(self.lid,))
        self.assertIn('Új, bontatlan',l['title'])
        self.assertIn('Állapot: új, bontatlan, gyári csomagolásban.',l['description'])
        self.assertEqual(l['description'].count(copy.FOOTER),1)
        e=db.row('SELECT * FROM listings WHERE id=?',(self.ebay,))
        self.assertNotIn(copy.FOOTER,e['description'])
        self.assertIn('Új, bontatlan',e['title'])
        self.assertEqual(copy.state_of(db.row('SELECT * FROM products WHERE id=?',(self.product,))),'sealed')

    def test_condition_reevaluation_not_duplicate_and_can_downgrade(self):
        copy.confirm_condition(self.product,'sealed',verified=True)
        copy.confirm_condition(self.product,'sealed',verified=True)
        l=db.row('SELECT * FROM listings WHERE id=?',(self.lid,))
        self.assertEqual(l['description'].count('Állapot: új, bontatlan'),1)
        self.assertEqual(l['title'].count('Új, bontatlan'),1)
        copy.confirm_condition(self.product,'new',verified=True)
        l=db.row('SELECT * FROM listings WHERE id=?',(self.lid,))
        self.assertIn('– Új',l['title'])
        self.assertNotIn('bontatlan',l['description'])
        copy.confirm_condition(self.product,'unknown')
        l=db.row('SELECT * FROM listings WHERE id=?',(self.lid,))
        self.assertNotIn('– Új',l['title'])
        self.assertNotIn('Állapot:',l['description'])

    def test_published_listing_never_modified(self):
        db.update_listing(self.lid,status='published')
        before=db.row('SELECT * FROM listings WHERE id=?',(self.lid,))
        copy.confirm_condition(self.product,'sealed',verified=True)
        after=db.row('SELECT * FROM listings WHERE id=?',(self.lid,))
        self.assertEqual(before['title'],after['title'])
        self.assertEqual(before['description'],after['description'])

    def test_long_title_limit_and_preserved_model(self):
        text=copy.title_for('LEGO Ideas 21366 Úszkáló vidrák '+('részlet ' * 15),'sealed')
        self.assertLessEqual(len(text),80)
        self.assertIn('21366',text)
        self.assertTrue(text.endswith('Új, bontatlan'))

if __name__=='__main__':unittest.main()
