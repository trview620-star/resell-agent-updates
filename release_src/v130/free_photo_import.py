"""No-API image import. ChatGPT creates pictures outside this app.

This module only validates, previews and stores seller-reviewed AI illustrations.
Never overwrites original photos or treats illustrations as authentic product evidence.
"""
from __future__ import annotations
import hashlib
import io
import zipfile
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

EXTS={'.png','.jpg','.jpeg','.webp'}
MAX_FILES=12
MAX_BYTES=18_000_000
MAX_TOTAL=85_000_000
MAX_PIXELS=32_000_000

def _picture(name: str, raw: bytes) -> dict:
    if not isinstance(raw,bytes) or len(raw)>MAX_BYTES or not raw:
        raise ValueError('Image missing or too large (18 MB max).')
    suffix=Path(name).suffix.lower()
    if suffix not in EXTS: raise ValueError('Only PNG, JPG and WEBP images are supported.')
    try:
        with Image.open(io.BytesIO(raw)) as img:
            w,h=img.size
            if not 1 <= w*h <= MAX_PIXELS:
                raise ValueError('Image dimensions too large.')
            fmt=img.format
            if fmt not in ('PNG','JPEG','WEBP'):
                raise ValueError('Invalid image format.')
            img.load()
            output=ImageOps.exif_transpose(img).convert('RGB')
            buf=io.BytesIO()
            output.save(buf,format='PNG',optimize=True)
    except (OSError,UnidentifiedImageError,Image.DecompressionBombError) as exc:
        raise ValueError('File is not a valid image.') from exc
    result=buf.getvalue()
    if len(result)>MAX_BYTES:
        raise ValueError('Converted image too large.')
    return {'name':Path(name).name[:140], 'bytes':result,
            'width':output.width, 'height':output.height,
            'sha256':hashlib.sha256(result).hexdigest(),'approved':False}

def unpack_uploads(uploads):
    """uploads: iterable of (filename, byte content). ZIPs are read in memory; no path extraction."""
    images=[]
    seen=set()
    used=0
    for name,content in uploads:
        if not isinstance(name,str) or not isinstance(content,bytes):
            raise ValueError('Invalid upload.')
        used+=len(content)
        if used>MAX_TOTAL: raise ValueError('Upload batch exceeds 85 MB.')
        if Path(name).suffix.lower()=='.zip':
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as package:
                    members=[x for x in package.infolist()
                        if not x.is_dir() and Path(x.filename).suffix.lower() in EXTS]
                    if len(members)>MAX_FILES or len(images)+len(members)>MAX_FILES:
                        raise ValueError('Maximum 12 images per batch.')
                    if sum(x.file_size for x in members)>MAX_TOTAL:
                        raise ValueError('ZIP uncompressed images exceed 85 MB.')
                    for member in members:
                        if member.file_size>MAX_BYTES:
                            raise ValueError('Image in ZIP exceeds 18 MB.')
                        # Never trust archive filenames as filesystem paths.
                        data=package.read(member)
                        used+=len(data)
                        if used>2*MAX_TOTAL:
                            raise ValueError('Too much uncompressed data.')
                        photo=_picture(Path(member.filename).name,data)
                        if photo['sha256'] not in seen:
                            seen.add(photo['sha256'])
                            images.append(photo)
            except (zipfile.BadZipFile,RuntimeError,EOFError) as exc:
                raise ValueError('Invalid or damaged ZIP file.') from exc
        else:
            photo=_picture(name,content)
            if photo['sha256'] not in seen:
                seen.add(photo['sha256'])
                images.append(photo)
        if len(images)>MAX_FILES:raise ValueError('Maximum 12 images per batch.')
    if not images:
        raise ValueError('No valid PNG, JPG or WEBP images found.')
    return images

def approved_zip(images: list[dict], product_id: int):
    chosen=[x for x in images if x.get('approved')]
    if not chosen:raise ValueError('Approve at least one image.')
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        for i,photo in enumerate(chosen,1):
            z.writestr(f'AI_ILLUSTRATIVE_product_{int(product_id)}_{i:02}.png',photo['bytes'])
        z.writestr('README_AI_ILLUSTRATIVE.txt',
            'Illustrative AI images. Verify against authentic product photos. '
            'Images are not proof of condition, authenticity, ownership or included accessories.\n')
    return buf.getvalue()

def save_approved(images:list[dict],base:Path,product_id:int):
    chosen=[x for x in images if x.get('approved')]
    if not chosen:raise ValueError('Approve at least one image.')
    destination=Path(base)/'ai_previews'/str(int(product_id))
    destination.mkdir(parents=True,exist_ok=True)
    paths=[]
    for item in chosen:
        path=destination/f'AI_ILLUSTRATIVE_{uuid4().hex}.png'
        path.write_bytes(item['bytes'])
        paths.append(path)
    return paths
