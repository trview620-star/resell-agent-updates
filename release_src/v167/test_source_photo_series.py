"""Regression tests for strict source-preserving listing photo series."""
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image,ImageDraw
from agent import db,hunter,source_photo_series as studio


def pattern(label='BRAND 123',color=(130,80,170)):
    im=Image.new('RGB',(1100,820),'white')
    dr=ImageDraw.Draw(im)
    for x in range(0,1100,25):
        dr.rectangle([x,0,x+10,820],fill=((x*3)%255,(x*7)%255,(x*11)%255))
    dr.rectangle([200,90,910,705],fill=color)
    dr.text((240,140),label,fill=(3,4,5),stroke_width=1)
    dr.ellipse([650,300,820,490],fill=(12,220,90))
    buf=io.BytesIO()
    im.save(buf,format='PNG')
    return buf.getvalue()


class SourcePhotoSeriesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        root=Path(self.temp.name)
        self.patches=[
            patch.object(db,'ROOT',root),
            patch.object(db,'DATA',root/'data'),
            patch.object(db,'DB_PATH',root/'data'/'db.sqlite3'),
            patch.object(db,'PHOTOS',root/'data'/'photos')]
        for p in self.patches:p.start()
        hunter.initialize()
        self.pid=db.insert_product({
            'title':'HyperX Cloud III gamer fejhallgató',
            'brand':'HyperX','model':'Cloud III','category':'Gaming',
            'condition_text':'Unknown / verify',
            'description':'','supplier':'Shop','supplier_url':'https://example.org/headset',
            'supplier_price':14000,'inbound_shipping':0,'outbound_shipping':0,
            'packaging':0,'marketplace_fees':0,'risk_buffer':0,'target_price':0,
            'stock_status':'unknown','stock_verified_at':None,'eta_days':0,
            'fulfillment':db.FULFILLMENT[0],'status':'candidate','notes':''})
        with db.session() as con:
            self.hid=con.execute("""
                INSERT INTO hunter_results(url,title,merchant,price_huf,
                  thumbnail,phrase,topic,link_type,found_at,product_id,status)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,('https://example.org/headset','HyperX Cloud III gamer fejhallgató',
                     'Shop',14000,'https://images.example.org/headset.png',
                     'HyperX Cloud III','Gaming','Direct-domain',db.utcnow(),
                     self.pid,'selected')).lastrowid

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def _upload(self,name='full_image.png',data=None):
        from agent.photos import save_photo
        return save_photo(self.pid,name,data if data is not None else pattern())

    def test_four_distinct_crops_keep_all_visible_logo_pixels(self):
        self._upload()
        with patch.object(studio.catalog,'download_catalog_image') as fetch:
            made=studio.create(self.pid,hunter_id=self.hid)
            fetch.assert_not_called()
        self.assertEqual(made['created'],[1,2,3,4])
        previews=studio.read(self.pid)
        self.assertEqual(len(previews),4)
        self.assertTrue(all(p['status']=='pending' for p in previews))
        self.assertEqual(len({tuple(p['crop_box']) for p in previews}),4)
        original=Image.open(io.BytesIO(pattern())).convert('RGB')
        for slot in previews:
            out=Image.open(io.BytesIO(slot['bytes'])).convert('RGB')
            reference=original.crop(tuple(slot['crop_box']))
            self.assertEqual(out.size,reference.size)
            self.assertEqual(list(out.getdata()),list(reference.getdata()))
            self.assertEqual(slot['source_type'],'original')
            self.assertNotIn('AI',slot['note'])
        self.assertTrue(studio.approve(self.pid,1))
        self.assertEqual(studio.read(self.pid)[0]['status'],'approved')

    def test_second_angle_uses_real_second_photo_not_hallucinated(self):
        self._upload('main.png',pattern())
        self._upload('side.png',pattern('SIDE VIEW',(5,100,50)))
        out=studio.create(self.pid)['gallery']
        third=out[2]
        self.assertEqual(third['role'],'Másik eredeti fotó')
        self.assertEqual(third['crop_box'],[0,0,1100,820])
        self.assertEqual(
            Image.open(io.BytesIO(third['bytes'])).getpixel((600,300)),
            Image.open(io.BytesIO(pattern('SIDE VIEW',(5,100,50)))).getpixel((600,300)))

    def test_packaging_requires_actual_source_picture(self):
        self._upload('photo.png')
        no_box=studio.create(self.pid)['gallery'][3]
        self.assertIn('doboz nincs igazolva',no_box['role'])
        # Separate product with real uploaded packaging image.
        from agent.photos import save_photo
        save_photo(self.pid,'real_doboz.png',pattern('MODEL LABEL / BOX',(250,30,30)))
        rebuilt=studio.create(self.pid,only_slots=[4],replace_existing=True)['gallery'][3]
        self.assertEqual(rebuilt['role'],'Valódi dobozfotó')
        self.assertEqual(rebuilt['crop_box'],[0,0,1100,820])

    def test_catalogue_only_stays_unapproved_not_seller_photo(self):
        data=pattern()
        with patch.object(studio.catalog,'download_catalog_image',return_value=data) as download:
            result=studio.create(self.pid,hunter_id=self.hid)
        self.assertEqual(download.call_count,1)
        self.assertEqual(len(result['created']),4)
        self.assertTrue(all(x['source_type']=='catalogue' for x in result['gallery']))
        with self.assertRaisesRegex(ValueError,'Beszállítói képet'):
            studio.approve(self.pid,1)
        with patch.object(studio.catalog,'download_catalog_image') as download:
            repeated=studio.create(self.pid,hunter_id=self.hid)
            download.assert_not_called()
        self.assertEqual(repeated['created'],[])

    def test_refuse_approve_missing_and_prevent_overwrite(self):
        self._upload()
        studio.create(self.pid)
        studio.approve(self.pid,2)
        with self.assertRaisesRegex(ValueError,'felülírni'):
            studio.create(self.pid,only_slots=[2],replace_existing=True,
                          focuses={2:(.1,.1)})
        old=studio.read(self.pid)[1]['bytes']
        self.assertEqual(studio.read(self.pid)[1]['bytes'],old)
        result=studio.create(self.pid,only_slots=[4],replace_existing=True,
                             focuses={4:(.9,.9)})
        self.assertEqual(result['created'],[4])

    def test_lack_of_photo_requires_real_source(self):
        with db.session() as conn:
            conn.execute('UPDATE hunter_results SET thumbnail=? WHERE id=?',('',self.hid))
        with self.assertRaisesRegex(ValueError,'termékfotó'):
            studio.create(self.pid,hunter_id=self.hid)

    def test_source_files_remain_unchanged(self):
        data=pattern()
        self._upload(data=data)
        path=db.rows('SELECT filename FROM photos WHERE product_id=?',(self.pid,))[0]
        original_path=db.PHOTOS/path['filename']
        studio.create(self.pid)
        self.assertEqual(original_path.read_bytes(),data)


if __name__=='__main__':
    unittest.main()
