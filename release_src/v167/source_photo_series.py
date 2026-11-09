"""Source-preserving four-shot photo studio.

A source-preserving crop or layout never redraws the product, text, labels or logo.
Separate source photos are required for *actual* alternate angles and packaging.
Google catalogue imagery is labeled and not represented as a seller-taken photo.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

from . import db, auto_stock_photo as catalog, photo_shot_plan

MAX_BYTES=18_000_000
MAX_PIXELS=32_000_000
SERIES_DIR='faithful_photo_series'
BOX_NAMES=('box','doboz','packaging','csomag','csomagolas','csomagolás','karton')
VALID_SLOTS=(1,2,3,4)


def initialize():
    db.initialize()
    with db.session() as conn:
        conn.executescript("""
          CREATE TABLE IF NOT EXISTS faithful_photo_series(
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            slot INTEGER NOT NULL CHECK(slot BETWEEN 1 AND 4),
            filename TEXT NOT NULL,
            role TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_name TEXT NOT NULL DEFAULT '',
            source_digest TEXT NOT NULL,
            crop_box TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            PRIMARY KEY(product_id,slot)
          );
        """)


def _safe_path(product_id,filename):
    if not re.fullmatch(r'SOURCE_[0-9a-f]{32}\.png',str(filename or '')):
        return None
    folder=(db.DATA/SERIES_DIR/str(int(product_id))).resolve()
    path=(folder/filename).resolve()
    return path if path.parent==folder else None


def _uploaded_sources(product_id):
    photos=[]
    for record in db.rows(
        'SELECT filename,original_name FROM photos WHERE product_id=? ORDER BY created_at,id',
        (int(product_id),)):
        name=str(record['filename'] or '')
        if Path(name).name!=name:
            continue
        file=db.PHOTOS/name
        if not file.is_file() or file.stat().st_size>MAX_BYTES:
            continue
        photos.append({'content':file.read_bytes(),'name':record['original_name'],
                       'type':'original'})
    return photos


def _catalog_source(hunter_id,product_id):
    if hunter_id is None:
        return None
    entry=db.row('SELECT product_id,thumbnail FROM hunter_results WHERE id=?',(int(hunter_id),))
    if not entry or entry['product_id']!=int(product_id) or not entry['thumbnail']:
        return None
    raw=catalog.download_catalog_image(entry['thumbnail'])
    return {'content':raw,'name':'Beszállító katalógusképe','type':'catalogue'}


def _decode(data):
    if not isinstance(data,bytes) or not data or len(data)>MAX_BYTES:
        raise ValueError('Túl nagy vagy hiányzó fotó.')
    try:
        with Image.open(io.BytesIO(data)) as src:
            if src.width*src.height>MAX_PIXELS:
                raise ValueError('Túl nagy felbontású fotó.')
            src.load()
            return ImageOps.exif_transpose(src).convert('RGB')
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError) as exc:
        raise ValueError('Nem támogatott vagy sérült fotó.') from exc


def _crop_box(image,slot,focus):
    w,h=image.size
    if slot==1:
        return (0,0,w,h)
    # Focal point is chosen by the seller using two controls; a source crop
    # retains the exact source pixels and cannot hallucinate unseen geometry.
    fractions={2:(.48,.48),3:(.82,.82),4:(.36,.36)}
    wf,hf=fractions[slot]
    cw=max(1,int(w*wf))
    ch=max(1,int(h*hf))
    x,y=focus if focus is not None else ((.62,.68) if slot==2 else (.32,.35))
    x=max(0.,min(1.,float(x))); y=max(0.,min(1.,float(y)))
    left=max(0,min(w-cw,round(x*w-cw/2)))
    top=max(0,min(h-ch,round(y*h-ch/2)))
    return left,top,left+cw,top+ch


def _assigned(sources,slot):
    if slot==1:
        return sources[0], 'Teljes termék'
    if slot==2:
        return sources[0], 'Közeli részlet'
    if slot==3 and len(sources)>1:
        return sources[1], 'Másik eredeti fotó'
    if slot==3:
        return sources[0], 'Másik kivágás (nem új kameraállás)'
    boxes=[s for s in sources if any(token in str(s['name']).casefold() for token in BOX_NAMES)]
    if boxes:
        return boxes[0], 'Valódi dobozfotó'
    if len(sources)>2:
        return sources[2], 'Harmadik eredeti fotó'
    return sources[0], 'Második közeli részlet (doboz nincs igazolva)'


def _render(source,slot,*,focus=None,second_original=False,box_photo=False):
    image=_decode(source['content'])
    full=(slot==1 or slot==3 and second_original or slot==4 and box_photo)
    bounds=(0,0,image.width,image.height) if full else _crop_box(image,slot,focus)
    cropped=image.crop(bounds)
    # PNG is a lossless encoding of an unaltered rectangular source pixel region.
    # No AI, compositing, retouching, upscaling or logo recreation takes place.
    buff=io.BytesIO()
    cropped.save(buff,format='PNG',optimize=True)
    binary=buff.getvalue()
    if len(binary)>MAX_BYTES:
        raise ValueError('A képkivágás túl nagy. Adj meg kisebb képet.')
    return binary,bounds


def _sources(product_id,hunter_id):
    found=_uploaded_sources(product_id)
    if found:return found
    candidate=_catalog_source(hunter_id,product_id)
    return [candidate] if candidate else []


def create(product_id,*,hunter_id=None,replace_existing=False,focuses=None,only_slots=None):
    """Create four separately reviewed originals-preserving variations.

    When a slot was already approved, regenerating is always refused.
    When no source picture exists, report it rather than inventing one.
    """
    initialize()
    pid=int(product_id)
    if not db.row('SELECT id FROM products WHERE id=?',(pid,)):
        raise ValueError('A termék már nem található.')
    existing={r['slot']:r for r in db.rows(
        'SELECT * FROM faithful_photo_series WHERE product_id=?',(pid,))}
    requested=VALID_SLOTS if only_slots is None else tuple(only_slots)
    if not requested or any(slot not in VALID_SLOTS for slot in requested):
        raise ValueError('Érvénytelen képkocka.')
    if any(existing.get(slot,{}).get('status')=='approved' for slot in requested) and replace_existing:
        raise ValueError('A jóváhagyott képet nem lehet felülírni.')
    sources=_sources(pid,hunter_id)
    if not sources:
        raise ValueError('Nincs használható termékfotó. Tölts fel saját fotót, vagy adj meg képes beszállítói ajánlatot.')
    # Validate every source before writing files, so failures cannot leave
    # partially changed database state.
    for source in sources:
        _decode(source['content'])
    folder=db.DATA/SERIES_DIR/str(pid)
    folder.mkdir(parents=True,exist_ok=True)
    produced=[]
    for slot in requested:
        if slot in existing and existing[slot]['status']!='rejected' and not replace_existing:
            continue
        source,role=_assigned(sources,slot)
        different=slot==3 and len(sources)>1
        packaging=slot==4 and role=='Valódi dobozfotó'
        chosen=(focuses or {}).get(slot)
        data,box=_render(source,slot,focus=chosen,
                         second_original=different,box_photo=packaging)
        filename='SOURCE_'+uuid4().hex+'.png'
        digest=hashlib.sha256(source['content']).hexdigest()
        original_type=source['type']
        note=('Saját termékfotóból, módosítatlan képpontokból vágva.'
              if original_type=='original' else
              'Beszállítói katalógusképből vágva; nem saját fotó.')
        if slot==3 and not different:
            note+=' Másik kameraálláshoz külön forrásfotó szükséges.'
        if slot==4 and not packaging:
            note+=' Dobozfotóhoz a valódi csomagolást külön fotózd le.'
        image=_decode(source['content'])
        if min(image.size)<700:
            note+=' Alacsony felbontású forrás; az apró részletek nem biztos, hogy jól olvashatók.'
        tmp=folder/(filename+'.tmp')
        target=folder/filename
        try:
            tmp.write_bytes(data)
            tmp.replace(target)
            with db.session() as conn:
                conn.execute("""
                  INSERT INTO faithful_photo_series(
                      product_id,slot,filename,role,source_type,source_name,
                      source_digest,crop_box,note,status,created_at)
                  VALUES(?,?,?,?,?,?,?,?,?,'pending',?)
                  ON CONFLICT(product_id,slot) DO UPDATE SET
                      filename=excluded.filename,role=excluded.role,
                      source_type=excluded.source_type,
                      source_name=excluded.source_name,
                      source_digest=excluded.source_digest,
                      crop_box=excluded.crop_box,note=excluded.note,
                      status='pending',created_at=excluded.created_at
                """,(pid,slot,filename,role,original_type,source['name'],
                      digest,json.dumps(box),note,db.utcnow()))
        except Exception:
            target.unlink(missing_ok=True)
            tmp.unlink(missing_ok=True)
            raise
        produced.append(slot)
    return {'created':produced,'gallery':read(pid)}


def read(product_id,*,include_bytes=True):
    initialize()
    result=[]
    for row in db.rows('SELECT * FROM faithful_photo_series WHERE product_id=? ORDER BY slot',
                       (int(product_id),)):
        path=_safe_path(product_id,row['filename'])
        data=(path.read_bytes() if include_bytes and path and path.is_file()
              and path.stat().st_size<=MAX_BYTES else None)
        result.append({'slot':row['slot'],'role':row['role'],'status':row['status'],
                       'source_type':row['source_type'],'source_name':row['source_name'],
                       'note':row['note'],'bytes':data,'crop_box':json.loads(row['crop_box'])})
    return result


def approve(product_id,slot):
    initialize()
    if slot not in VALID_SLOTS:
        raise ValueError('Nem létező képsorszám.')
    record=db.row('SELECT * FROM faithful_photo_series WHERE product_id=? AND slot=?',
                  (int(product_id),int(slot)))
    if not record or record['status']!='pending':
        raise ValueError('Ehhez a képkockához nincs jóváhagyható előnézet.')
    path=_safe_path(product_id,record['filename'])
    if not path or not path.is_file():
        raise ValueError('Az előnézeti fotó nem található.')
    if record['source_type']=='catalogue':
        raise ValueError('Beszállítói képet nem lehet saját termékfotóként jóváhagyni. '
                         'Tölts fel eredeti képeket a termékről.')
    with db.session() as conn:
        conn.execute("""UPDATE faithful_photo_series SET status='approved'
                        WHERE product_id=? AND slot=?""",(int(product_id),int(slot)))
    return True


def reject(product_id,slot):
    initialize()
    if slot not in VALID_SLOTS:
        raise ValueError('Nem létező képsorszám.')
    with db.session() as conn:
        conn.execute("""UPDATE faithful_photo_series SET status='rejected'
                        WHERE product_id=? AND slot=?""",(int(product_id),int(slot)))
    return True
