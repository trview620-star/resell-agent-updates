"""Vinted helper packages only confirmed personal used-item drafts."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile
from io import BytesIO
import json
import unittest

from PIL import Image
from agent import db, vinted_upload


class VintedUploadBundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        root=Path(self.tmp.name)
        self.patches=[patch.object(db,'ROOT',root),patch.object(db,'DATA',root/'data'),
                      patch.object(db,'DB_PATH',root/'data'/'db.sqlite3'),
                      patch.object(db,'PHOTOS',root/'data'/'photos')]
        for item in self.patches:item.start()
        db.initialize()
        with db.session() as conn:
            self.product_id=conn.execute(
                'INSERT INTO products(title,created_at,updated_at) VALUES(?,?,?)',
                ('Használt társasjáték',db.utcnow(),db.utcnow())).lastrowid
        self.listing_id=db.insert_listing(self.product_id,'Vinted','Társasjáték','Saját, használt darab.',5000)

    def tearDown(self):
        for item in reversed(self.patches):item.stop()
        self.tmp.cleanup()

    def add_photo(self):
        img=Image.new('RGB',(3,3),'red'); buff=BytesIO(); img.save(buff,format='PNG')
        content=buff.getvalue(); digest=sha256(content).hexdigest()
        db.PHOTOS.mkdir(parents=True,exist_ok=True)
        filename=f'p{self.product_id}_{digest[:16]}.png'
        (db.PHOTOS/filename).write_bytes(content)
        db.add_photo(self.product_id,filename,digest,'sajat_foto.png')

    def test_confirmation_and_original_photo_required(self):
        with self.assertRaises(ValueError):
            vinted_upload.build_upload_bundle(self.listing_id)
        with self.assertRaises(ValueError):
            vinted_upload.build_upload_bundle(self.listing_id,confirmed_personal_used=True)
        self.add_photo()
        data,manifest=vinted_upload.build_upload_bundle(
            self.listing_id,confirmed_personal_used=True)
        self.assertEqual(manifest['price_huf'],5000)
        with ZipFile(BytesIO(data)) as archive:
            self.assertIn('kepek/01.png',archive.namelist())
            self.assertEqual(json.loads(archive.read('hirdetes.json'))['title'],'Társasjáték')
            self.assertEqual(sha256(archive.read('kepek/01.png')).hexdigest(),manifest['photos'][0]['sha256'])

    def test_published_listing_cannot_be_prepared_again(self):
        self.add_photo()
        db.update_listing(self.listing_id,status='published',url='https://www.vinted.hu/items/123')
        with self.assertRaises(ValueError):
            vinted_upload.build_upload_bundle(self.listing_id,confirmed_personal_used=True)


if __name__=='__main__':unittest.main()
