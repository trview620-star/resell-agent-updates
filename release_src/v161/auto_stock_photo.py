"""Download a public catalog thumbnail and make ONE natural home-style AI preview.

Only stages an illustrative preview, never asserts ownership or resale rights
for the source photo. No source image is registered as an authentic product photo.
No Cloudflare API token is stored. External URLs are checked for SSRF, strict
size limits, and actual image content.
"""
from __future__ import annotations

from datetime import datetime, timezone
import io
import ipaddress
import re
import socket
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import requests
from PIL import Image, ImageOps, UnidentifiedImageError
from . import db, cloudflare_photos

SOURCE_MAX_BYTES=8_000_000
SOURCE_MAX_PIXELS=25_000_000
TIMEOUT=(5,15)

PROMPT=(
    'Image 0 is the reference photo of the product. Keep the exact SAME product, '
    'its shape, colors, printed logos and markings, quantity, attachments, '
    'materials and proportions. Do not change what the item is or add accessories. '
    'Transform the background from a sterile catalog listing to an ordinary '
    'slightly imperfect Hungarian home environment: an everyday wooden tabletop, '
    'real window daylight, natural contact shadows, quiet background objects '
    'softly out of focus. One casual handheld phone photograph, natural sharpness '
    'and modest grain. No dramatic studio lighting, no perfect plastic 3D look, '
    'no unrealistic gloss, no fake reflections, no highly saturated render, '
    'no pristine advertising layout. Do not rotate to an unseen side; use the '
    'visible reference camera angle. No people, collage, logos added, captions, '
    'watermarks, price tags or typography. This is an illustrative edited image '
    'that must be checked against the exact source product before any resale use.'
)


def _public_https_url(url):
    """Check hostname resolution (with no redirects) before downloading remote data."""
    if not isinstance(url,str) or len(url)>2000:return False
    try:
        parts=urlsplit(url)
        host=(parts.hostname or '').lower().rstrip('.')
        if parts.scheme!='https' or not host or parts.username or parts.password:
            return False
        if parts.port not in (None,443):return False
        if host in ('localhost','localhost.localdomain') or host.endswith(('.local','.internal','.lan','.onion')):
            return False
        if parts.fragment:return False
        from .research import valid_public_url
        if not valid_public_url(url):return False
        ips=socket.getaddrinfo(host,443,proto=socket.IPPROTO_TCP,type=socket.SOCK_STREAM)
        if not ips:return False
        return all(ipaddress.ip_address(a[4][0]).is_global for a in ips)
    except (OSError,ValueError,TypeError):
        return False


def download_catalog_image(url):
    """One HTTPS GET with maximum 8MB total; redirects and HTTP errors rejected."""
    if not _public_https_url(url):
        raise ValueError('Nem biztonságos vagy nem elérhető katalóguskép URL.')
    try:
        with requests.get(url,stream=True,timeout=TIMEOUT,allow_redirects=False,
                          headers={'Accept':'image/png,image/jpeg,image/webp'}) as response:
            if response.status_code!=200:
                raise ValueError('A katalóguskép nem tölthető le (HTTP '+str(response.status_code)+').')
            content_type=response.headers.get('Content-Type','').split(';')[0].strip().lower()
            if content_type not in ('image/png','image/jpeg','image/webp'):
                raise ValueError('Nem támogatott katalóguskép-formátum.')
            declared=response.headers.get('Content-Length')
            if declared and declared.isdigit() and int(declared)>SOURCE_MAX_BYTES:
                raise ValueError('A katalóguskép túl nagy.')
            raw=bytearray()
            for chunk in response.iter_content(chunk_size=65536):
                raw.extend(chunk)
                if len(raw)>SOURCE_MAX_BYTES:
                    raise ValueError('A katalóguskép túl nagy.')
    except requests.RequestException as e:
        raise ValueError('Katalóguskép letöltési hiba.') from e
    if not raw:raise ValueError('Üres katalóguskép.')
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.width*image.height>SOURCE_MAX_PIXELS:
                raise ValueError('A forráskép felbontása túl nagy.')
            image=ImageOps.exif_transpose(image).convert('RGB')
            image.thumbnail((480,480),resample=Image.Resampling.LANCZOS)
            buffer=io.BytesIO()
            image.save(buffer,format='PNG',optimize=True)
            return buffer.getvalue()
    except (OSError,UnidentifiedImageError,Image.DecompressionBombError) as e:
        raise ValueError('A katalóguskép nem érvényes.') from e


def init_store():
    db.initialize()
    with db.session() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS hunter_stock_photos(
           hunter_id INTEGER PRIMARY KEY REFERENCES hunter_results(id) ON DELETE CASCADE,
           product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
           source_image_url TEXT NOT NULL DEFAULT '',
           preview_file TEXT NOT NULL DEFAULT '',
           status TEXT NOT NULL DEFAULT 'pending',
           last_error TEXT NOT NULL DEFAULT '',
           reviewed_at TEXT,
           created_at TEXT NOT NULL
        );
        """)


def _read_preview(filename,product_id):
    if not filename or not re.fullmatch(r'AI_STOCK_[0-9a-f]{32}\.png',filename):return None
    folder=(db.DATA/'ai_pending'/str(int(product_id))).resolve()
    f=(folder/filename).resolve()
    if f.parent!=folder or not f.is_file() or f.stat().st_size>cloudflare_photos.MAX_RESPONSE:
        return None
    return f.read_bytes()


def preview_record(hunter_id):
    init_store()
    record=db.row('SELECT * FROM hunter_stock_photos WHERE hunter_id=?',(hunter_id,))
    if not record:return None
    data=_read_preview(record.get('preview_file'),record['product_id'])
    return {'status':record['status'],'bytes':data,
      'source_image_url':record['source_image_url'],
      'last_error':record['last_error'],'product_id':record['product_id'],
      'reviewed_at':record['reviewed_at']}


def _update_status(hunter_id,product_id,src,status,filename='',error=''):
    # Deliberately limit errors to human-readable messages, no remote response bodies.
    with db.session() as conn:
        conn.execute("""
        INSERT INTO hunter_stock_photos(
            hunter_id,product_id,source_image_url,preview_file,status,last_error,created_at
        ) VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(hunter_id) DO UPDATE SET
            product_id=excluded.product_id,source_image_url=excluded.source_image_url,
            preview_file=excluded.preview_file,status=excluded.status,
            last_error=excluded.last_error
        """,(hunter_id,product_id,src,filename,status,error[:220],db.utcnow()))


def generate_preview(hunter_id,account_id,token,*,force=False):
    """One request only for a new product; retry only when user explicitly presses it."""
    init_store()
    row=db.row('SELECT * FROM hunter_results WHERE id=?',(hunter_id,))
    if not row or not row.get('product_id'):
        raise ValueError('Előbb válaszd ki a terméket.')
    existing=preview_record(hunter_id)
    if existing and existing['status']=='approved':
        return existing
    if existing and existing['status']=='pending' and existing['bytes'] and not force:
        return existing
    src=row.get('thumbnail') or ''
    if not src:
        _update_status(hunter_id,row['product_id'],'','missing',error='Nincs képes találat ehhez a termékhez.')
        return preview_record(hunter_id)
    if not account_id or not token:
        raise ValueError('A képgeneráláshoz Cloudflare Account ID és API token szükséges.')
    try:
        ref=download_catalog_image(src)
        if not re.fullmatch(r'[0-9a-fA-F]{32}',str(account_id).strip()):
            raise ValueError('Hibás Cloudflare Account ID.')
        label=next(iter(cloudflare_photos.MODELS))
        url=cloudflare_photos.BASE+str(account_id).strip()+'/ai/run/'+cloudflare_photos.MODELS[label]
        response=requests.post(url,
            headers={'Authorization':'Bearer '+str(token).strip()},
            files={'input_image_0':('source.png',io.BytesIO(ref),'image/png'),
                   'prompt':(None,PROMPT),'width':(None,'1024'),'height':(None,'768')},
            timeout=(10,180))
        if response.status_code in (401,403):
            raise ValueError('A Cloudflare API token nem érvényes.')
        if response.status_code==429:
            raise ValueError('Elérted a Cloudflare ingyenes keretét.')
        if response.status_code==400:
            raise ValueError('Cloudflare HTTP 400: '+cloudflare_photos._safe_provider_error(
                response,str(account_id),str(token)))
        if not response.ok:
            raise ValueError('Cloudflare képgenerálási hiba (HTTP '+str(response.status_code)+').')
        binary=cloudflare_photos._decode_response(response)
        folder=db.DATA/'ai_pending'/str(int(row['product_id']))
        folder.mkdir(parents=True,exist_ok=True)
        filename='AI_STOCK_'+uuid4().hex+'.png'
        (folder/filename).write_bytes(binary)
        _update_status(hunter_id,row['product_id'],src,'pending',filename=filename)
        return preview_record(hunter_id)
    except (requests.RequestException,ValueError,OSError) as e:
        # Known validation/IO errors only; never include raw API response or tokens.
        _update_status(hunter_id,row['product_id'],src,'failed',error=str(e))
        return preview_record(hunter_id)


def approve(hunter_id):
    """Only user approval moves a preview to the permanent AI-illustrations directory."""
    from .free_photo_import import save_approved
    record=preview_record(hunter_id)
    if not record or record['status']!='pending' or not record['bytes']:
        raise ValueError('Nem található jóváhagyható képelőnézet.')
    paths=save_approved([{'bytes':record['bytes'],'approved':True}],db.DATA,record['product_id'])
    with db.session() as conn:
        conn.execute("""UPDATE hunter_stock_photos SET status='approved',reviewed_at=?
                        WHERE hunter_id=? AND status='pending'""",(db.utcnow(),hunter_id))
    return paths
