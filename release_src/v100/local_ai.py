"""Optional local Ollama model; no API token charges. AI output requires review."""
from __future__ import annotations
import base64,json,os
from pathlib import Path
import requests

BASE='http://127.0.0.1:11434'
MODEL=os.getenv('RESELL_OLLAMA_MODEL','gemma3:4b')

def model_status():
    try:
        r=requests.get(BASE+'/api/tags',timeout=3)
        r.raise_for_status()
        return {'connected':True,'models':[x.get('name','') for x in r.json().get('models',[])]}
    except (requests.RequestException,ValueError,KeyError):
        return {'connected':False,'models':[]}

def _ask(model,prompt,images=None):
    payload={'model':model,'stream':False,'messages':[{'role':'user','content':prompt,
              **({'images':images} if images else {})}],
             'options':{'temperature':0}}
    try:
        r=requests.post(BASE+'/api/chat',json=payload,timeout=(5,180))
        r.raise_for_status()
        return str(r.json()['message']['content'])
    except (requests.RequestException,ValueError,KeyError) as e:
        raise ValueError('Ollama unavailable, model missing or response invalid') from e

def analyze_photo(path:Path,model=MODEL):
    if not path.is_file() or path.stat().st_size>15_000_000:
        raise ValueError('A saved original under 15 MB is required')
    prompt=('Identify only directly visible product details. Do not claim a verified model, authenticity, '
            'condition or function from appearance alone. Output JSON with product_type, visible_text, '
            'likely_brand, likely_model, confidence and facts_to_verify.')
    text=_ask(model,prompt,[base64.b64encode(path.read_bytes()).decode('ascii')])
    try:
        start=text.find('{');end=text.rfind('}')+1
        parsed=json.loads(text[start:end])
        if not isinstance(parsed,dict):raise ValueError('Not an object')
        return parsed
    except (ValueError,TypeError) as e:raise ValueError('Ollama did not return usable JSON') from e

def draft_description(facts,model=MODEL):
    if not facts.strip():raise ValueError('Add confirmed facts first')
    prompt=('Write a concise, natural Hungarian resale listing from only these VERIFIED facts. '
            'Never add imaginary condition, original purchase history, authenticity, testing, stock or '
            'delivery claims. Plain text only. Facts:\n'+facts[:4000])
    return _ask(model,prompt)[:6000]
