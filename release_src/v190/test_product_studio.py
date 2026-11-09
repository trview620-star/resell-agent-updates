import unittest
import io
import zipfile
from unittest.mock import patch
from agent.product_studio import suggested_price,MIN_PROFIT_HUF,IMAGE_SLOTS
from agent import product_studio

class ProductStudioTests(unittest.TestCase):
    def test_under_market_cost_uses_cost_plus_4900(self):
        self.assertEqual(suggested_price(10000,12000),16900)

    def test_market_price_above_floor_is_retained(self):
        self.assertEqual(suggested_price(25000,12000),25000)

    def test_unknown_supplier_cost_has_no_price(self):
        self.assertIsNone(suggested_price(25000,None))

    def test_four_ordered_independent_image_slots(self):
        self.assertEqual(len(IMAGE_SLOTS),4)
        self.assertEqual(MIN_PROFIT_HUF,4900)
        self.assertEqual(len({x[0] for x in IMAGE_SLOTS}),4)

    def test_posting_pack_keeps_text_and_ai_disclosure_in_numbered_folder(self):
        row={'title':'LEGO 42151','description':'Rövid magyar szöveg',
             'target_price':16900,'sold_units':10,'period_days':30,
             'verified_offer':None,'images':[{'slot':1,'bytes':b'PNG'}]}
        with patch.object(product_studio,'selected',return_value=[row]):
            payload=product_studio.posting_zip()
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names=archive.namelist()
            self.assertIn('01_LEGO_42151/00_hirdetesszoveg.txt',names)
            self.assertIn('01_LEGO_42151/01_AI_ILLUSZTRACIO.png',names)
            text=archive.read(names[0]).decode()
            self.assertIn('16 900 Ft',text)
            self.assertIn('AI-képek illusztrációk',text)

if __name__=='__main__':unittest.main()
