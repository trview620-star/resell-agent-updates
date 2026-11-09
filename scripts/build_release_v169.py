"""Resell Agent v1.6.9 - Top 50 image thumbnail research interface."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from hashlib import sha256
import sys

base=Path(sys.argv[1] if len(sys.argv)>1 else 'resell-agent-mvp-v1.6.8.zip')
check=Path(str(base)+'.sha256')
assert check.is_file(),'Missing published release checksum'
assert sha256(base.read_bytes()).hexdigest()==check.read_text(encoding='ascii').split()[0], 'Release checksum mismatch'

ROOT='resell-agent-starter/'
with ZipFile(base) as z:
    files={i.filename:z.read(i.filename) for i in z.infolist() if not i.is_dir()}

def replace(path,old,new):
    key=ROOT+path
    source=files[key].decode('utf-8')
    if old not in source:
        raise RuntimeError('Version drift in '+path+': missing '+repr(old[:120]))
    files[key]=source.replace(old,new).encode('utf-8')

replace('agent/updater.py',"VERSION = '1.6.8'","VERSION = '1.6.9'")
replace('tests/test_updater.py','1.6.9','1.6.10')
replace('tests/test_upload_update.py',"'1.6.9'","'1.6.10'")
replace('tests/test_upload_update.py',"'1.6.8'","'1.6.9'")
replace('tests/test_upload_update.py',"'v1.6.9'","'v1.6.10'")

# New photo columns and detail previews use the product images already
# captured by the existing Shopping data source. No external image source,
# new API token or extra billed request is required for existing hits.
for module in ('radar_previews','ui_market_radar','market_intelligence'):
    files[ROOT+'agent/'+module+'.py']=Path('release_src/v169/'+module+'.py').read_bytes()
files[ROOT+'tests/test_radar_previews.py']=Path(
    'release_src/v169/test_radar_previews.py').read_bytes()

files[ROOT+'UPGRADE_TO_V169.md']=(
    '# Resell Agent v1.6.9 – Photo previews in Top 50\n\n'
    '- The Top 50 research table includes a genuine Shopping supplier thumbnail '
    'column, spacious image row heights and a card-view switch.\n'
    '- Click photo-card details to see the selected research candidate, '
    'larger image and up to four different merchant catalogue pictures.\n'
    '- Individual supplier offers also show their original catalogue thumbnail.\n'
    '- Handles Serper Shopping imageUrl, image_url, thumbnailUrl, thumbnail, '
    'image and imageLink field variations while retaining URL validation.\n'
    '- No invented image or model match: previously unchecked candidates '
    'show an honest empty thumbnail until searched.\n'
    '- Existing discovery, saved listings, original and derivative photos, '
    'in-site update workflow, API settings and backups remain intact.\n'
).encode('utf-8')

out=Path('resell-agent-mvp-v1.6.9.zip')
with ZipFile(out,'w',ZIP_DEFLATED) as z:
    for name,data in files.items():
        if name.startswith(ROOT+'data/') or name.startswith(ROOT+'backups/'):
            raise ValueError('Refusing to ship user data in application release')
        z.writestr(name,data)
digest=sha256(out.read_bytes()).hexdigest()
Path(str(out)+'.sha256').write_text(digest+'  '+out.name+'\n',encoding='ascii')
print('Built',out,'SHA256='+digest)
