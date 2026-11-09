"""Tests of listing thumbnails, trust labels, shot planning and source preservation."""
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from agent import db,hunter,listing_previews,photo_shot_plan,auto_stock_photo as stock


def png(color):
    buf=io.BytesIO()
    Image.new('RGB',(160,100),color).save(buf,format='PNG')
    return buf.getvalue()


class ListingImagePreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        root=Path(self.temp.name)
        self.patches=[
            patch.object(db,'ROOT',root),
            patch.object(db,'DATA',root/'data'),
            patch.object(db,'DB_PATH',root/'data'/'test.sqlite3'),
            patch.object(db,'PHOTOS',root/'data'/'photos')
        ]
        for p in self.patches:p.start()
        hunter.initialize()
        self.pid=db.insert_product({
            'title':'HyperX Cloud III gamer headset',
            'brand':'HyperX','model':'Cloud III','category':'Gaming',
            'condition_text':'Unknown / verify',
            'description':'','supplier':'Test store',
            'supplier_url':'https://example.org/cloud','supplier_price':12990,
            'inbound_shipping':0,'outbound_shipping':0,
            'packaging':0,'marketplace_fees':0,'risk_buffer':0,
            'target_price':0,'stock_status':'unknown','stock_verified_at':None,
            'eta_days':0,'fulfillment':db.FULFILLMENT[0],
            'status':'candidate','notes':''})
        with db.session() as con:
            cur=con.execute("""INSERT INTO hunter_results(
                url,title,merchant,price_huf,thumbnail,phrase,topic,
                link_type,found_at,product_id,status
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                ('https://example.org/cloud',
                 'HyperX Cloud III gamer headset','Test store',12990,
                 'https://example.org/cloud.jpg','HyperX Cloud III','Gaming',
                 'Direct-domain',db.utcnow(),self.pid,'selected'))
            self.hid=int(cur.lastrowid)

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def test_catalogue_label_when_no_saved_photo(self):
        photo=listing_previews.primary(self.pid,hunter_id=self.hid)
        self.assertEqual(photo['kind'],'catalogue')
        self.assertIn('nem saját fotó',photo['label'])
        self.assertIn('example.org',photo['image'])

    def test_originals_first_and_bytes_not_modified(self):
        from agent.photos import save_photo
        data=png('red')
        self.assertTrue(save_photo(self.pid,'my.png',data))
        photo=listing_previews.primary(self.pid,hunter_id=self.hid)
        self.assertEqual(photo['kind'],'original')
        self.assertEqual(Path(photo['image']).read_bytes(),data)
        self.assertEqual(listing_previews.sources(self.pid,hunter_id=self.hid)[0]['kind'],'original')

    def test_approved_illustration_precedes_pending(self):
        approved=db.DATA/'ai_previews'/str(self.pid)/'AI_ILLUSTRATIVE_abc123.png'
        approved.parent.mkdir(parents=True,exist_ok=True)
        approved.write_bytes(png('green'))
        pending=db.DATA/'ai_pending'/str(self.pid)/('AI_STOCK_'+'a'*32+'.png')
        pending.parent.mkdir(parents=True,exist_ok=True)
        pending.write_bytes(png('blue'))
        stock._update_status(self.hid,self.pid,
            'https://example.org/cloud.jpg','pending',filename=pending.name)
        items=listing_previews.sources(self.pid,hunter_id=self.hid)
        self.assertEqual([x['kind'] for x in items][:3],
                         ['approved','pending','catalogue'])
        self.assertIn('AI',items[0]['label'])
        self.assertIn('AI',items[1]['label'])

    def test_missing_file_is_skipped_safely(self):
        from agent.photos import save_photo
        save_photo(self.pid,'deleted.jpg',png('orange'))
        r=db.row('SELECT filename FROM photos WHERE product_id=?',(self.pid,))
        (db.PHOTOS/r['filename']).unlink()
        p=listing_previews.primary(self.pid,hunter_id=self.hid)
        self.assertEqual(p['kind'],'catalogue')

    def test_four_shots_have_distinct_roles(self):
        title='HyperX Cloud III gamer headset'
        plans=[photo_shot_plan.prompt_for(title,i) for i in range(1,5)]
        self.assertEqual(len(set(plans)),4)
        self.assertIn('WHOLE',plans[0])
        self.assertIn('ear cushion',plans[1])
        self.assertIn('different',plans[2])
        self.assertIn('no invented boxes',plans[3].lower())
        self.assertTrue(all('No kitchen' in p for p in plans))
        self.assertTrue(all('brand logo' in p for p in plans))
        self.assertEqual(photo_shot_plan.category(title),'gaming_headset')

    def test_scene_specific_categories(self):
        self.assertEqual(photo_shot_plan.category('LEGO 21366'),'lego')
        self.assertEqual(photo_shot_plan.category('Ninja Airfryer 180'),'kitchen')
        self.assertEqual(photo_shot_plan.category('Dobble társasjáték'),'boardgame')
        self.assertIn('No kitchen', photo_shot_plan.prompt_for('Gamer headset',1))

    def test_duplicate_warning(self):
        data=png('red')
        self.assertIn(2,photo_shot_plan.difference_warning([(1,data),(2,data)]))


if __name__=='__main__':
    unittest.main()
