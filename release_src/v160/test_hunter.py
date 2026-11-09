import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
from agent import hunter,db,shopping,extra_db

class HunterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.patches=[patch.object(db,'ROOT',self.root),
                      patch.object(db,'DATA',self.root/'data'),
                      patch.object(db,'DB_PATH',self.root/'data'/'test.sqlite3'),
                      patch.object(db,'PHOTOS',self.root/'data'/'photos')]
        for p in self.patches:p.start()
        hunter.initialize()
        self.source_a={'title':'LED fényfüzér 2m karácsony','price_huf':3900,
            'url':'https://example.org/product/holiday-led','merchant':'Test Shop',
            'kind':'Direct-domain link (checkout not verified)','stock_status':'unknown',
            'shipping_huf':0,'eta_days':None,'brand':'','category':''}
        self.source_b=dict(self.source_a,title='Karácsonyi dekoráció ablak',
            price_huf=4900,url='https://example.org/product/holiday-window')
        self.mock_payload={'shopping_results':[
          {'title':self.source_a['title'],'source':'Test Shop',
           'imageUrl':'https://example.org/led.png','price':'3 900 Ft',
           'link':self.source_a['url']},
          {'title':self.source_b['title'],'source':'Test Shop',
           'imageUrl':'http://localhost/private','price':'4 900 Ft',
           'link':self.source_b['url']}]}

    def tearDown(self):
        for p in self.patches[::-1]:p.stop()
        self.temp.cleanup()

    def _insert(self):
        with db.session() as con:
            cur=con.execute("""INSERT INTO hunter_results
                (url,title,merchant,price_huf,thumbnail,phrase,topic,link_type,found_at)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (self.source_a['url'],self.source_a['title'],'Test Shop',3900,'',
                 'karácsony','Karácsony','Direct-domain link',db.utcnow()))
            return int(cur.lastrowid)

    def test_scan_persists_deduplicated_real_huf_offers(self):
        with patch.object(shopping,'fetch_serper_results',return_value=self.mock_payload) as calls:
            result=hunter.scan('fake-serper','Karácsony',3)
        self.assertEqual(calls.call_count,3)
        self.assertEqual(result['queries'],3)
        saved=hunter.offers(topic='Karácsony')
        self.assertEqual(len(saved),2)
        self.assertEqual(sorted(x['price_huf'] for x in saved),[3900,4900])
        self.assertEqual(next(x for x in saved if x['price_huf']==4900)['thumbnail'],'')
        self.assertTrue(next(x for x in saved if x['price_huf']==3900)['thumbnail'].startswith('https://'))
        self.assertTrue(all(x['status']=='new' for x in saved))

    def test_no_key_does_not_scan_or_invent_products(self):
        with patch.object(shopping,'fetch_serper_results') as send:
            with self.assertRaises(ValueError):
                hunter.scan('','Karácsony',6)
            send.assert_not_called()
        self.assertEqual(hunter.offers(topic='Karácsony'),[])

    def test_invalid_search_count(self):
        with self.assertRaises(ValueError):
            hunter.scan('key','Karácsony',100)

    def test_select_idempotent_unknown_stock_and_zero_resale_price(self):
        hid=self._insert()
        first=hunter.select_offer(hid)
        second=hunter.select_offer(hid)
        self.assertEqual(first,second)
        p=db.row('SELECT * FROM products WHERE id=?',(first,))
        self.assertEqual(p['stock_status'],'unknown')
        self.assertEqual(p['target_price'],0)
        self.assertIn('ellenőrizve',p['notes'])

    def test_prepare_one_and_all_seven_marketplaces(self):
        hid=self._insert()
        answer=hunter.prepare(hid,db.PLATFORMS,use_ai=False)
        second=hunter.prepare(hid,db.PLATFORMS,use_ai=False)
        self.assertEqual(answer['product_id'],second['product_id'])
        self.assertEqual(len(answer['drafts']),7)
        self.assertEqual(len(db.rows('SELECT * FROM listings')),7)
        self.assertEqual(db.row('SELECT status FROM hunter_results WHERE id=?',(hid,))['status'],'prepared')
        item=db.row('SELECT * FROM listings WHERE marketplace="Vinted"')
        self.assertIn('Hasonló termékekért',item['description'])
        self.assertNotIn('készleten',item['description'].lower())
        self.assertEqual(item['price'],0)

    def test_cloudflare_generated_hungarian_copy_and_account_redaction(self):
        hid=self._insert()
        result=Mock(ok=True,status_code=200)
        result.json.return_value={'result':{'response':'Eladó fényfüzér, ünnepi dekorációnak. '
            'Ha érdekel, írj nyugodtan.\n\nHasonló termékekért nézd meg a többi hirdetésemet.'}}
        with patch.object(hunter.requests,'post',return_value=result) as post:
            outcome=hunter.prepare(hid,['Jófogás'],account='a'*32,token='FAKE-CF-TOKEN',use_ai=True)
        self.assertEqual(outcome['description_source'],'AI')
        self.assertIn('gemma-4-26b-a4b-it',post.call_args.args[0])
        p=db.row('SELECT * FROM products WHERE id=?',(outcome['product_id'],))
        self.assertNotIn('FAKE-CF-TOKEN',str(p))

    def test_ai_failure_does_not_block_drafts(self):
        hid=self._insert()
        with patch.object(hunter.requests,'post',side_effect=Exception('no network')):
            # requests layer normally raises requests.RequestException; use a provider HTTP error.
            pass
        r=Mock(ok=False,status_code=503)
        with patch.object(hunter.requests,'post',return_value=r):
            result=hunter.prepare(hid,['Jófogás'],account='b'*32,token='FAKE-CF-TOKEN',use_ai=True)
        self.assertIn('AI nem elérhető',result['description_source'])
        self.assertEqual(len(result['drafts']),1)

    def test_do_not_autopost_without_stock_price_or_photo(self):
        hid=self._insert()
        hunter.prepare(hid,['eBay'],use_ai=False)
        with patch('agent.publisher.EbayInventory') as cls:
            with self.assertRaises(ValueError):
                hunter.publish_ebay(hid,'FAKE-OAUTH-TOKEN',{})
            cls.assert_not_called()

    def test_sandbox_ebay_does_not_mark_live(self):
        hid=self._insert()
        result=hunter.prepare(hid,['eBay'],use_ai=False)
        pid=result['product_id']
        db.update_product(pid,stock_status='available',stock_verified_at=db.utcnow(),target_price=15000)
        draft=db.row('SELECT * FROM listings WHERE product_id=? AND marketplace="eBay"',(pid,))
        db.update_listing(draft['id'],price=15000)
        profile={
            'environment':'sandbox','market_price':'35.50','currency':'EUR','sku':'sku-1',
            'marketplace_id':'EBAY_DE','category_id':'123','condition':'NEW',
            'merchant_location_key':'MY-LOCATION','payment_policy_id':'A',
            'return_policy_id':'B','fulfillment_policy_id':'C',
            'image_urls':['https://example.org/owned_photo.jpg'],
            'aspects':{'Brand':['Test Shop']},'confirmed_source_photo':True}
        with patch('agent.publisher.EbayInventory') as adapter:
            adapter.return_value.publish.return_value={'listing_id':'abc123','offer_id':'mock'}
            output=hunter.publish_ebay(hid,'FAKE-OAUTH-TOKEN',profile)
            self.assertEqual(output['mode'],'sandbox')
            self.assertEqual(adapter.return_value.publish.call_args.kwargs['price'],'35.50')
        listing=db.row('SELECT * FROM listings WHERE id=?',(draft['id'],))
        self.assertNotEqual(listing['status'],'published')

    def test_thumbnails_not_used_as_listing_photos(self):
        hid=self._insert()
        hunter.prepare(hid,['Jófogás'],use_ai=False)
        row=db.row('SELECT * FROM hunter_results WHERE id=?',(hid,))
        self.assertFalse(db.rows('SELECT * FROM photos WHERE product_id=?',(row['product_id'],)))

if __name__=='__main__':unittest.main()
