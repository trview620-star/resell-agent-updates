"""Build verified v1.4.0 Cloudflare AI photo generation integration."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from hashlib import sha256
import sys

base=Path(sys.argv[1] if len(sys.argv)>1 else 'resell-agent-mvp-v1.3.0.zip')
check=Path(str(base)+'.sha256')
assert check.is_file(), 'Published base checksum missing'
assert sha256(base.read_bytes()).hexdigest()==check.read_text(encoding='ascii').split()[0], 'Base ZIP checksum mismatch'
ROOT='resell-agent-starter/'
with ZipFile(base) as archive:
    files={i.filename:archive.read(i.filename) for i in archive.infolist() if not i.is_dir()}

def replace(path,old,new):
    key=ROOT+path
    content=files[key].decode('utf-8')
    if old not in content:
        raise RuntimeError(f'Base changed: {path} missing {old[:80]}')
    files[key]=content.replace(old,new).encode('utf-8')

replace('agent/updater.py',"VERSION = '1.3.0'","VERSION = '1.4.0'")
replace('tests/test_updater.py','1.3.1','1.4.1')
replace('agent/ui_command_center.py',
    'from .ui_free_photo_import import render_free_photo_import_page',
    'from .ui_free_photo_import import render_free_photo_import_page\nfrom .ui_cloudflare_photos import render_cloudflare_photo_page')
replace('agent/ui_command_center.py',
    "'Free AI Photos','Listing publisher'",
    "'Cloudflare AI Photos','Free AI Photos','Listing publisher'")
replace('agent/ui_command_center.py',
    '''    with tabs[2]:
        render_free_photo_import_page(products)
        with st.expander('Optional paid API image generator'):
            render_ai_photo_page(products)
    with tabs[3]:_publish(products)
    with tabs[4]:_operations(products)''',
    '''    with tabs[2]:render_cloudflare_photo_page(products)
    with tabs[3]:
        render_free_photo_import_page(products)
        with st.expander('Optional paid OpenAI API image generator'):
            render_ai_photo_page(products)
    with tabs[4]:_publish(products)
    with tabs[5]:_operations(products)''')

for mod in ('cloudflare_photos','ui_cloudflare_photos'):
    files[ROOT+'agent/'+mod+'.py']=Path('release_src/v140/'+mod+'.py').read_bytes()
files[ROOT+'tests/test_cloudflare_photos.py']=Path('release_src/v140/test_cloudflare_photos.py').read_bytes()
files[ROOT+'UPGRADE_TO_V140.md']=b'''# Resell Agent v1.4.0 - Cloudflare AI Photos

Fully automated photo generation inside the local dashboard without running GPU inference
on the local machine. Go to Command Center -> Cloudflare AI Photos.
Enter your Cloudflare account ID and a Workers AI API token in the local UI,
select the included FLUX.2 Klein 4B model by default or optional 9B quality model,
then click Generate 4 photos. The app sends the actual reference image resized to
480x480 or smaller with instructions for four separate photographic angles.
Review each generated PNG separately; approve or regenerate individual results
with written feedback. Save approved files into data/ai_previews/<product_id>
or download as individual PNGs/ZIP. Originals never overwritten.
The token is only kept in the Streamlit session, not written to the database or
published to GitHub. Cloudflare Free includes a daily AI quota but does not
guarantee unlimited free image generations; 9B may use more quota.
If generation fails, the app shows an actionable provider error without logging
the token. Direct publishing and purchases remain disabled/unconfigured.
Cloudflare generated images are illustrative, especially unseen sides and rear.
Never use AI images as evidence of actual product condition.
The existing no-API ChatGPT import remains available in another tab.
'''
out=Path('resell-agent-mvp-v1.4.0.zip')
with ZipFile(out,'w',ZIP_DEFLATED) as archive:
    for name,content in files.items():
        if name.startswith(ROOT+'data/') or name.startswith(ROOT+'backups/'):
            raise ValueError('Private user files should not be packaged')
        archive.writestr(name,content)
digest=sha256(out.read_bytes()).hexdigest()
Path(str(out)+'.sha256').write_text(digest+'  '+out.name+'\n',encoding='ascii')
print('Built '+out.name+' sha256 '+digest)
