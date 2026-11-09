import unittest
from agent.ui_trending_catalog import search_topics,group_offers

class TrendingCatalogTests(unittest.TestCase):
    def test_current_season_includes_christmas_topics(self):
        topics=search_topics(11)
        self.assertGreaterEqual(len(topics),6)
        self.assertTrue(any('karácsony' in phrase.casefold() or 'adventi' in phrase.casefold()
                            for _,phrase in topics))

    def test_other_month_uses_evergreen_topics(self):
        self.assertFalse(any('adventi' in phrase.casefold() for _,phrase in search_topics(5)))

    def test_cards_deduplicate_same_model_across_approved_suppliers(self):
        offers=[
          {'title':'LEGO Botanicals 10329 Apró növények','merchant':'Alza.hu','url':'https://www.alza.hu/lego','price_huf':8990,'thumbnail':'https://img.example/1.jpg'},
          {'title':'LEGO 10329 Apró növények Botanicals','merchant':'MediaMarkt','url':'https://www.mediamarkt.hu/lego','price_huf':9490,'thumbnail':'https://img.example/2.jpg'},
          {'title':'LEGO Botanicals 10329 Apró növények','merchant':'Ismeretlen bolt','url':'https://example.com/item','price_huf':7000,'thumbnail':''},
        ]
        cards=group_offers(offers)
        self.assertEqual(len(cards),1)
        self.assertEqual(cards[0]['best']['price_huf'],8990)
        self.assertEqual(len(cards[0]['retailers']),2)
        self.assertTrue(cards[0]['thumbnail'])

if __name__=='__main__':unittest.main()
