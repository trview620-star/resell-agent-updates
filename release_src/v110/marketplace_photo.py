"""Local photo finish and white-background cutout/composite. Originals untouched."""
from __future__ import annotations
from io import BytesIO
from pathlib import Path
from hashlib import sha256
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps
from . import db

MAX_BYTES=15*1024*1024
OUTPUT=(1080,1350)

def _open(data):
    if not isinstance(data,bytes) or not data or len(data)>MAX_BYTES:
        raise ValueError('Use JPG, PNG or WEBP under 15 MB.')
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format not in ('JPEG','PNG','WEBP') or image.width*image.height>30_000_000:
                raise ValueError('Unsupported or oversized image.')
            return ImageOps.exif_transpose(image).convert('RGBA')
    except OSError as exc:
        raise ValueError('Could not read image.') from exc

def _cutout(source):
    im=source.copy()
    im.thumbnail((1500,1500),Image.Resampling.LANCZOS)
    alpha=im.getchannel('A')
    if alpha.getextrema()[0]<230:
        return im
    rgb=im.convert('RGB')
    w,h=rgb.size
    corners=((1,1),(w-2,1),(1,h-2),(w-2,h-2))
    whites=sum(min(rgb.getpixel(pt))>=215 and
        max(rgb.getpixel(pt))-min(rgb.getpixel(pt))<=45 for pt in corners)
    if whites<2:
        raise ValueError('Room mode requires a transparent or white-background image. Use Natural finish for other photos.')
    pixels=np.asarray(rgb).astype(np.int16)
    small=pixels.min(axis=2)
    neutral=(small>=135)&(pixels.max(axis=2)-small<=22)
    region=Image.fromarray(np.where(neutral,255,0).astype('uint8'),'L').copy()
    seeds=corners+((w//2,1),(w//2,h-2),(1,h//2),(w-2,h//2))
    for xy in seeds:
        if region.getpixel(xy)==255:
            ImageDraw.floodfill(region,xy,120,thresh=1)
    background=np.asarray(region)==120
    portion=float(background.mean())
    if not 0.09<=portion<=0.94:
        raise ValueError('White background could not be separated reliably. Try another photo.')
    mask=Image.fromarray(np.where(background,0,255).astype('uint8'),'L')
    mask=mask.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.65))
    box=mask.point(lambda n:255 if n>15 else 0).getbbox()
    if not box:raise ValueError('No product detected.')
    im.putalpha(mask)
    pad=4
    return im.crop((max(0,box[0]-pad),max(0,box[1]-pad),
                    min(w,box[2]+pad),min(h,box[3]+pad)))

def _finish(rgb,strength,seed):
    if not 0<=strength<=1:
        raise ValueError('Effect strength is outside 0..1.')
    if not strength:return rgb.convert('RGB')
    rgb=ImageEnhance.Color(rgb.convert('RGB')).enhance(1-0.04*strength)
    arr=np.asarray(rgb,dtype=np.float32).copy()
    h,w,_=arr.shape
    yy,xx=np.ogrid[-1:1:complex(h),-1:1:complex(w)]
    falloff=np.clip((xx*xx+yy*yy)/2,0,1)
    arr*=(1-0.07*strength*falloff)[...,None]
    arr[:,:,0]+=1.5*strength
    arr[:,:,2]-=1.0*strength
    rng=np.random.default_rng(seed)
    arr+=rng.normal(0,1.6*strength,(h,w,1))
    return Image.fromarray(np.clip(arr,0,255).astype('uint8'),'RGB')

def make_marketplace_photo(source_bytes,*,room_bytes=None,strength=0.45,scale=0.73,
                           x=0.5,y=0.72,blur=5):
    source=_open(source_bytes)
    seed=int(sha256(source_bytes).hexdigest()[:8],16)
    if room_bytes is None:
        source.thumbnail((1920,1920),Image.Resampling.LANCZOS)
        result=source.convert('RGB')
    else:
        if not 0.35<=scale<=0.95 or not 0<=x<=1 or not 0<=y<=1 or not 0<=blur<=16:
            raise ValueError('Placement controls out of range.')
        room=_open(room_bytes)
        background=ImageOps.fit(room.convert('RGB'),OUTPUT,method=Image.Resampling.LANCZOS)
        background=ImageEnhance.Contrast(background).enhance(0.96)
        if blur: background=background.filter(ImageFilter.GaussianBlur(blur))
        fg=_cutout(source)
        factor=min(OUTPUT[0]*scale/fg.width,OUTPUT[1]*0.74/fg.height)
        fg=fg.resize((max(1,int(fg.width*factor)),max(1,int(fg.height*factor))),
                      Image.Resampling.LANCZOS)
        px=int(x*(OUTPUT[0]-fg.width))
        py=int(y*(OUTPUT[1]-fg.height))
        px=max(0,min(OUTPUT[0]-fg.width,px))
        py=max(0,min(OUTPUT[1]-fg.height,py))
        # Separate, gentle contact shadow. Product pixels remain sourced from original.
        contact=Image.new('L',OUTPUT,0)
        draw=ImageDraw.Draw(contact)
        bottom=min(OUTPUT[1]-2,py+fg.height-max(5,fg.height//35))
        draw.ellipse((max(0,px+fg.width//10),max(0,bottom-14),
                      min(OUTPUT[0]-1,px+fg.width-fg.width//10),
                      min(OUTPUT[1]-1,bottom+32)),fill=95)
        contact=contact.filter(ImageFilter.GaussianBlur(20))
        base=background.convert('RGBA')
        shadow=Image.new('RGBA',OUTPUT,(0,0,0,0))
        shadow.paste((10,8,5,100),(0,0,*OUTPUT),contact)
        base=Image.alpha_composite(base,shadow)
        product_layer=Image.new('RGBA',OUTPUT,(0,0,0,0))
        product_layer.alpha_composite(fg,(px,py))
        result=Image.alpha_composite(base,product_layer).convert('RGB')
        strength=min(strength,0.35)
    result=_finish(result,strength,seed)
    out=BytesIO()
    result.save(out,'JPEG',quality=93,subsampling=0,optimize=True)
    return out.getvalue()

def save_marketplace_variant(photo_id,jpeg):
    row=db.row('SELECT * FROM photos WHERE id=?',(photo_id,))
    if not row:raise ValueError('Original photo not found.')
    original=db.PHOTOS/row['filename']
    if not original.is_file() or original.resolve().parent!=db.PHOTOS.resolve():
        raise ValueError('Original photo missing.')
    _open(jpeg)
    name=f'marketplace_edit_{photo_id}_{sha256(jpeg).hexdigest()[:14]}.jpg'
    output=db.PHOTOS/name
    output.write_bytes(jpeg)
    return output

def saved_variants(photo_id):
    if not isinstance(photo_id,int) or photo_id<1:return []
    return sorted(db.PHOTOS.glob(f'marketplace_edit_{photo_id}_*.jpg'),
                  key=lambda path:path.stat().st_mtime,reverse=True)
