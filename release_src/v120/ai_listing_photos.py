"""Generate separate AI illustrative product-photo previews from a reference image.

Uses the OpenAI Images Edit API by explicit user action only.
Never modifies a source file. Images are simulations, not evidence of condition.
"""
from __future__ import annotations
import base64
import io
import json
from pathlib import Path
from PIL import Image, ImageOps
import requests

MODEL = 'gpt-image-1.5'
ANGLES = (
    ('front_three_quarter', 'Front three-quarter', 'low 3/4 front view, showing the front and side'),
    ('straight_front', 'Straight front', 'straight-on front view at tabletop height'),
    ('side_profile', 'Side profile', 'true side-on profile view'),
    ('rear_three_quarter', 'Rear three-quarter', 'low 3/4 rear view, showing the rear and side'),
)

def prepare_reference(path: Path) -> bytes:
    path=Path(path)
    if not path.is_file():
        raise ValueError('Original photo is missing.')
    with Image.open(path) as source:
        if source.width*source.height>35_000_000:
            raise ValueError('Reference photo exceeds safe dimensions.')
        frame=ImageOps.exif_transpose(source).convert('RGB')
        frame.thumbnail((1800,1800))
        out=io.BytesIO()
        frame.save(out,'PNG',optimize=True)
        data=out.getvalue()
    if len(data)>12_000_000:
        raise ValueError('Reference photo is too large.')
    return data

def make_prompt(angle_name:str, product_name:str='',feedback:str='') -> str:
    angle=next((item for item in ANGLES if item[0]==angle_name),None)
    if angle is None: raise ValueError('Unknown camera angle')
    name=str(product_name or 'Product').strip()[:160]
    notes=str(feedback or '').strip()[:800]
    return (
        'Create ONE independent realistic photographic image, never a collage, grid, montage, diptych, '
        'before/after, labels, infographic, poster or composite of multiple pictures. '
        'Use the reference image to identify the product. Product reference name: '+name+'. '
        'Show a single product, with its actual box only if the reference shows a box. '
        'Camera angle: '+angle[2]+'. '
        'Set it on an ordinary wood table in a believable lived-in apartment or kitchen, '
        'soft window daylight, imperfect natural camera framing, realistic background depth of field '
        'and natural contact shadow. Not a studio advertisement, not cinematic, not obviously AI. '
        'Match product color, shape, stripes, accessories, labels and visible parts as faithfully as '
        'the reference permits; do not add extra objects sold with the product, do not invent damage '
        'or claim anything about condition. Do not add text, watermarks or overlay graphics. '
        'For views that are not visible in the supplied photograph, create a plausible illustrative '
        'approximation only; do not assert authenticity of unseen details. '
        +(('Additional user-requested visual correction: '+notes+'. ') if notes else '')
    )

def decode_result(payload:dict) -> bytes:
    try:
        encoded=payload['data'][0]['b64_json']
        if not isinstance(encoded,str):raise ValueError('No image')
        image=base64.b64decode(encoded,validate=True)
        with Image.open(io.BytesIO(image)) as img:
            img.verify()
        if len(image)>25_000_000:raise ValueError('Image too large')
        return image
    except (KeyError,IndexError,TypeError,ValueError,base64.binascii.Error,OSError) as e:
        raise ValueError('Image service did not return a valid image.') from e

def generate_view(reference:Path,angle:str,api_key:str,product_name:str='',feedback:str='') -> bytes:
    if not api_key or not isinstance(api_key,str) or not api_key.strip():
        raise ValueError('Enter an image generation API key.')
    source=prepare_reference(reference)
    fields={'model':MODEL,'prompt':make_prompt(angle,product_name,feedback),
           'size':'1536x1024','quality':'medium','output_format':'png','input_fidelity':'high'}
    try:
        response=requests.post('https://api.openai.com/v1/images/edits',
            headers={'Authorization':'Bearer '+api_key.strip()},
            data=fields,
            files={'image[]':('reference.png',io.BytesIO(source),'image/png')},
            timeout=(10,210))
    except requests.RequestException as e:
        raise ValueError('Image service is unreachable. Check internet access.') from e
    if not response.ok:
        try:
            message=str(response.json().get('error',{}).get('message',''))
        except (ValueError,AttributeError):message=''
        # Never echo submitted key or request payload.
        status=response.status_code
        if status in (401,403):
            raise ValueError('API key rejected or image API access unavailable.')
        if status==429:
            raise ValueError('Image API request limit or billing limit reached.')
        raise ValueError('Image generation failed (HTTP '+str(status)+'). '+message[:160])
    try: return decode_result(response.json())
    except ValueError as e: raise e
    except (requests.RequestException,TypeError,AttributeError) as e:
        raise ValueError('Invalid image generation response.') from e
