import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from datetime import datetime,timezone,timedelta,date
from unittest.mock import patch
from PIL import Image
from agent import db,extra_db,opportunities,event_radar,photo_studio,publisher,backup
from agent.photos import save_photo

class CommandCenterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.home=Path(self.tmp.name)
        self.patches=[patch.object(db,'ROOT',self.home),
            patch.object(db,'DATA',self.home/'data'),
            patch.object(db,'DB_PATH',self.home/'data'/'resell_agent.sqlite3'),
            patch.object(db,'PHOTOS',self.home/'data'/'photos'),
            patch.object(backup,'BACKUPS',self.home/'backups')]
        for p in self.patches:p.start()
        extra_db.initialize()
        self.product=db.insert_product({
            'title':'LEGO 42154','brand':'LEGO','model':'42154',
            'category':'Toys','condition_text':'New (verified)','description':'LEGO Ford GT',
            'supplier':'Example','supplier_url':'https://example.org/lego',
            'supplier_price':20000,'inbound_shipping':1000,'outbound_shipping':1000,
            'packaging':200,'marketplace_fees':400,'risk_buffer':400,
            'target_price':32990,'stock_status':'available','stock_verified_at':db.utcnow(),
            'eta_days':1,'fulfillment':db.FULFILLMENT[0],'status':'candidate','notes':''})

    def tearDown(self):
        for p in self.patches[::-1]:p.stop()
        self.tmp.cleanup()

    def info(self):
        return db.row('SELECT * FROM products WHERE id=?',(self.product,))

    def test_without_evidence_not_qualified(self):
        r=opportunities.analyze_product(self.info(),[],[])
        self.assertNotEqual(r['status'],'Qualified for review')
        self.assertIsNone(r['suggested_price_huf'])

    def test_verified_sales_and_supplier_quote(self):
        timestamp=datetime.now(timezone.utc).isoformat()
        for value in [35000,33000,34000]:
            db.add_resale_comparable(self.product,marketplace='Vatera',
                url='https://example.org/sold',price_huf=value,completed_sale=True,
                condition_text='exact complete set')
        db.add_supplier_offer(self.product,supplier='Example',url='https://example.org/lego',
            price_huf=20000,shipping_huf=1000,eta_days=1,stock_status='available')
        r=opportunities.rank_database()[0]
        self.assertEqual(r['suggested_price_huf'],34000)
        self.assertEqual(r['status'],'Qualified for review')
        self.assertEqual(r['completed_comps'],3)

    def test_outdated_supplier_quote_requires_review(self):
        old=(datetime.now(timezone.utc)-timedelta(days=5)).isoformat()
        offers=[{'price_huf':20000,'shipping_huf':0,'stock_status':'available',
                 'observed_at':old,'url':'https://example.org'}]
        comps=[{'price_huf':32000,'completed_sale':1,'observed_at':db.utcnow()}]*3
        r=opportunities.analyze_product(self.info(),offers,comps)
        self.assertNotEqual(r['status'],'Qualified for review')
        self.assertIn('No supplier quote from the last 72 hours',r['warnings'])

    def test_negative_profit_not_qualified(self):
        r=opportunities.analyze_product(self.info(),[{
            'price_huf':50000,'shipping_huf':500,'stock_status':'available',
            'observed_at':db.utcnow(),'eta_days':1}],[
            {'price_huf':10000,'completed_sale':1,'observed_at':db.utcnow()}]*3)
        self.assertEqual(r['status'],'Reject / pause')

    def test_order_alerts(self):
        l=[{'product_id':self.product,'status':'published','marketplace':'Vinted'}]
        o=[{'id':7,'product_id':self.product,'marketplace':'Jófogás',
            'status':'received','due_date':date.today().isoformat()}]
        alerts=opportunities.fulfillment_flags(o,l,today=date.today())
        self.assertEqual(len(alerts),2)

    def test_event_match_not_assumed_demand(self):
        events=[{'name':'Gaming release','event_date':(date.today()+timedelta(days=10)).isoformat(),
                 'product_ideas':'LEGO gaming'}]
        self.assertEqual(len(event_radar.candidate_event_matches(self.info(),events)),1)

    def test_seven_packets_and_draft_idempotency(self):
        a=publisher.prepare_drafts(self.product)
        b=publisher.prepare_drafts(self.product)
        self.assertEqual(a,b)
        self.assertEqual(len(a),7)
        content=publisher.listing_package(self.product)
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            self.assertEqual(len([x for x in z.namelist() if x.startswith('listings/')]),7)
            self.assertIn('master.json',z.namelist())
            self.assertIn('LEGO',z.read('listings/Vinted.txt').decode())

    def test_non_destructive_photo_studio(self):
        b=io.BytesIO()
        Image.new('RGB',(48,48),'red').save(b,'PNG')
        save_photo(self.product,'red.png',b.getvalue())
        photo=db.row('SELECT * FROM photos WHERE product_id=?',(self.product,))
        original=db.PHOTOS/photo['filename']
        copy=photo_studio.improve_light(photo['id'])
        self.assertTrue(copy.is_file())
        self.assertEqual(original.read_bytes(),b.getvalue())
        archive=backup.make_backup()
        with zipfile.ZipFile(archive) as z:
            self.assertTrue(any('enhanced_' in x for x in z.namelist()))

    def test_ebay_adapter_does_not_publish_with_incomplete_fields(self):
        client=publisher.EbayInventory('secret','sandbox')
        with patch.object(client,'_call') as call:
            with self.assertRaises(ValueError):
                client.publish(sku='x',title='Y',description='Z',price='0',
                    currency='EUR',category_id='1',condition='NEW',
                    merchant_location_key='x',marketplace_id='EBAY_DE',
                    payment_policy_id='a',return_policy_id='b',
                    fulfillment_policy_id='c',image_urls=['https://example.org/a.jpg'],
                    aspects={'Brand':['Example']})
            call.assert_not_called()

if __name__=='__main__':unittest.main()
