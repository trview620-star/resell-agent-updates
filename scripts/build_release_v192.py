"""Build the simple seasonal visual product catalogue from known-working v1.8.0."""
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import sys

base=Path(sys.argv[1] if len(sys.argv)>1 else 'resell-agent-mvp-v1.8.0.zip')
checksum=Path(str(base)+'.sha256')
assert checksum.is_file(),'Missing known-working release SHA-256'
assert sha256(base.read_bytes()).hexdigest()==checksum.read_text(encoding='ascii').split()[0],'Previous release checksum mismatch'
root='resell-agent-starter/'
with ZipFile(base) as source:files={x.filename:source.read(x.filename) for x in source.infolist() if not x.is_dir()}

def replace(path,before,after):
    name=root+path;raw=files[name].decode('utf-8')
    if before not in raw:raise RuntimeError(f'Expected text missing in {path}: {before}')
    files[name]=raw.replace(before,after).encode('utf-8')

replace('agent/updater.py',"VERSION = '1.8.0'","VERSION = '1.9.2'")
replace('tests/test_updater.py','1.8.1','1.9.3')
replace('tests/test_upload_update.py',"'1.8.1'","'1.9.3'")
replace('tests/test_upload_update.py',"'1.8.0'","'1.9.2'")
replace('tests/test_upload_update.py',"'v1.8.1'","'v1.9.3'")
files[root+'app.py']=Path('release_src/v192/app.py').read_bytes()
files[root+'agent/ui_trending_catalog.py']=Path('release_src/v192/ui_trending_catalog.py').read_bytes()
files[root+'tests/test_trending_catalog.py']=Path('release_src/v192/test_trending_catalog.py').read_bytes()
files[root+'UPGRADE_TO_V192.md']=('''# v1.9.2 – Seasonal visual product catalogue

- Restores the known-working v1.8.0 app base and replaces the main page with a simple 3-column product preview grid.
- One refresh searches seasonal (including Christmas) or evergreen themes in Google Shopping and accepts offers only from the thirteen approved retailers.
- Cards show real supplier catalogue images, current displayed price, store count, the lowest matching offer, and a prefilled Google Trends link.
- No AI photo generation, listing drafts, queues or extra diagnostic forms are included.
- Existing local database, supplier checks and user files are retained by the in-app updater; none are bundled in this archive.
''').encode()
out=Path('resell-agent-mvp-v1.9.2.zip')
with ZipFile(out,'w',ZIP_DEFLATED) as z:
    for name,content in files.items():
        if name.startswith(root+'data/') or name.startswith(root+'backups/'):raise RuntimeError('Do not include user data in update')
        z.writestr(name,content)
digest=sha256(out.read_bytes()).hexdigest()
Path(str(out)+'.sha256').write_text(digest+'  '+out.name+'\n',encoding='ascii')
print('Built',out,'SHA256='+digest)
