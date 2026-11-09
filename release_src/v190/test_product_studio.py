import unittest
import io
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch,Mock
from agent.product_studio import suggested_price,MIN_PROFIT_HUF,IMAGE_SLOTS
from agent import db,product_studio,demand_workbench

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
             'manually_verified':True,'verified_offer':None,'images':[{'slot':1,'bytes':b'PNG'}]}
        with patch.object(product_studio,'selected',return_value=[row]):
            payload=product_studio.posting_zip()
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names=archive.namelist()
            self.assertIn('01_LEGO_42151/00_hirdetesszoveg.txt',names)
            self.assertIn('01_LEGO_42151/01_AI_ILLUSZTRACIO.png',names)
            text=archive.read(names[0]).decode()
            self.assertIn('16 900 Ft',text)
            self.assertIn('AI-képek illusztrációk',text)

class AutomaticDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();root=Path(self.tmp.name)
        self.patches=[patch.object(db,'ROOT',root),patch.object(db,'DATA',root/'data'),
                      patch.object(db,'DB_PATH',root/'data'/'db.sqlite3'),
                      patch.object(db,'PHOTOS',root/'data'/'photos')]
        for p in self.patches:p.start()
        demand_workbench.initialize()
        self.lead=demand_workbench.save_lead('LEGO 42151')

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()

    def test_one_action_runs_four_indexed_market_searches_without_manual_metrics(self):
        response=Mock();response.json.return_value={'organic':[{'link':'https://example.com/result','title':'Találat','snippet':'Kivonat'}]}
        response.raise_for_status.return_value=None
        with patch('agent.product_studio.shopping.reserve_call') as reserve, patch('agent.product_studio.requests.post',return_value=response) as request:
            report=product_studio.scan_market_diagnostics(self.lead['id'],'fake-api-key-for-test')
        self.assertEqual(report['searched'],4)
        self.assertEqual(report['found'],4)
        self.assertEqual(request.call_count,4)
        self.assertEqual(reserve.call_count,4)
        data=product_studio.market_diagnostics(self.lead['id'])
        self.assertEqual(len(data['results']['vinted']),1)
        self.assertIsNone(data['lead']['sold_units'])

if __name__=='__main__':unittest.main()
