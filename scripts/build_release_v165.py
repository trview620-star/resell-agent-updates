"""Resell Agent v1.6.5 - supplier links, Top 50 intelligence and modern UI."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from hashlib import sha256
import sys

base=Path(sys.argv[1] if len(sys.argv)>1 else 'resell-agent-mvp-v1.6.4.zip')
check=Path(str(base)+'.sha256')
assert check.is_file(),'Published source checksum missing'
assert sha256(base.read_bytes()).hexdigest()==check.read_text(encoding='ascii').split()[0], 'Published base checksum mismatch'

ROOT='resell-agent-starter/'
with ZipFile(base) as z:
    files={i.filename:z.read(i.filename) for i in z.infolist() if not i.is_dir()}

def replace(path,old,new):
    key=ROOT+path
    raw=files[key].decode('utf-8')
    if old not in raw:
        raise RuntimeError('Base changed: '+path+' missing '+repr(old[:125]))
    files[key]=raw.replace(old,new).encode('utf-8')

def span(path,start,end,replacement):
    key=ROOT+path
    raw=files[key].decode('utf-8')
    i=raw.find(start)
    if i<0:raise RuntimeError('Missing start '+path+': '+repr(start[:115]))
    j=raw.find(end,i+len(start))
    if j<0:raise RuntimeError('Missing end '+path+': '+repr(end[:115]))
    files[key]=(raw[:i]+replacement+raw[j:]).encode('utf-8')

replace('agent/updater.py',"VERSION = '1.6.4'","VERSION = '1.6.5'")
replace('tests/test_updater.py','1.6.5','1.6.6')
replace('tests/test_upload_update.py',"'1.6.5'","'1.6.6'")
replace('tests/test_upload_update.py',"'1.6.4'","'1.6.5'")
replace('tests/test_upload_update.py',"'v1.6.5'","'v1.6.6'")

for name in ('supplier_links','market_intelligence','product_copy','ui_market_radar','ui_theme'):
    files[ROOT+'agent/'+name+'.py']=Path('release_src/v165/'+name+'.py').read_bytes()
files[ROOT+'tests/test_radar_v165.py']=Path('release_src/v165/test_radar_v165.py').read_bytes()

# Source links can be transient Google offers. Do not reuse them as retailer URLs.
replace('agent/hunter.py','from . import db, shopping, condition_copy',
    'from . import db, shopping, condition_copy, product_copy, supplier_links')
replace('agent/hunter.py',
    "                img=pictures.get((title.strip().casefold(),seller.strip().casefold()),'')",
    "                img=pictures.get((title.strip().casefold(),seller.strip().casefold()),'')\n"
    "                source_url,source_kind=supplier_links.offer_url(item,payload)")
replace('agent/hunter.py',
    "(item['url'],title,seller,int(item['price_huf']),img,phrase,topic,\n                          item['kind'],db.utcnow())",
    "(source_url,title,seller,int(item['price_huf']),img,phrase,topic,\n                          source_kind,db.utcnow())")

# Human Hungarian copy, fallback works even when cloud API is absent.
span('agent/hunter.py','def plain_description(title):','TEXT_MODEL=',
    "def plain_description(title):\n"
    "    return product_copy.fallback(title)\n\n\n")
span('agent/hunter.py',
    "    title = str(product.get('title') or '').strip()[:180]",
    "    try:\n",
    "    prompt = product_copy.cloud_prompt(product)\n")
span('agent/hunter.py',
    "        closing='Hasonló termékekért nézd meg a többi hirdetésemet.'",
    "    except (ValueError,AttributeError,KeyError,IndexError,TypeError)",
    "        return product_copy.clean_ai(text,product)\n")

# Modern product hub, plus direct safe supplier links in selected product detail.
replace('agent/ui_hunter.py',
    'from . import db, hunter, shopping, free_photo_import, cloudflare_photos, auto_stock_photo, condition_copy, stock_photo_gallery',
    'from . import db, hunter, shopping, free_photo_import, cloudflare_photos, auto_stock_photo, condition_copy, stock_photo_gallery, supplier_links, ui_market_radar, market_intelligence')
replace('agent/ui_hunter.py',
    "    st.markdown('[Beszállítói ajánlat ellenőrzése]('+row['url']+')')",
    "    destination,real_link=supplier_links.navigable(row['url'],row['title'],row['merchant'])\n"
    "    st.link_button('Beszállító termékoldala ↗' if real_link else "
    "'Beszállítói termék keresése ↗',destination)\n"
    "    if not real_link:\n"
    "        st.caption('A korábbi Shopping-hivatkozás nem közvetlen termékoldal. '\n"
    "                   'Most normál Google-keresés nyílik, nem üres Shopping-ajánlat.')")
# Old gallery cards also get a safe link, in case this legacy view is reached.
replace('agent/ui_hunter.py',
    "                     st.markdown('[Beszállítói találat]('+row['url']+')')",
    "                     url,real=supplier_links.navigable(row['url'],row['title'],row['merchant'])\n"
    "                     st.link_button('Kereskedő termékoldala ↗' if real else "
    "'Kereskedői keresés ↗',url)")
render=Path('release_src/v165/ui_hunter_render.txt').read_text(encoding='utf-8')
key=ROOT+'agent/ui_hunter.py'
source=files[key].decode('utf-8')
offset=source.find('def render_hunter():')
assert offset>=0,'UI entrypoint missing'
files[key]=(source[:offset]+render).encode('utf-8')

replace('app.py','from agent import updater',
        'from agent import updater\nfrom agent.ui_theme import render_theme, top_bar')
replace('app.py','</style>""", unsafe_allow_html=True)',
        '</style>""", unsafe_allow_html=True)\nrender_theme()\ntop_bar(updater.VERSION)')
replace('app.py','st.title("📦 Resell Agent")','st.title("◈ Resell AI")')

files[ROOT+'UPGRADE_TO_V165.md']=(
    '# v1.6.5 – Top 50 Market Intelligence and Navigation\n\n'
    '- 50 product-specific research targets, curated from public CATEGORY evidence, never fictitious product sales.\n'
    '- Cost-capped live Shopping checks in batches of 5/10/20/50, showing real merchant asking prices.\n'
    '- Independent one-query custom keyword search, without overwriting Top 50 targets.\n'
    '- Direct merchant URLs where available, otherwise clearly labelled stable Google search fallback.\n'
    '- Natural Hungarian resale descriptions, with no invented product condition or included accessories.\n'
    '- New responsive dark theme, better sidebar, top navigation and functioning bottom quick actions.\n'
    '- Data preserved; existing API providers, image drafts, updates and publication safeguards unchanged.\n'
    '- Existing product copies are not silently rewritten; regenerate and approve in Selected products.\n'
    '- Seller prices, availability, actual sales, search volumes and projected profit remain distinct signals.\n'
).encode('utf-8')

out=Path('resell-agent-mvp-v1.6.5.zip')
with ZipFile(out,'w',ZIP_DEFLATED) as z:
    for key,value in files.items():
        if key.startswith(ROOT+'data/') or key.startswith(ROOT+'backups/'):
            raise ValueError('User data must not ship in release')
        z.writestr(key,value)
digest=sha256(out.read_bytes()).hexdigest()
Path(str(out)+'.sha256').write_text(digest+'  '+out.name+'\n',encoding='ascii')
print('Built',out,'SHA256='+digest)
