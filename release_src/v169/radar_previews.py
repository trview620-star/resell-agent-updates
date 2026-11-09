"""Safe, evidence-matched supplier photo previews for the Top 50 research table.

These remain supplier/catalogue thumbnails, never genuine seller photos.
No additional API usage is required after a Shopping search has been saved.
"""
from __future__ import annotations

from . import shopping


def normalize_thumbnail(raw):
    from . import hunter
    if not isinstance(raw,str):
        return ''
    return hunter.safe_thumbnail(raw)


def preview_for(phrase, offers):
    """Choose a safe thumbnail from a matching saved shopping offer.

    Prefer a direct retail result with a matching model and a thumbnail.
    Never invent or fetch a replacement image from an unrelated product.
    """
    candidates=[]
    for offer in offers:
        image=normalize_thumbnail(offer.get('thumbnail'))
        if not image:
            continue
        title=str(offer.get('title') or '')
        match, _=shopping.classify_product_match(title,phrase)
        if match in ('Different model','Accessory / compatible item'):
            continue
        direct=bool(offer.get('url','').startswith('https://')) and \
            'google.com/search?' not in str(offer.get('url',''))
        score=int(match=='Model code matches')*10+int(direct)*3
        candidates.append((score,image))
    if not candidates:
        return ''
    candidates.sort(key=lambda item:-item[0])
    return candidates[0][1]


def offer_images(offers, limit=4):
    """Return up to four distinct catalog thumbnails of the *same search*."""
    seen=set()
    found=[]
    for offer in offers:
        image=normalize_thumbnail(offer.get('thumbnail'))
        if image and image not in seen:
            seen.add(image)
            found.append({'image':image,'title':offer.get('title',''),
                          'merchant':offer.get('merchant','')})
            if len(found)>=limit:
                break
    return found


def url_from_hit(hit):
    """Shopping APIs expose both imageUrl and thumbnail variations."""
    from . import hunter
    if not isinstance(hit,dict):
        return ''
    for field in ('imageUrl','image_url','thumbnailUrl','thumbnail','image',
                  'imageLink','image_link'):
        image=hunter.safe_thumbnail(hit.get(field))
        if image:
            return image
    return ''
