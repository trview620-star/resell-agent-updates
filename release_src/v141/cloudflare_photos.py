"""Opt-in Cloudflare Workers AI image editing with safe per-photo preview.

No API credentials persisted. Source is resized under Cloudflare's 512x512
reference limit. Image generation occurs on Cloudflare's GPUs, not user's GPU.
"""
from __future__ import annotations
import base64
import io
import re
from pathlib import Path
from urllib.parse import quote
import requests
from PIL import Image, ImageOps, UnidentifiedImageError
from .ai_listing_photos import ANGLES

MODELS = {
    'FLUX.2 Klein 4B (more free generations)': '@cf/black-forest-labs/flux-2-klein-4b',
    'FLUX.2 Klein 9B (higher quality, fewer free generations)': '@cf/black-forest-labs/flux-2-klein-9b',
}
BASE='https://api.cloudflare.com/client/v4/accounts/'
MAX_RESPONSE=26_000_000

def reference_png(path):
    p=Path(path)
    if not p.is_file(): raise ValueError('Original reference photo is missing.')
    try:
        with Image.open(p) as image:
            if image.width * image.height>35_000_000: raise ValueError('Reference photo dimensions too large.')
            image=ImageOps.exif_transpose(image).convert('RGB')
            image.thumbnail((480,480),resample=Image.Resampling.LANCZOS)
            out=io.BytesIO()
            image.save(out,format='PNG',optimize=True)
            result=out.getvalue()
            if len(result)>5_000_000:raise ValueError('Reference photo could not be compressed.')
            return result
    except (OSError,UnidentifiedImageError,Image.DecompressionBombError) as e:
        raise ValueError('Original image is invalid.') from e

def prompt_for(angle,product_name='',feedback=''):
    entry=next((x for x in ANGLES if x[0]==angle),None)
    if entry is None:raise ValueError('Unsupported angle')
    return (
        'Image 0 is the actual product reference. Create exactly ONE independent '
        'realistic camera photograph, never a collage, split screen, grid, poster '
        'or multi-panel. Subject: '+str(product_name)[:150]+'. '
        'Show the same product from this camera angle: '+entry[2]+'. '
        'Place it on an ordinary wooden table in a lived-in home, with natural '
        'window lighting, imperfect casual seller-camera framing, subtle background '
        'blur and correct contact shadows. Preserve product shape, color, material, '
        'logos, markings, details and all visible accessories where possible; '
        'if a retail box is present in the reference, include the same box in the '
        'background without changing the product. Do not add parts, additional '
        'sold items, invented damage, overlay text or watermarks. '
        'When unseen sides must be synthesized, they are hypothetical illustrations, '
        'not verified views of the real product. '
        + ('Visual changes requested: '+str(feedback).strip()[:650]+'. ' if feedback else '')
    )

def _decode_response(response):
    if len(response.content)>MAX_RESPONSE*2:
        raise ValueError('Image response exceeds safe size.')
    if response.headers.get('Content-Type','').lower().startswith('image/'):
        binary=response.content
    else:
        try:
            body=response.json()
            if not isinstance(body,dict):
                raise ValueError('Unexpected image API response.')
            if body.get('success') is False:
                raise ValueError('Cloudflare rejected the image request.')
            result=body.get('result')
            if isinstance(result,dict):
                val=result.get('image')
            elif isinstance(result,str):
                val=result
            else:
                val=body.get('image')
            if not isinstance(val,str):
                raise ValueError('Cloudflare did not return an encoded image.')
            if val.startswith('data:image/') and ',' in val:
                val=val.split(',',1)[1]
            binary=base64.b64decode(val,validate=True)
        except (ValueError,TypeError,KeyError,base64.binascii.Error) as e:
            raise ValueError('Cloudflare returned an invalid image response.') from e
    if len(binary)>MAX_RESPONSE:
        raise ValueError('Image too large.')
    try:
        with Image.open(io.BytesIO(binary)) as image:
            if image.width * image.height>35_000_000:raise ValueError('Image dimensions too large.')
            image.load()
            out=io.BytesIO()
            image.convert('RGB').save(out,'PNG',optimize=True)
            converted=out.getvalue()
    except (OSError,UnidentifiedImageError,Image.DecompressionBombError) as e:
        raise ValueError('Generated image is invalid.') from e
    if len(converted)>MAX_RESPONSE:raise ValueError('Generated image exceeds size limit.')
    return converted


def _safe_provider_error(response, account_id, token):
    """Show Cloudflare's validation reason without exposing bearer credentials."""
    try:
        payload=response.json()
        errors=payload.get('errors') if isinstance(payload,dict) else None
        first=errors[0] if isinstance(errors,list) and errors else None
        if isinstance(first,dict):
            code=str(first.get('code',''))[:12]
            message=str(first.get('message',''))
        else:
            code=''
            message=str(payload.get('message','')) if isinstance(payload,dict) else ''
    except (ValueError,TypeError,AttributeError,IndexError):
        code=''
        message=''
    # Structured Cloudflare messages explain invalid fields and quota configuration.
    # Strip secrets and potential PII before showing in the local UI.
    message=message.replace(token.strip(),'[REDACTED]').replace(account_id.strip(),'[ACCOUNT]')
    message=re.sub(r'(?i)\bBearer\s+\S+', 'Bearer [REDACTED]', message)
    message=re.sub(r'cf(?:ut|at|k)_[A-Za-z0-9_-]+','[REDACTED]',message)
    message=re.sub(r'(?i)[\w.+-]+@[\w.-]+\.[a-z]{2,}','[EMAIL]',message)
    message=re.sub(r'(?i)\b[0-9a-f]{32}\b','[ACCOUNT]',message)
    message=re.sub(r'[\r\n\t]+',' ',message).strip()[:240]
    return (('Cloudflare error '+code+': ') if code else 'Cloudflare validation: ') + (message or 'No details provided by Cloudflare.')

def generate(path,angle,account_id,token,model_label,product_name='',feedback=''):
    if not isinstance(account_id,str) or not re.fullmatch('[a-fA-F0-9]{32}',account_id.strip()):
        raise ValueError('Enter the 32-character Cloudflare Account ID.')
    if not isinstance(token,str) or len(token.strip())<10:
        raise ValueError('Enter your Cloudflare Workers AI API token.')
    if model_label not in MODELS:
        raise ValueError('Invalid AI model.')
    reference=reference_png(path)
    model=MODELS[model_label]
    url=BASE+account_id.strip()+'/ai/run/'+model
    try:
        response=requests.post(
            url,
            headers={'Authorization':'Bearer '+token.strip()},
            data={'prompt':prompt_for(angle,product_name,feedback),
                  'width':'1024','height':'768'},
            files={'input_image_0':('reference.png',io.BytesIO(reference),'image/png')},
            timeout=(10,180))
    except requests.RequestException as e:
        raise ValueError('Cannot reach Cloudflare. Check connection or retry later.') from e
    # Do not echo errors from the provider: they can include sensitive values.
    if response.status_code in (401,403):
        raise ValueError('Cloudflare rejected the token or Workers AI permissions.')
    if response.status_code==429:
        raise ValueError('Cloudflare rate limit or free usage allowance reached.')
    if response.status_code in (402,409):
        raise ValueError('Cloudflare may require billing or account activation for this model.')
    if response.status_code == 400:
        raise ValueError('Cloudflare HTTP 400: '+_safe_provider_error(response,account_id,token))
    if not response.ok:
        raise ValueError('Cloudflare image generation failed (HTTP '+str(response.status_code)+').')
    return _decode_response(response)
