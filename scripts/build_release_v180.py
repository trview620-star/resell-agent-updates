"""Build the v1.8.0 demand-led discovery workspace from v1.7.3."""
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import sys

base=Path(sys.argv[1] if len(sys.argv)>1 else 'resell-agent-mvp-v1.7.3.zip')
checksum=Path(str(base)+'.sha256')
assert checksum.is_file(),'Missing previous release SHA-256'
assert sha256(base.read_bytes()).hexdigest()==checksum.read_text(encoding='ascii').split()[0], 'Previous release checksum mismatch'
root='resell-agent-starter/'
with ZipFile(base) as source:
    files={x.filename:source.read(x.filename) for x in source.infolist() if not x.is_dir()}

def replace(path,before,after):
    name=root+path
    raw=files[name].decode('utf-8')
    if before not in raw:raise RuntimeError('Expected text missing in '+path+': '+before)
    files[name]=raw.replace(before,after).encode('utf-8')

replace('agent/updater.py',"VERSION = '1.7.3'","VERSION = '1.8.0'")
replace('tests/test_updater.py','1.7.4','1.8.1')
replace('tests/test_upload_update.py',"'1.7.4'","'1.8.1'")
replace('tests/test_upload_update.py',"'1.7.3'","'1.8.0'")
replace('tests/test_upload_update.py',"'v1.7.4'","'v1.8.1'")

files[root+'app.py']=Path('release_src/v180/app.py').read_bytes()
files[root+'agent/demand_workbench.py']=Path('release_src/v180/demand_workbench.py').read_bytes()
files[root+'agent/ui_demand_workbench.py']=Path('release_src/v180/ui_demand_workbench.py').read_bytes()
files[root+'tests/test_demand_workbench.py']=Path('release_src/v180/test_demand_workbench.py').read_bytes()
files[root+'UPGRADE_TO_V180.md']=(
    '# v1.8.0 – Demand-first product discovery\n\n'
    '- Replaces the multi-page home workflow with a demand radar and updater access.\n'
    '- Records manually verified eBay Sold evidence, then searches the 13 approved suppliers through the configured Shopping API.\n'
    '- Shows supplier images and match confidence; availability and four-day delivery only qualify after exact product, stock, postcode and explicit delivery promise are verified.\n'
    '- Retains the existing database and files. eBay sold counts are not fabricated or scraped.\n'
).encode('utf-8')

out=Path('resell-agent-mvp-v1.8.0.zip')
with ZipFile(out,'w',ZIP_DEFLATED) as output:
    for name,content in files.items():
        if name.startswith(root+'data/') or name.startswith(root+'backups/'):
            raise RuntimeError('Do not include user data in update')
        output.writestr(name,content)
digest=sha256(out.read_bytes()).hexdigest()
Path(str(out)+'.sha256').write_text(digest+'  '+out.name+'\n',encoding='ascii')
print('Built',out,'SHA256='+digest)
