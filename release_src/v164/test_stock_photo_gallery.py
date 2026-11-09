import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from PIL import Image
from agent import db,hunter,auto_stock_photo as stock,stock_photo_gallery as gallery

def image_bytes():
    buf=io.BytesIO()
    Image.new('RGB',(240,160),'blue').save(buf,format='PNG')
    return buf.getvalue()

class FourImageGalleryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        home=Path(self.tmp.name)
        self.patches=[patch.object(db,'ROOT',home),
            patch.object(db,'DATA',home/'data'),
            patch.object(db,'DB_PATH',home/'data'/'db.sqlite3'),
            patch.object(db,'PHOTOS',home/'data'/'photos')]
        for p in self.patches:p.start()
        hunter.initialize()
        with db.session() as c:
            cur=c.execute("""INSERT INTO hunter_results(url,title,merchant,
                 price_huf,thumbnail,phrase,topic,link_type,found_at)
                 VALUES(?,?,?,?,?,?,?,?,?)""",
                 ('https://store.example/item','LEGO Ideas 21366 Úszkáló vidrák',
                  'Store',19990,'https://images.example/item.png',
                  'LEGO','Játékok','Direct',db.utcnow()))
            self.hid=int(cur.lastrowid)
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()
    def test_four_distinct_previews_once(self):
        png=image_bytes()
        result=Mock(status_code=200,ok=True,content=png,
                    headers={'Content-Type':'image/png'})
        with patch.object(stock,'download_catalog_image',return_value=png) as fetch, \
             patch.object(stock.requests,'post',return_value=result) as send:
            response=hunter.prepare(self.hid,['Vinted'],account='a'*32,
                  token='FAKE-CLOUD-API-TOKEN',use_ai=False,auto_photo=True)
        self.assertEqual(send.call_count,4)
        self.assertEqual(fetch.call_count,2)
        self.assertEqual(response['photo_status'],'pending')
        photos=gallery.slots(self.hid)
        self.assertEqual(len(photos),4)
        self.assertEqual([p['slot'] for p in photos],[1,2,3,4])
        self.assertTrue(all(p['status']=='pending' and p['bytes'] for p in photos))
        self.assertFalse(db.rows('SELECT * FROM photos WHERE product_id=?',(response['product_id'],)))
        with patch.object(stock.requests,'post') as send:
            hunter.prepare(self.hid,['Vinted'],account='a'*32,
                token='FAKE-CLOUD-API-TOKEN',use_ai=False,auto_photo=True)
            send.assert_not_called()
        for number in range(1,5):
            saved=gallery.approve(self.hid,number)
            self.assertEqual(len(saved),1)
            self.assertTrue(saved[0].exists())
        self.assertTrue(all(p['status']=='approved' for p in gallery.slots(self.hid)))
        with patch.object(stock.requests,'post') as send:
            gallery.generate_remaining(self.hid,'a'*32,'FAKE-CLOUD-API-TOKEN')
            send.assert_not_called()
    def test_no_source_no_fake_photos(self):
        with db.session() as c:
            c.execute('UPDATE hunter_results SET thumbnail="" WHERE id=?',(self.hid,))
        with patch.object(stock.requests,'post') as send:
            result=hunter.prepare(self.hid,['Vinted'],account='a'*32,
                    token='FAKE-CLOUD-API-TOKEN',use_ai=False)
            send.assert_not_called()
        self.assertEqual(result['photo_status'],'missing')
        self.assertEqual(len([p for p in gallery.slots(self.hid) if p['bytes']]),0)
    def test_validate_slot(self):
        with self.assertRaises(ValueError):
            gallery.approve(self.hid,5)

if __name__=='__main__':unittest.main()
