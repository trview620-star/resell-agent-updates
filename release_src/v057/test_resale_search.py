import unittest
from unittest.mock import patch, Mock
from agent import resale_search as r


class ResaleSearchTests(unittest.TestCase):
    def test_explicit_huf(self):
        self.assertEqual(r.extract_single_huf_price('LEGO 42154 · 29 990 Ft'), 29990)
        self.assertIsNone(r.extract_single_huf_price('Price €40'))
        self.assertIsNone(r.extract_single_huf_price('15 000 Ft vagy 20 000 Ft'))

    def test_model_and_domain(self):
        data = {'organic': [
            {'title': 'LEGO Technic 42154 Ford GT', 'snippet': '29 990 Ft', 'link': 'https://www.jofogas.hu/pest/item.htm'},
            {'title': 'LEGO Technic 42155', 'snippet': '10 000 Ft', 'link': 'https://www.jofogas.hu/pest/other.htm'},
            {'title': 'LEGO 42154 stand', 'snippet': '10 000 Ft', 'link': 'https://www.jofogas.hu/pest/stand.htm'},
            {'title': 'LEGO Technic 42154 Ford GT', 'snippet': '13 000 Ft', 'link': 'https://example.com/a'},
        ]}
        found = r.normalize_organic(data, 'LEGO Technic 42154', 'Jófogás')
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['price_huf'], 29990)

    def test_api_counted_once(self):
        response = Mock()
        response.json.return_value = {'organic': [
            {'title': 'LEGO 42154', 'snippet': '29 990 Ft', 'link': 'https://www.vinted.hu/items/123'}
        ]}
        with patch.object(r.shopping, 'reserve_call') as reserve, patch.object(r.requests, 'post', return_value=response) as send:
            result = r.search_marketplace('LEGO 42154', 'Vinted', 'secret')
        self.assertEqual(len(result), 1)
        reserve.assert_called_once()
        self.assertIn('site:vinted.hu', send.call_args.kwargs['json']['q'])
        self.assertNotIn('secret', str(result))

    def test_bad_response(self):
        with self.assertRaises(ValueError):
            r.normalize_organic({}, 'LEGO 42154', 'Vinted')
