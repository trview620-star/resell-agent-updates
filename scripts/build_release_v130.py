"""Build v1.3.0 no-extra-cost ChatGPT photo import workflow."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from hashlib import sha256
import sys

base=Path(sys.argv[1] if len(sys.argv)>1 else 'resell-agent-mvp-v1.2.0.zip')
checksum=Path(str(base)+'.sha256')
assert checksum.is_file(), 'Missing published base SHA-256 checksum'
assert sha256(base.read_bytes()).hexdigest()==checksum.read_text(encoding='ascii').split()[0], 'Base ZIP failed checksum'
ROOT='resell-agent-starter/'
with ZipFile(base) as archive:
    files={i.filename:archive.read(i.filename) for i in archive.infolist() if not i.is_dir()}
def replace(path,old,new):
    key=ROOT+path
    content=files[key].decode('utf-8')
    if old not in content:raise RuntimeError(f'Unexpected source in {path}: {old[:90]}')
    files[key]=content.replace(old,new).encode('utf-8')

replace('agent/updater.py',"VERSION = '1.2.0'","VERSION = '1.3.0'")
replace('tests/test_updater.py','1.2.1','1.3.1')
replace('agent/ui_command_center.py',
    'from .ui_ai_listing_photos import render_ai_photo_page',
    'from .ui_ai_listing_photos import render_ai_photo_page\nfrom .ui_free_photo_import import render_free_photo_import_page')
replace('agent/ui_command_center.py',
    "'AI Listing Photos','Listing publisher'",
    "'Free AI Photos','Listing publisher'")
replace('agent/ui_command_center.py',
    '    with tabs[2]:render_ai_photo_page(products)',
    "    with tabs[2]:\n        render_free_photo_import_page(products)\n        with st.expander('Optional paid API image generator'):\n            render_ai_photo_page(products)")

for mod in ('free_photo_import','ui_free_photo_import'):
    files[ROOT+'agent/'+mod+'.py']=Path('release_src/v130/'+mod+'.py').read_bytes()
files[ROOT+'tests/test_free_photo_import.py']=Path('release_src/v130/test_free_photo_import.py').read_bytes()
files[ROOT+'UPGRADE_TO_V130.md']=b'''# Resell Agent v1.3.0 - Free ChatGPT image import

No separate image-generation API key is needed to import and organize ChatGPT image outputs.
Use ChatGPT Images to generate four separate views within your ChatGPT usage limits,
then download those images and import them all at once as individual PNG/JPG/WEBP
files or a ZIP. In Resell Agent > Command Center > Free AI Photos, preview,
approve/reject, download or save approved full-resolution pictures to
data/ai_previews/<product_id>. Revisit saved photos later.

Important: ChatGPT image generation cannot be called for free programmatically
from this local third-party app. It is a manual transfer. The old optional paid
API workflow remains under a collapsed Advanced section.

Generated views are illustrative. Never replace true photos documenting the actual
item, unseen defects or included accessories. No images are automatically published.
The original product-photo records and local user data are not altered.
'''
out=Path('resell-agent-mvp-v1.3.0.zip')
with ZipFile(out,'w',ZIP_DEFLATED) as z:
    for name,content in files.items():
        if name.startswith(ROOT+'data/') or name.startswith(ROOT+'backups/'):
            raise RuntimeError('Refusing to ship private user files')
        z.writestr(name,content)
digest=sha256(out.read_bytes()).hexdigest()
Path(str(out)+'.sha256').write_text(digest+'  '+out.name+'\n',encoding='ascii')
print('Built '+out.name+' sha256='+digest)
