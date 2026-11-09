import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from PIL import Image
from agent import christmas_trial as x,db,extra_db,free_photo_import

def png():
    b=io.BytesIO()
    Image.new('RGB',(128,96),'green').save(b,'PNG')
    return b.getvalue()

class ChristmasPilotTests(unittest.TestCase):
    def test_one_specific_product(self):
        self.assertEqual(x.PRODUCT['model'],'8090234')
        self.assertIn('Christmas',x.photo_prompt().replace('Christmas-decor','Christmas'))
        self.assertIn('ONE realistic',x.photo_prompt())
        self.assertIn('illustrative',x.hungarian_draft())
    def test_huf_price_only_explicit_currency(self):
        self.assertEqual(x.huf_price('2.890 Ft'),2890)
        self.assertEqual(x.huf_price('2 890,00 HUF'),2890)
        self.assertEqual(x.huf_price(2890,'HUF'),2890)
        self.assertIsNone(x.huf_price('€7.50'))
        self.assertIsNone(x.huf_price(2890,'EUR'))
    def test_sku_exact_and_lowest_price(self):
        payload={'shopping':[
            {'title':'MagicHome natúr adventi koszorú 8090234, piros 25 cm',
             'price':'3.390 Ft','source':'A','link':'https://example.com/wreath-a'},
            {'title':'MagicHome natúr adventi koszorú 8090234, piros 25 cm',
             'price':'2.890 Ft','source':'B','link':'https://example.com/wreath-b'},
            {'title':'MagicHome adventi koszorú 8090235','price':'999 Ft','source':'C','link':'https://example.com/wrong'},
            {'title':'MagicHome koszorú 8090234','price':'100 Ft','link':'http://127.0.0.1/private'}]}
        found=x.select_one_offer(payload)
        self.assertEqual(found['price_huf'],2890)
        self.assertEqual(found['merchant'],'B')
        self.assertIsNone(found['shipping_huf'])
    def test_serper_one_call_and_never_invents_stock(self):
        res=Mock()
        res.json.return_value={'shopping':[{
            'title':'MagicHome adventi koszorú piros 8090234',
            'price':'2.890 Ft','link':'https://example.org/ok','source':'Supplier'}]}
        with patch.object(x.shopping,'reserve_call') as reserve,patch.object(x.requests,'post',return_value=res) as send:
            res.status_code=200
            response,msg=x.find_one_offer('FAKE-SECRET-KEY')
        reserve.assert_called_once()
        send.assert_called_once()
        self.assertIn('google.serper.dev/shopping',send.call_args.args[0])
        self.assertEqual(response['price_huf'],2890)
        self.assertEqual(response['source_status'].startswith('Google Shopping'),True)
        self.assertNotIn('FAKE-SECRET-KEY',str(response))
    def test_no_key_uses_dated_example_not_live(self):
        with patch.object(x.requests,'post') as send:
            found,msg=x.find_one_offer('')
        send.assert_not_called()
        self.assertIn('Historical',found['source_status'])
        self.assertEqual(x.purchase_cost_known(found),5880)
    def test_one_cloudflare_request_uses_multipart_text_only(self):
        response=Mock(status_code=200,ok=True,content=png(),headers={'Content-Type':'image/png'})
        with patch.object(x.requests,'post',return_value=response) as send:
            out=x.generate_one_photo('a'*32,'FAKE-CLOUDFLARE-TOKEN')
        send.assert_called_once()
        self.assertEqual(send.call_args.kwargs['files']['prompt'][0],None)
        self.assertEqual(send.call_args.kwargs['files']['width'],(None,'1024'))
        self.assertNotIn('input_image_0',send.call_args.kwargs['files'])
        self.assertEqual(out,png())
    def test_wrong_credentials_no_cloud_call(self):
        with patch.object(x.requests,'post') as send:
            with self.assertRaises(ValueError):
                x.generate_one_photo('wrong','BAD')
        send.assert_not_called()
    def test_candidate_saves_illustration_separate_from_originals(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            patches=[
                patch.object(db,'ROOT',root),
                patch.object(db,'DATA',root/'data'),
                patch.object(db,'DB_PATH',root/'data'/'test.sqlite3'),
                patch.object(db,'PHOTOS',root/'data'/'photos')]
            for p in patches:p.start()
            try:
                extra_db.initialize()
                offer=x.reference_offer()
                id=db.insert_product({
                    'title':x.PRODUCT['name'],'brand':'MagicHome','model':'8090234',
                    'category':'Karácsonyi dekoráció','condition_text':'Unknown',
                    'description':x.hungarian_draft(),'supplier':offer['merchant'],
                    'supplier_url':offer['url'],'supplier_price':offer['price_huf'],
                    'inbound_shipping':offer['shipping_huf'],'outbound_shipping':0,
                    'packaging':0,'marketplace_fees':0,'risk_buffer':0,'target_price':0,
                    'stock_status':'unknown','stock_verified_at':None,'eta_days':None,
                    'fulfillment':db.FULFILLMENT[0],'status':'candidate','notes':'Pilot'})
                paths=free_photo_import.save_approved([{'bytes':png(),'approved':True}],db.DATA,id)
                self.assertEqual(len(paths),1)
                self.assertTrue(paths[0].is_file())
                self.assertFalse(db.rows('SELECT * FROM photos WHERE product_id=?',(id,)))
                self.assertEqual(db.row('SELECT * FROM products WHERE id=?',(id,))['target_price'],0)
            finally:
                for p in patches[::-1]:p.stop()

if __name__=='__main__':unittest.main()
