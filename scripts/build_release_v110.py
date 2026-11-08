"""Build offline, reversible marketplace photo mode from published v1.0.0."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from hashlib import sha256
import sys

base=Path(sys.argv[1] if len(sys.argv)>1 else 'resell-agent-mvp-v1.0.0.zip')
check=Path(str(base)+'.sha256')
assert check.is_file(), 'Missing v1.0.0 checksum'
assert sha256(base.read_bytes()).hexdigest()==check.read_text(encoding='ascii').split()[0], 'Base ZIP checksum failed'
ROOT='resell-agent-starter/'
with ZipFile(base) as archive:
    files={f.filename:archive.read(f.filename) for f in archive.infolist() if not f.is_dir()}

def replace(path,before,after):
    key=ROOT+path
    content=files[key].decode('utf-8')
    if before not in content:
        raise RuntimeError(f'Unexpected base code in {path}: {before[:90]}')
    files[key]=content.replace(before,after).encode('utf-8')

replace('agent/updater.py',"VERSION = '1.0.0'","VERSION = '1.1.0'")
replace('tests/test_updater.py','1.0.1','1.1.1')
replace('agent/ui_command_center.py',
    'from .backup import make_backup',
    'from .backup import make_backup\nfrom .ui_marketplace_photo import render_photo_mode')
replace('agent/ui_command_center.py',
    "    else:st.info('Upload an original photo from Add product.')",
    "    else:st.info('Upload an original photo from Add product.')\n    if photos: render_photo_mode(photo)")
for module in ('marketplace_photo','ui_marketplace_photo'):
    files[ROOT+'agent/'+module+'.py']=Path('release_src/v110/'+module+'.py').read_bytes()
files[ROOT+'tests/test_marketplace_photo.py']=Path('release_src/v110/test_marketplace_photo.py').read_bytes()
requirements=files[ROOT+'requirements.txt'].decode('utf-8')
if 'numpy' not in requirements.lower():
    files[ROOT+'requirements.txt']=(requirements.rstrip()+'\nnumpy>=1.26,<3\n').encode('utf-8')
files[ROOT+'UPGRADE_TO_V110.md']=b'''# Resell Agent v1.1.0 - Marketplace Photo Mode

New section: Command Center -> Photo + AI -> Marketplace Photo Mode.
Local workflow: Natural camera finish (subtle light/color/grain) or Room background composite
(requires user-provided real background and a clean white/transparent source image).
Preview, adjust placement/blur, download full-resolution JPG, or save a separate variant.
The original uploaded photo is never overwritten. No AI credits or cloud images required.
Photo mode does not generate new items or invent missing product details.
Note: It is a local photo composite, not generative inpainting. Results on complex stock
photos can still look edited. Check the preview carefully. Composite should never be
presented as proof of actual ownership, condition, or where the product was photographed.

Other features are preserved. Marketplace account automation remains disabled/unconfigured.
'''
result=Path('resell-agent-mvp-v1.1.0.zip')
with ZipFile(result,'w',ZIP_DEFLATED) as z:
    for filename,content in files.items():
        if filename.startswith(ROOT+'data/') or filename.startswith(ROOT+'backups/'):
            raise ValueError('Private user data in package')
        z.writestr(filename,content)
digest=sha256(result.read_bytes()).hexdigest()
Path(str(result)+'.sha256').write_text(digest+'  '+result.name+'\n',encoding='ascii')
print('Built '+result.name+' '+digest)
