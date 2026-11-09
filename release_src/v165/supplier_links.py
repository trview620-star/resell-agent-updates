"""Reliable supplier navigation from Google Shopping result records.

Avoid transient Google offer links; a search fallback is clearly labeled, never
presented as a checked-out supplier product page.
"""
from __future__ import annotations
from urllib.parse import urlsplit, urlencode
import re
from .research import valid_public_url

FIELDS=('offerUrl','productUrl','productURL','product_link','productLink',
        'merchantLink','merchantUrl','sellerUrl','link','url')
GOOGLE_HOSTS=('google.com','google.hu','googleadservices.com',
              'googleusercontent.com','gstatic.com','serper.dev')

def direct_url(url):
    if not isinstance(url,str) or not valid_public_url(url):
        return False
    try:
        hostname=(urlsplit(url).hostname or '').lower().strip('.')
        if not hostname:return False
        if any(hostname==domain or hostname.endswith('.'+domain)
               for domain in GOOGLE_HOSTS):return False
        return urlsplit(url).scheme=='https'
    except (ValueError,TypeError):
        return False

def search_url(title,merchant=''):
    # A stable normal Google search page, rather than Google's transient Shopping offer ID.
    q=' '.join([str(title or '').strip(),str(merchant or '').strip(),'termék rendelés'])
    return 'https://www.google.com/search?'+urlencode({'q':q[:180],'gl':'hu','hl':'hu'})

def offer_url(item,payload=None):
    """Find a direct retailer URL matched to this exact title and merchant."""
    target_title=' '.join(str(item.get('title','')).casefold().split())
    target_store=' '.join(str(item.get('merchant','')).casefold().split())
    candidates=[]
    for hit in (payload or {}).get('shopping_results',[]):
        if not isinstance(hit,dict):continue
        title=' '.join(str(hit.get('title') or hit.get('name') or '').casefold().split())
        store=' '.join(str(hit.get('source') or hit.get('merchant') or hit.get('seller') or '').casefold().split())
        if title==target_title and store==target_store:
            candidates.append(hit)
    candidates.append(item)
    for hit in candidates:
        for field in FIELDS:
            url=hit.get(field)
            if direct_url(url):
                return url,'Közvetlen kereskedői link – elérhetőség még nem ellenőrzött'
    return search_url(item.get('title'),item.get('merchant')),'Keresési hivatkozás – nincs ellenőrzött termékoldal'

def navigable(url,title,merchant):
    """Repair previously stored temporary Google URLs on display."""
    if direct_url(url):
        return url,True
    return search_url(title,merchant),False
