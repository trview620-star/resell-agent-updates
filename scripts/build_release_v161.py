"""Add automatic stock-photo transformation to the published v1.6.0 workspace."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from hashlib import sha256
import sys

base=Path(sys.argv[1] if len(sys.argv)>1 else 'resell-agent-mvp-v1.6.0.zip')
check=Path(str(base)+'.sha256')
assert check.is_file(),'Published base checksum missing'
assert sha256(base.read_bytes()).hexdigest()==check.read_text(encoding='ascii').split()[0], 'Base release hash mismatch'

ROOT='resell-agent-starter/'
with ZipFile(base) as z:
    files={item.filename:z.read(item.filename) for item in z.infolist() if not item.is_dir()}
def replace(path,old,new):
    key=ROOT+path
    raw=files[key].decode('utf-8')
    if old not in raw:raise RuntimeError('Base changed: '+path+' missing '+old[:95])
    files[key]=raw.replace(old,new).encode('utf-8')
replace('agent/updater.py',"VERSION = '1.6.0'","VERSION = '1.6.1'")
replace('tests/test_updater.py','1.6.1','1.6.2')
for module in ('hunter','ui_hunter','auto_stock_photo'):
    files[ROOT+'agent/'+module+'.py']=Path('release_src/v161/'+module+'.py').read_bytes()
files[ROOT+'tests/test_auto_stock_photo.py']=Path('release_src/v161/test_auto_stock_photo.py').read_bytes()
files[ROOT+'UPGRADE_TO_V161.md']=(
    '# Resell Agent v1.6.1 — automatically transform supplier catalog photos\n\n'
    'Product selection now automatically fetches the available catalog thumbnail '
    'from Serper Shopping search results and sends it as a reference to Cloudflare '
    'FLUX.2 Klein to produce ONE natural home-style AI illustration. '
    'No user photo upload is needed; select the item and the application handles '
    'source download, compression, API call, image staging, preview and approval. '
    'The downloaded reference source is a catalog picture, not a verified authentic '
    'photo from the seller or a license grant. AI changes must preserve exact '
    'visible item details; missing thumbnails never produce fictitious matching images. '
    'Images remain in local ai_pending until approval, then under data/ai_previews. '
    'Original search images are not copied to authentic product photo records.\n\n'
    'Re-running preparation does NOT consume extra Cloudflare image calls unless '
    'the user explicitly clicks regenerate. No image is published automatically '
    'and no third-party rights are assumed. Where source photo usage rights '
    'have not been established, marketplace publication remains blocked pending '
    'legitimate supplier or seller media permissions. Other seven-marketplace '
    'publishing limitations remain unchanged. No secret keys included in files.\n'
).encode('utf-8')

out=Path('resell-agent-mvp-v1.6.1.zip')
with ZipFile(out,'w',ZIP_DEFLATED) as z:
    for key,value in files.items():
        if key.startswith(ROOT+'data/') or key.startswith(ROOT+'backups/'):
            raise ValueError('Refusing to include user data')
        z.writestr(key,value)
digest=sha256(out.read_bytes()).hexdigest()
Path(str(out)+'.sha256').write_text(digest+'  '+out.name+'\n',encoding='ascii')
print('Built '+str(out)+' SHA256='+digest)
