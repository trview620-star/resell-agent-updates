import base64
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from PIL import Image
from agent import cloudflare_photos as c

def make_image(color='blue'):
    b=io.BytesIO()
    Image.new('RGB',(740,530),color).save(b,'PNG')
    return b.getvalue()

class CloudflarePhotosTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.path=Path(self.folder.name)/'photo.png'
        self.path.write_bytes(make_image())
    def tearDown(self):
        self.folder.cleanup()

    def test_reference_downscaled_to_api_limit(self):
        data=c.reference_png(self.path)
        with Image.open(io.BytesIO(data)) as pic:
            self.assertLess(pic.width,512)
            self.assertLess(pic.height,512)
        self.assertEqual(self.path.read_bytes(),make_image())

    def test_four_unique_prompts_never_collages(self):
        self.assertEqual(len(c.ANGLES),4)
        for angle,_,_ in c.ANGLES:
            text=c.prompt_for(angle,'LEGO 42154','Use less studio lighting')
            self.assertIn('never a collage',text)
            self.assertIn('Image 0',text)
            self.assertIn('Use less studio lighting',text)

    def test_missing_token_or_id_blocks_requests(self):
        with patch.object(c.requests,'post') as send:
            for account,token in [('bad','secret-secret'),('0'*32,'')]:
                with self.assertRaises(ValueError):
                    c.generate(self.path,'straight_front',account,token,list(c.MODELS)[0])
            send.assert_not_called()

    def test_4b_and_9b_multipart_request(self):
        for label,path in c.MODELS.items():
            response=Mock(ok=True,status_code=200,content=b'{"success":true}',headers={'Content-Type':'application/json'})
            response.json.return_value={
              'success':True,'result':{'image':base64.b64encode(make_image()).decode()}}
            with patch.object(c.requests,'post',return_value=response) as send:
                result=c.generate(self.path,'straight_front','a'*32,'FAKE-PRIVATE-KEY',label,'LEGO')
            with Image.open(io.BytesIO(result)) as img:
                self.assertEqual(img.size,(740,530))
            url=send.call_args.args[0]
            self.assertTrue(url.endswith(path))
            self.assertNotIn('FAKE-PRIVATE-KEY',url)
            self.assertIn('input_image_0',send.call_args.kwargs['files'])
            self.assertEqual(send.call_args.kwargs['data']['width'],'1024')

    def test_auth_errors_keep_tokens_private(self):
        response=Mock(ok=False,status_code=403)
        with patch.object(c.requests,'post',return_value=response):
            with self.assertRaises(ValueError) as exc:
                c.generate(self.path,'straight_front','b'*32,'FAKE-PRIVATE-KEY',list(c.MODELS)[0])
        self.assertNotIn('FAKE-PRIVATE-KEY',str(exc.exception))

    def test_rate_limit_error(self):
        response=Mock(ok=False,status_code=429)
        with patch.object(c.requests,'post',return_value=response):
            with self.assertRaises(ValueError) as exc:
                c.generate(self.path,'straight_front','a'*32,'another-fake-private-key',list(c.MODELS)[0])
        self.assertIn('allowance',str(exc.exception))

    def test_binary_image_response(self):
        response=Mock(ok=True,status_code=200,content=make_image(),headers={'Content-Type':'image/png'})
        self.assertEqual(c._decode_response(response),make_image())

    def test_bad_image_response(self):
        response=Mock(ok=True,status_code=200,content=b'{}',headers={'Content-Type':'application/json'})
        response.json.return_value={'success':True,'result':{}}
        with self.assertRaises(ValueError):
            c._decode_response(response)

if __name__=='__main__': unittest.main()
