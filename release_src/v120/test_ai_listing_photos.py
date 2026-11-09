import base64
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from PIL import Image
from agent import ai_listing_photos as a
from agent.ui_ai_listing_photos import _approved_zip
from zipfile import ZipFile

def png():
    out=io.BytesIO()
    Image.new('RGB',(128,96),'blue').save(out,'PNG')
    return out.getvalue()

class AIAnglePhotoTests(unittest.TestCase):
    def setUp(self):
        self.d=tempfile.TemporaryDirectory()
        self.path=Path(self.d.name)/'reference.png'
        self.path.write_bytes(png())
    def tearDown(self):
        self.d.cleanup()
    def test_four_separate_unique_angles_and_no_collages(self):
        self.assertEqual(len(a.ANGLES),4)
        self.assertEqual(len(set(x[0] for x in a.ANGLES)),4)
        for key,_,_ in a.ANGLES:
            prompt=a.make_prompt(key,'LEGO Technic 42154','A simple kitchen table')
            self.assertIn('never a collage',prompt)
            self.assertIn('reference',prompt)
            self.assertIn('A simple kitchen table',prompt)
    def test_missing_key_blocks_network(self):
        with patch.object(a.requests,'post') as post:
            with self.assertRaises(ValueError):
                a.generate_view(self.path,'side_profile','','Test')
            post.assert_not_called()
    def test_request_and_result(self):
        res=Mock(ok=True,status_code=200)
        res.json.return_value={'data':[{'b64_json':base64.b64encode(png()).decode()}]}
        with patch.object(a.requests,'post',return_value=res) as post:
            image=a.generate_view(self.path,'straight_front','test-user-key','Car')
        self.assertEqual(image,png())
        args,kwargs=post.call_args
        self.assertEqual(args[0],'https://api.openai.com/v1/images/edits')
        self.assertEqual(kwargs['data']['model'],'gpt-image-1.5')
        self.assertIn('image[]',kwargs['files'])
        self.assertEqual(kwargs['data']['size'],'1536x1024')
    def test_error_401_does_not_expose_key(self):
        res=Mock(ok=False,status_code=401)
        res.json.return_value={'error':{'message':'bad token keysecret'}}
        with patch.object(a.requests,'post',return_value=res):
            with self.assertRaises(ValueError) as ctx:
                a.generate_view(self.path,'straight_front','keysecret','Car')
        self.assertNotIn('keysecret',str(ctx.exception))
    def test_invalid_base64_fails(self):
        with self.assertRaises(ValueError):
            a.decode_result({'data':[{'b64_json':'abc!'}]})
    def test_only_approved_exported_as_individual_images(self):
        batch={'images':{
            'straight_front':{'bytes':png(),'approved':True},
            'side_profile':{'bytes':png(),'approved':False}}}
        output=_approved_zip(batch,42)
        with ZipFile(io.BytesIO(output)) as zipfile:
            names=zipfile.namelist()
            self.assertEqual(len([n for n in names if n.endswith('.png')]),1)
            self.assertIn('AI_ILLUSTRATIVE_product_42_straight_front.png',names)
            self.assertFalse(any('side_profile' in n for n in names))
            self.assertIn('README.txt',names)
    def test_reference_not_modified(self):
        before=self.path.read_bytes()
        with patch.object(a.requests,'post') as post:
            resp=Mock(ok=True,status_code=200)
            resp.json.return_value={'data':[{'b64_json':base64.b64encode(png()).decode()}]}
            post.return_value=resp
            a.generate_view(self.path,'side_profile','test','Car')
        self.assertEqual(before,self.path.read_bytes())

if __name__=='__main__':
    unittest.main()
