import io
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from PIL import Image
from agent import free_photo_import as m

def png(color='blue',size=(64,48)):
    out=io.BytesIO()
    Image.new('RGB',size,color).save(out,'PNG')
    return out.getvalue()

class FreePhotoImportTests(unittest.TestCase):
    def test_individual_files_deduplicated(self):
        data=m.unpack_uploads([('front.png',png('blue')),('duplicate.png',png('blue')),('rear.png',png('red'))])
        self.assertEqual(len(data),2)
        self.assertEqual((data[0]['width'],data[0]['height']),(64,48))
        self.assertFalse(any(x['approved'] for x in data))

    def test_zip_without_extraction(self):
        stream=io.BytesIO()
        with ZipFile(stream,'w') as z:
            z.writestr('../../front.png',png())
            z.writestr('notes.txt','not an image')
        data=m.unpack_uploads([('my_photos.zip',stream.getvalue())])
        self.assertEqual(len(data),1)
        self.assertEqual(data[0]['name'],'front.png')

    def test_corrupt_image(self):
        with self.assertRaises(ValueError):
            m.unpack_uploads([('bad.png',b'not an image')])

    def test_large_dimensions_rejected(self):
        with self.assertRaises(ValueError):
            m.unpack_uploads([('bad.png',png(size=(6500,6500)))])

    def test_empty_archive(self):
        stream=io.BytesIO()
        with ZipFile(stream,'w') as z:z.writestr('text.txt','hello')
        with self.assertRaises(ValueError):
            m.unpack_uploads([('photos.zip',stream.getvalue())])

    def test_approved_only_save_and_export(self):
        items=m.unpack_uploads([('front.png',png('blue')),('rear.png',png('red'))])
        items[0]['approved']=True
        with tempfile.TemporaryDirectory() as temp:
            paths=m.save_approved(items,Path(temp),11)
            self.assertEqual(len(paths),1)
            self.assertEqual(paths[0].parent,Path(temp)/'ai_previews'/'11')
            self.assertEqual(paths[0].read_bytes(),items[0]['bytes'])
            self.assertFalse(any('rear' in p.name for p in paths))
        export=m.approved_zip(items,11)
        with ZipFile(io.BytesIO(export)) as z:
            self.assertEqual(len([x for x in z.namelist() if x.endswith('.png')]),1)
            self.assertIn('README_AI_ILLUSTRATIVE.txt',z.namelist())

    def test_no_approval_no_save(self):
        items=m.unpack_uploads([('front.png',png())])
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                m.save_approved(items,Path(temp),1)
            self.assertFalse((Path(temp)/'ai_previews').exists())

if __name__=='__main__':
    unittest.main()
