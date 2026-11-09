"""Four separately reviewable AI listing-image drafts per selected product.

Slot 1 uses the existing stock-photo pipeline; slots 2–4 reuse its safety
checks and provider. All generated pictures are illustrative, not proof of
the item's condition. Original thumbnails are never saved as seller photos.
"""
from __future__ import annotations

import io
from pathlib import Path
from uuid import uuid4
import re
import requests
from . import db, auto_stock_photo as stock, cloudflare_photos

COUNT=4
EXTRA_PROMPTS={
    2: 'Alternate image 2 of 4: same exact visible reference camera angle and same product, '
       'slightly closer framing to visible details. No new side or opened package.',
    3: 'Alternate image 3 of 4: same exact visible reference product and angle, '
       'casual bookshelf or desk background, soft natural daylight. Never invent contents.',
    4: 'Alternate image 4 of 4: same exact visible reference product and angle, '
       'a second uncluttered home tabletop arrangement with gentle side light. '
       'No fake factory seals, no new writing, no altered package.'
}


def initialize():
    stock.init_store()
    with db.session() as connection:
        connection.executescript("""
          CREATE TABLE IF NOT EXISTS hunter_stock_gallery(
             hunter_id INTEGER NOT NULL REFERENCES hunter_results(id) ON DELETE CASCADE,
             slot INTEGER NOT NULL CHECK(slot BETWEEN 2 AND 4),
             product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
             source_image_url TEXT NOT NULL DEFAULT '',
             preview_file TEXT NOT NULL DEFAULT '',
             status TEXT NOT NULL DEFAULT 'pending',
             last_error TEXT NOT NULL DEFAULT '',
             reviewed_at TEXT,
             created_at TEXT NOT NULL,
             PRIMARY KEY(hunter_id,slot)
          );
        """)


def slots(hunter_id):
    initialize()
    base=stock.preview_record(hunter_id)
    first={'slot':1,'status':base['status'] if base else 'not_generated',
           'bytes':base['bytes'] if base else None,
           'source_image_url':base['source_image_url'] if base else '',
           'last_error':base['last_error'] if base else ''}
    rows=db.rows('SELECT * FROM hunter_stock_gallery WHERE hunter_id=?',
                 (int(hunter_id),))
    existing={r['slot']:r for r in rows}
    output=[first]
    for slot in (2,3,4):
        row=existing.get(slot)
        output.append({
            'slot':slot,
            'status':row['status'] if row else 'not_generated',
            'bytes':stock._read_preview(row['preview_file'],row['product_id']) if row else None,
            'source_image_url':row['source_image_url'] if row else first['source_image_url'],
            'last_error':row['last_error'] if row else ''
        })
    return output


def _save(hunter_id,slot,product_id,source,status,filename='',error=''):
    with db.session() as connection:
        connection.execute("""
          INSERT INTO hunter_stock_gallery(
             hunter_id,slot,product_id,source_image_url,preview_file,status,
             last_error,created_at)
          VALUES(?,?,?,?,?,?,?,?)
          ON CONFLICT(hunter_id,slot) DO UPDATE SET
             product_id=excluded.product_id,
             source_image_url=excluded.source_image_url,
             preview_file=excluded.preview_file,
             status=excluded.status,
             last_error=excluded.last_error
          """,(hunter_id,slot,product_id,source,filename,status,error[:220],
               db.utcnow()))


def _generate_one(hunter_id,slot,account_id,token,ref,source,product_id):
    if not isinstance(account_id,str) or not re.fullmatch('[0-9a-fA-F]{32}',account_id.strip()):
        raise ValueError('Hibás Cloudflare Account ID.')
    if not token or len(str(token).strip())<10:
        raise ValueError('Hiányzik a Cloudflare API token.')
    model=next(iter(cloudflare_photos.MODELS.values()))
    prompt=stock.PROMPT+' '+EXTRA_PROMPTS[slot]
    reply=requests.post(
        cloudflare_photos.BASE+account_id.strip()+'/ai/run/'+model,
        headers={'Authorization':'Bearer '+str(token).strip()},
        files={'input_image_0':('source.png',io.BytesIO(ref),'image/png'),
               'prompt':(None,prompt),'width':(None,'1024'),
               'height':(None,'768')},
        timeout=(10,180))
    if reply.status_code in (401,403):
        raise ValueError('A Cloudflare API token nem érvényes.')
    if reply.status_code==429:
        raise ValueError('Elérted a Cloudflare ingyenes keretét.')
    if not reply.ok:
        raise ValueError('Cloudflare képgenerálási hiba (HTTP '+str(reply.status_code)+').')
    binary=cloudflare_photos._decode_response(reply)
    folder=db.DATA/'ai_pending'/str(int(product_id))
    folder.mkdir(parents=True,exist_ok=True)
    filename='AI_STOCK_'+uuid4().hex+'.png'
    (folder/filename).write_bytes(binary)
    _save(hunter_id,slot,product_id,source,'pending',filename)
    return 'pending'


def generate_remaining(hunter_id,account_id,token,*,force=False,only_slot=None):
    """Generate missing 2–4; repeat calls do not re-consume API credits.

    A failed slot is retried only via the explicit dashboard retry action.
    """
    initialize()
    if only_slot is not None and only_slot not in (2,3,4):
        raise ValueError('Hibás képsorszám.')
    row=db.row('SELECT * FROM hunter_results WHERE id=?',(hunter_id,))
    if not row or not row.get('product_id'):
        raise ValueError('Előbb válaszd ki a terméket.')
    base=stock.preview_record(hunter_id)
    if not base or base['status'] not in ('pending','approved') or not base['bytes']:
        return slots(hunter_id)
    target=[only_slot] if only_slot else [2,3,4]
    known={item['slot']:item for item in slots(hunter_id)}
    needed=[i for i in target
            if known[i]['status'] == 'not_generated' or
               (force and known[i]['status'] in ('pending','failed'))]
    if not needed:
        return slots(hunter_id)
    source=row.get('thumbnail') or ''
    # Source and rights must be reviewed before any AI illustration is published.
    ref=stock.download_catalog_image(source)
    for slot in needed:
        try:
            _generate_one(hunter_id,slot,account_id,token,ref,source,row['product_id'])
        except (ValueError,OSError,requests.RequestException) as error:
            _save(hunter_id,slot,row['product_id'],source,'failed',error=str(error))
            if 'keretét' in str(error) or 'token' in str(error).lower():
                break
    return slots(hunter_id)


def approve(hunter_id,slot):
    from .free_photo_import import save_approved
    if slot==1:
        return stock.approve(hunter_id)
    if slot not in (2,3,4):
        raise ValueError('Hibás képsorszám.')
    initialize()
    row=db.row('SELECT * FROM hunter_stock_gallery WHERE hunter_id=? AND slot=?',
               (hunter_id,slot))
    if not row or row['status']!='pending':
        raise ValueError('Nincs jóváhagyható képelőnézet.')
    data=stock._read_preview(row['preview_file'],row['product_id'])
    if not data:raise ValueError('Hiányzik a képelőnézet.')
    paths=save_approved([{'bytes':data,'approved':True}],db.DATA,row['product_id'])
    with db.session() as connection:
        connection.execute("""
          UPDATE hunter_stock_gallery SET status='approved',reviewed_at=?
          WHERE hunter_id=? AND slot=? AND status='pending'
        """,(db.utcnow(),hunter_id,slot))
    return paths


def regenerate(hunter_id,slot,account_id,token):
    if slot==1:
        return stock.generate_preview(hunter_id,account_id,token,force=True)
    return generate_remaining(hunter_id,account_id,token,force=True,only_slot=slot)
