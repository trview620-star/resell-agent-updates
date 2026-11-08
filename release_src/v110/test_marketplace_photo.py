import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image,ImageDraw
from agent import marketplace_photo as m

def sample():
    image=Image.new('RGB',(400,380),'white')
    draw=ImageDraw.Draw(image)
    draw.rounded_rectangle((65,45,350,320),radius=16,fill=(23,58,105))
    draw.rectangle((100,100,190,200),fill=(240,240,240))
    stream=io.BytesIO();image.save(stream,'PNG')
    return stream.getvalue()

def room():
    im=Image.new('RGB',(900,1200),'#aa9988')
    stream=io.BytesIO();im.save(stream,'JPEG')
    return stream.getvalue()

class PhotoModeTests(unittest.TestCase):
    def test_camera_finish_preserves_shape(self):
        original=sample()
        result=m.make_marketplace_photo(original)
        with Image.open(io.BytesIO(result)) as image:
            self.assertEqual(image.size,(400,380))
            self.assertEqual(image.format,'JPEG')
        self.assertEqual(original,sample())

    def test_room_mode_full_resolution(self):
        result=m.make_marketplace_photo(sample(),room_bytes=room())
        with Image.open(io.BytesIO(result)) as image:
            self.assertEqual(image.size,(1080,1350))
            self.assertEqual(image.format,'JPEG')

    def test_transparent_source(self):
        image=Image.new('RGBA',(400,380),(0,0,0,0))
        ImageDraw.Draw(image).rectangle((80,80,300,300),fill=(0,120,180,255))
        out=io.BytesIO();image.save(out,'PNG')
        result=m.make_marketplace_photo(out.getvalue(),room_bytes=room())
        self.assertGreater(len(result),3000)

    def test_nonwhite_background_rejected(self):
        im=Image.new('RGB',(400,380),'blue')
        out=io.BytesIO();im.save(out,'PNG')
        with self.assertRaisesRegex(ValueError,'white-background'):
            m.make_marketplace_photo(out.getvalue(),room_bytes=room())

    def test_bad_source_rejected(self):
        with self.assertRaises(ValueError):m.make_marketplace_photo(b'invalid')
        with self.assertRaises(ValueError):m.make_marketplace_photo(b'x'*(m.MAX_BYTES+1))

    def test_bad_placement_rejected(self):
        with self.assertRaises(ValueError):
            m.make_marketplace_photo(sample(),room_bytes=room(),x=2)

    def test_same_input_same_result(self):
        self.assertEqual(m.make_marketplace_photo(sample()),m.make_marketplace_photo(sample()))

    def test_saved_edit_does_not_replace_original(self):
        with tempfile.TemporaryDirectory() as dirname:
            photos=Path(dirname)
            original=photos/'test.png'
            original.write_bytes(sample())
            class FakeDB:
                PHOTOS=photos
                @staticmethod
                def row(*args):return {'id':1,'filename':'test.png'}
            with patch.object(m,'db',FakeDB):
                result=m.make_marketplace_photo(original.read_bytes())
                saved=m.save_marketplace_variant(1,result)
                self.assertTrue(saved.is_file())
                self.assertNotEqual(saved,original)
                self.assertEqual(original.read_bytes(),sample())
                self.assertEqual(m.saved_variants(1),[saved])
