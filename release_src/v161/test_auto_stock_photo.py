import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
from PIL import Image
from agent import db, hunter, auto_stock_photo as a

def small_image(color='red'):
    f=io.BytesIO()
    Image.new('RGB',(320,240),color).save(f,format='PNG')
    return f.getvalue()

class AutoStockPhotosTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.patches=[
            patch.object(db,'ROOT',self.root),
            patch.object(db,'DATA',self.root/'data'),
            patch.object(db,'DB_PATH',self.root/'data'/'test.sqlite3'),
            patch.object(db,'PHOTOS',self.root/'data'/'photos')]
        for item in self.patches:item.start()
        hunter.initialize()
        with db.session() as connection:
            cur=connection.execute(
                '''INSERT INTO hunter_results(url,title,merchant,price_huf,thumbnail,
                   phrase,topic,link_type,found_at) VALUES(?,?,?,?,?,?,?,?,?)''',
                ('https://shop.example.com/holiday-wreath','Piros karácsonyi koszorú',
                 'Shop',4990,'https://image.example.com/wreath.jpg',
                 'karácsonyi koszorú','Karácsony','Direct-domain',db.utcnow()))
            self.hid=cur.lastrowid

    def tearDown(self):
        for p in self.patches[::-1]:p.stop()
        self.tmp.cleanup()

    def test_http_and_private_addresses_are_blocked(self):
        for link in (
            'http://image.example.com/item.png',
            'https://127.0.0.1/secret.png',
            'https://localhost/private',
            'https://user:pass@image.example.com/photo.png',
            'https://image.example.com:8443/photo.png'
        ):
            self.assertFalse(a._public_https_url(link))

    def test_public_hostname_requires_global_address(self):
        with patch.object(a.socket,'getaddrinfo',return_value=[
            (None,None,None,None,('10.0.0.7',443))]):
            self.assertFalse(a._public_https_url('https://image.example.com/photo.png'))

    def test_image_downloading_and_preprocessing(self):
        content=small_image()
        response=Mock(status_code=200)
        response.headers={'Content-Type':'image/png','Content-Length':str(len(content))}
        response.iter_content.return_value=[content]
        response.__enter__=Mock(return_value=response)
        response.__exit__=Mock(return_value=False)
        with patch.object(a,'_public_https_url',return_value=True),patch.object(a.requests,'get',return_value=response) as get:
            result=a.download_catalog_image('https://image.example.com/wreath.jpg')
        self.assertEqual(get.call_args.kwargs['allow_redirects'],False)
        with Image.open(io.BytesIO(result)) as im:
            self.assertEqual(im.size,(320,240))

    def test_reject_redirects(self):
        response=Mock(status_code=302)
        response.headers={'Location':'http://localhost/'}
        response.__enter__=Mock(return_value=response)
        response.__exit__=Mock(return_value=False)
        with patch.object(a,'_public_https_url',return_value=True),patch.object(a.requests,'get',return_value=response):
            with self.assertRaises(ValueError):
                a.download_catalog_image('https://image.example.com/wreath.jpg')

    def test_select_generates_one_ai_preview_automatically(self):
        output=small_image()
        response=Mock(status_code=200,ok=True,content=output,
                      headers={'Content-Type':'image/png'})
        with patch.object(a,'download_catalog_image',return_value=small_image()) as download,patch.object(a.requests,'post',return_value=response) as post:
            prepared=hunter.prepare(self.hid,['Jófogás'],account='a'*32,
                       token='FAKE-CLOUDFLARE-TOKEN',use_ai=False,auto_photo=True)
        self.assertEqual(prepared['photo_status'],'pending')
        self.assertEqual(download.call_count,1)
        self.assertEqual(post.call_count,1)
        args=post.call_args.kwargs
        self.assertIn('input_image_0',args['files'])
        self.assertIn('wooden tabletop',args['files']['prompt'][1])
        entry=a.preview_record(self.hid)
        self.assertEqual(entry['status'],'pending')
        self.assertTrue(entry['bytes'])
        self.assertFalse(db.rows('SELECT * FROM photos WHERE product_id=?',(prepared['product_id'],)))
        self.assertFalse((db.DATA/'ai_previews'/str(prepared['product_id'])).exists())

        with patch.object(a.requests,'post') as send:
            second=hunter.prepare(self.hid,['Jófogás'],account='a'*32,
                                  token='FAKE-CLOUDFLARE-TOKEN',use_ai=False)
            send.assert_not_called()
        self.assertEqual(second['photo_status'],'pending')
        saved=a.approve(self.hid)
        self.assertEqual(len(saved),1)
        self.assertTrue(saved[0].is_file())
        self.assertEqual(a.preview_record(self.hid)['status'],'approved')
        with patch.object(a.requests,'post') as send:
            third=hunter.prepare(self.hid,['Jófogás'],account='a'*32,
                                 token='FAKE-CLOUDFLARE-TOKEN',use_ai=False)
            send.assert_not_called()
        self.assertEqual(third['photo_status'],'approved')

    def test_missing_image_never_generates_fake_product_photo(self):
        with db.session() as conn:
            conn.execute('UPDATE hunter_results SET thumbnail="" WHERE id=?',(self.hid,))
        with patch.object(a.requests,'post') as send:
            result=hunter.prepare(self.hid,['Jófogás'],account='a'*32,
                    token='FAKE-CLOUDFLARE-TOKEN',use_ai=False)
            send.assert_not_called()
        self.assertEqual(result['photo_status'],'missing')
        self.assertIsNone(a.preview_record(self.hid)['bytes'])

    def test_network_failure_leaves_drafts_without_secret_leak(self):
        with patch.object(a,'download_catalog_image',side_effect=ValueError('Kép letöltése nem sikerült.')):
            result=hunter.prepare(self.hid,['Jófogás'],account='a'*32,
                token='FAKE-CLOUDFLARE-TOKEN',use_ai=False)
        self.assertEqual(result['photo_status'],'failed')
        self.assertEqual(len(db.rows('SELECT * FROM listings')),1)
        self.assertNotIn('FAKE-CLOUDFLARE-TOKEN',
                         a.preview_record(self.hid)['last_error'])

if __name__=='__main__':unittest.main()
