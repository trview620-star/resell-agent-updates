"""Regression tests: image thumbnails in Top 50 product results."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from agent import db, hunter, shopping, market_intelligence as radar, radar_previews


class RadarPreviewsTests(unittest.TestCase):
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
        radar.initialize()

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def test_existing_shopping_image_is_in_ranked_top50(self):
        payload={'shopping_results':[
            {'title':'LEGO Botanicals 10328 Rózsacsokor',
             'source':'Bolt A','price':'17 290 Ft',
             'link':'https://shop.example.com/lego-10328',
             'imageUrl':'https://images.example.com/lego-10328.jpg'},
            {'title':'LEGO Botanicals 10329 Apró növények',
             'source':'Bolt B','price':'15 290 Ft',
             'link':'https://shop.example.com/lego-10329',
             'imageUrl':'https://images.example.com/lego-10329.jpg'},
        ]}
        with patch.object(shopping,'fetch_serper_results',return_value=payload) as fetch:
            report=radar.scan_keyword('dummy','LEGO Botanicals 10328 Rózsacsokor','LEGO')
        fetch.assert_called_once()
        self.assertEqual(report['found'],1)
        row=next(x for x in radar.shortlisted()
                 if x['phrase']=='LEGO Botanicals 10328 Rózsacsokor')
        self.assertEqual(row['thumbnail'],'https://images.example.com/lego-10328.jpg')
        self.assertEqual(row['offers'],1)
        self.assertEqual(len(radar.shortlisted()),50)

    def test_alternate_image_field_from_provider(self):
        payload={'shopping_results':[
            {'title':'LEGO Technic 42171 Mercedes F1',
             'source':'Bolt B','price':'29 990 Ft',
             'link':'https://shop.example.com/technic-42171',
             'image':'https://assets.example.com/mercedes.jpg'},
        ]}
        with patch.object(shopping,'fetch_serper_results',return_value=payload):
            result=radar.scan_keyword('dummy','LEGO Technic 42171 Mercedes F1','LEGO')
        self.assertEqual(result['found'],1)
        offer=radar.offers_for('LEGO Technic 42171 Mercedes F1')[0]
        self.assertEqual(offer['thumbnail'],'https://assets.example.com/mercedes.jpg')

    def test_reject_unsafe_and_unrelated_thumbnails(self):
        invalid=[
            {'title':'LEGO Botanicals 10328 Rózsacsokor',
             'thumbnail':'http://127.0.0.1/private.jpg',
             'url':'https://shop.example.com/lego-10328'},
            {'title':'LEGO Botanicals 10329 Apró növények',
             'thumbnail':'https://images.example.com/other.jpg',
             'url':'https://shop.example.com/lego-10329'},
            {'title':'LEGO Botanicals 10328 Rózsacsokor tok',
             'thumbnail':'https://images.example.com/accessory.jpg',
             'url':'https://shop.example.com/accessory'}]
        result=radar_previews.preview_for('LEGO Botanicals 10328 Rózsacsokor',invalid)
        self.assertEqual(result,'')
        self.assertEqual(radar_previews.normalize_thumbnail('javascript:alert(1)'),'')
        self.assertEqual(radar_previews.normalize_thumbnail('data:text/html,hi'),'')

    def test_offer_images_deduplicated(self):
        offers=[
            {'title':'X','merchant':'A','thumbnail':'https://images.example.com/a.jpg'},
            {'title':'X','merchant':'B','thumbnail':'https://images.example.com/a.jpg'},
            {'title':'X','merchant':'C','thumbnail':'https://images.example.com/b.jpg'}]
        result=radar_previews.offer_images(offers)
        self.assertEqual(len(result),2)
        self.assertEqual(result[0]['merchant'],'A')

    def test_unknown_candidates_remain_without_fake_images(self):
        untouched=radar.shortlisted()
        self.assertTrue(all(x['thumbnail']=='' for x in untouched))
        self.assertEqual(len(untouched),50)


if __name__=='__main__':
    unittest.main()
