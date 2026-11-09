"""Build v1.9.3 from the released v1.9.2 product grid, retaining user data."""
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import sys

base=Path(sys.argv[1] if len(sys.argv)>1 else 'resell-agent-mvp-v1.9.2.zip')
checksum=Path(str(base)+'.sha256')
assert checksum.is_file(), 'Missing v1.9.2 checksum'
assert sha256(base.read_bytes()).hexdigest()==checksum.read_text(encoding='ascii').split()[0], 'v1.9.2 checksum mismatch'
root='resell-agent-starter/'
with ZipFile(base) as source:
    files={x.filename:source.read(x.filename) for x in source.infolist() if not x.is_dir()}

def replace(path,before,after):
    name=root+path
    raw=files[name].decode('utf-8')
    if before not in raw: raise RuntimeError(f'Expected text missing in {path}: {before}')
    files[name]=raw.replace(before,after).encode('utf-8')

replace('agent/updater.py', "VERSION = '1.9.2'", "VERSION = '1.9.3'")
replace('tests/test_updater.py', '1.9.3', '1.9.4')
replace('tests/test_upload_update.py', "'1.9.3'", "'1.9.4'")
replace('tests/test_upload_update.py', "'1.9.2'", "'1.9.3'")
replace('tests/test_upload_update.py', "'v1.9.3'", "'v1.9.4'")
files[root+'app.py']=Path('release_src/v192/app.py').read_bytes()
files[root+'agent/ui_trending_catalog.py']=Path('release_src/v192/ui_trending_catalog.py').read_bytes()
files[root+'tests/test_trending_catalog.py']=Path('release_src/v192/test_trending_catalog.py').read_bytes()
files[root+'UPGRADE_TO_V193.md']='''# v1.9.3 – API key field fix\n\nKeeps the Serper API key field visible after entry so the key can be reviewed or edited before starting a search. The key stays in the current app session unless configured through SERPER_API_KEY.\n'''.encode('utf-8')
out=Path('resell-agent-mvp-v1.9.3.zip')
with ZipFile(out,'w',ZIP_DEFLATED) as z:
    for name,content in files.items():
        if name.startswith(root+'data/') or name.startswith(root+'backups/'):
            raise RuntimeError('Do not include user data in update')
        z.writestr(name,content)
digest=sha256(out.read_bytes()).hexdigest()
Path(str(out)+'.sha256').write_text(digest+'  '+out.name+'\n',encoding='ascii')
print('Built',out,'SHA256='+digest)
