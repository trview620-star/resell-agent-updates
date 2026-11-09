"""Fast manual Vinted listing preparation for personally owned used items.

Vinted's consumer terms prohibit unapproved automation. This module only
prepares local text and original seller photos; it never signs in, calls
private endpoints, or publishes a listing.
"""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from . import db


def build_upload_bundle(listing_id: int, *, confirmed_personal_used: bool=False):
    if not confirmed_personal_used:
        raise ValueError('Csak saját tulajdonú, használt termékhez készíthető Vinted-csomag.')
    row=db.row("""SELECT l.*,p.title AS product_name FROM listings l
                   JOIN products p ON p.id=l.product_id WHERE l.id=?
                   AND l.marketplace='Vinted'""",(int(listing_id),))
    if not row:
        raise ValueError('A Vinted-piszkozat nem található.')
    if row['status'] not in ('draft','ready'):
        raise ValueError('Csak helyi piszkozat készíthető elő.')
    title=str(row['title'] or '').strip()
    description=str(row['description'] or '').strip()
    price=int(row['price'] or 0)
    if not title or not description:
        raise ValueError('A címet és a leírást töltsd ki a piszkozatban.')
    if price<=0:
        raise ValueError('Adj meg pozitív, ellenőrzött hirdetési árat.')

    image_files=[]
    root=db.PHOTOS.resolve()
    for photo in db.rows(
        'SELECT filename,original_name,sha256 FROM photos WHERE product_id=? ORDER BY created_at,id',
        (row['product_id'],)):
        filename=str(photo['filename'])
        if Path(filename).name!=filename:
            continue
        path=(db.PHOTOS/filename).resolve()
        if path.parent!=root or not path.is_file() or path.suffix.lower() not in ('.jpg','.jpeg','.png','.webp'):
            continue
        content=path.read_bytes()
        digest=sha256(content).hexdigest()
        if not content or digest!=photo['sha256']:
            continue
        image_files.append((photo,content,path.suffix.lower(),digest))
    if not image_files:
        raise ValueError('Nincs eredeti, saját termékfotó. Beszállítói katalógus- és AI-kép nem használható.')

    manifest={
        'marketplace':'Vinted','listing_id':int(row['id']),
        'product_name':row['product_name'],'title':title,
        'description':description,'price_huf':price,
        'item_type':'personally owned used item (seller confirmed)',
        'photos':[]
    }
    output=BytesIO()
    with ZipFile(output,'w',ZIP_DEFLATED) as archive:
        for index,(photo,content,ext,digest) in enumerate(image_files,1):
            target=f'kepek/{index:02d}{ext}'
            archive.writestr(target,content)
            manifest['photos'].append({'file':target,
                'original_name':str(photo['original_name']), 'sha256':digest})
        archive.writestr('hirdetes.json',json.dumps(manifest,ensure_ascii=False,indent=2))
        archive.writestr('FELTOLTES.txt',
            'Vinted kézi feltöltés\n\n'
            'Másold át a címet és leírást az alkalmazásból, töltsd fel a kepek/ mappa eredeti képeit, '
            'válaszd ki a pontos kategóriát és állapotot, majd ellenőrzés után te tedd közzé.\n')
    return output.getvalue(),manifest
