import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from agent import db,hunter,shopping,market_intelligence as radar,product_copy,supplier_links

class RadarAndCopyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        root=Path(self.tmp.name)
        self.patches=[patch.object(db,'ROOT',root),
                      patch.object(db,'DATA',root/'data'),
                      patch.object(db,'DB_PATH',root/'data'/'test.sqlite3'),
                      patch.object(db,'PHOTOS',root/'data'/'photos')]
        for p in self.patches:p.start()
        hunter.initialize()
        radar.initialize()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()
    def test_exactly_fifty_unique_evidence_labeled_candidates(self):
        items=radar.shortlisted()
        self.assertEqual(len(items),50)
        self.assertEqual(len({item['phrase'] for item in items}),50)
        self.assertTrue(all(item['source_url'].startswith('https://') for item in items))
        self.assertTrue(all(item['offers']==0 for item in items))
        self.assertTrue(all('Kategóriaadat' in item['confidence'] for item in items))
    def test_vendor_link_prefers_real_domain_not_google_shopping(self):
        item={'title':'LEGO Ideas 21366 Úszkáló vidrák','merchant':'Alza.hu',
              'url':'https://www.google.com/search?ibp=oshop&prds=localAnnotatedOfferId:1'}
        payload={'shopping_results':[{'title':item['title'],'source':item['merchant'],
               'link':item['url'],
               'productUrl':'https://www.alza.hu/lego-ideas-21366-d123.htm'}]}
        url,kind=supplier_links.offer_url(item,payload)
        self.assertEqual(url,'https://www.alza.hu/lego-ideas-21366-d123.htm')
        self.assertIn('Közvetlen',kind)
    def test_google_offer_falls_back_to_stable_search_page(self):
        old='https://www.google.com/search?ibp=oshop&prds=localAnnotatedOfferId:1'
        url,is_direct=supplier_links.navigable(old,'LEGO Ideas 21366','Alza.hu')
        self.assertFalse(is_direct)
        self.assertTrue(url.startswith('https://www.google.com/search?q='))
        self.assertNotIn('localAnnotatedOfferId',url)
        self.assertIn('Alza.hu',url)
    def test_user_keyword_is_one_api_call_independent_of_top50(self):
        payload={'shopping_results':[
            {'title':'LEGO Ideas 21366 Úszkáló vidrák','source':'Alza.hu','price':'21 990 Ft',
             'link':'https://www.google.com/search?ibp=oshop&prds=1',
             'productUrl':'https://www.alza.hu/lego-ideas-21366-d123.htm'}]}
        with patch.object(shopping,'fetch_serper_results',return_value=payload) as fetch:
            result=radar.scan_keyword('test-key','LEGO Ideas 21366','Saját keresés')
        self.assertEqual(fetch.call_count,1)
        self.assertEqual(result['found'],1)
        row=db.row('SELECT * FROM hunter_results LIMIT 1')
        self.assertEqual(row['url'],'https://www.alza.hu/lego-ideas-21366-d123.htm')
        self.assertEqual(row['topic'],'Saját keresés')
    def test_lego_text_is_human_and_preserves_claim_guards(self):
        text=product_copy.fallback('LEGO Ideas 21366 Úszkáló vidrák')
        self.assertIn('Nagyon aranyos',text)
        self.assertIn('összerakva',text)
        self.assertTrue(text.endswith(product_copy.FOOTER))
        self.assertNotIn('A részleteket üzenetben egyeztetjük',text)
        self.assertNotIn('bontatlan',text)
        self.assertNotIn('hibátlan',text)
    def test_unverified_ai_claim_is_replaced_not_published(self):
        product={'title':'LEGO Ideas 21366','condition_text':'Unknown / verify'}
        draft='Eladó LEGO Ideas 21366, teljesen bontatlan, új gyári csomagolásban.'
        result=product_copy.clean_ai(draft,product)
        self.assertNotIn('bontatlan',result)
        self.assertIn('LEGO Ideas 21366',result)
    def test_candidate_ranking_is_not_fake_sales(self):
        item=radar.shortlisted()[0]
        self.assertNotIn('sales',item)
        self.assertNotIn('profit_huf',item)
        self.assertLess(item['score'],100)

if __name__=='__main__':unittest.main()
