"""Build the demand-led visual catalogue and post studio from v1.8.0."""
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import sys

base=Path(sys.argv[1] if len(sys.argv)>1 else 'resell-agent-mvp-v1.8.0.zip')
checksum=Path(str(base)+'.sha256')
assert checksum.is_file(),'Missing previous release SHA-256'
assert sha256(base.read_bytes()).hexdigest()==checksum.read_text(encoding='ascii').split()[0],'Previous release checksum mismatch'
root='resell-agent-starter/'
with ZipFile(base) as source:files={x.filename:source.read(x.filename) for x in source.infolist() if not x.is_dir()}

def replace(path,before,after):
    key=root+path;text=files[key].decode('utf-8')
    if before not in text:raise RuntimeError(f'Expected text missing in {path}: {before}')
    files[key]=text.replace(before,after).encode('utf-8')

replace('agent/updater.py',"VERSION = '1.8.0'","VERSION = '1.9.0'")
replace('tests/test_updater.py','1.8.1','1.9.1')
replace('tests/test_upload_update.py',"'1.8.1'","'1.9.1'")
replace('tests/test_upload_update.py',"'1.8.0'","'1.9.0'")
replace('tests/test_upload_update.py',"'v1.8.1'","'v1.9.1'")
files[root+'app.py']=Path('release_src/v190/app.py').read_bytes()
files[root+'agent/product_studio.py']=Path('release_src/v190/product_studio.py').read_bytes()
files[root+'agent/ui_product_studio.py']=Path('release_src/v190/ui_product_studio.py').read_bytes()
files[root+'tests/test_product_studio.py']=Path('release_src/v190/test_product_studio.py').read_bytes()
files[root+'UPGRADE_TO_V190.md']=('''# v1.9.0 – Product Studio

- Turns verified eBay Sold observations into image-led supplier cards from the 13 approved stores.
- Saves a selected posting queue ordered by actual entered eBay sales pace.
- Adds editable Hungarian listing copy, manually observed Vinted reference prices, and the established +4,900 HUF minimum price floor over checked landed supplier cost.
- Generates four separate Cloudflare AI illustrative images from the supplier catalogue image after an explicit user action; keeps the supplier image identified as stock and generated images identified as AI illustrations.
- Exports a numbered ZIP posting pack. Marketplace publication remains manual.
- Preserves the local database and existing user records. eBay sold counts and supplier availability are never fabricated.
''').encode()
out=Path('resell-agent-mvp-v1.9.0.zip')
with ZipFile(out,'w',ZIP_DEFLATED) as z:
    for name,content in files.items():
        if name.startswith(root+'data/') or name.startswith(root+'backups/'):raise RuntimeError('Do not include user data in release')
        z.writestr(name,content)
digest=sha256(out.read_bytes()).hexdigest()
Path(str(out)+'.sha256').write_text(digest+'  '+out.name+'\n',encoding='ascii')
print('Built',out,'SHA256='+digest)
