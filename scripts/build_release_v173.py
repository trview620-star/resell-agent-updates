"""Build v1.7.3 manual Vinted listing preparation from verified v1.7.2."""
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import sys

base=Path(sys.argv[1] if len(sys.argv)>1 else 'resell-agent-mvp-v1.7.2.zip')
checksum=Path(str(base)+'.sha256')
assert checksum.is_file(),'Missing previous release SHA-256'
assert sha256(base.read_bytes()).hexdigest()==checksum.read_text(encoding='ascii').split()[0], 'Previous release checksum mismatch'
root='resell-agent-starter/'
with ZipFile(base) as source:
    files={x.filename:source.read(x.filename) for x in source.infolist() if not x.is_dir()}

def replace(path,before,after):
    name=root+path
    raw=files[name].decode('utf-8')
    if before not in raw: raise RuntimeError('Expected text missing in '+path)
    files[name]=raw.replace(before,after).encode('utf-8')

replace('agent/updater.py',"VERSION = '1.7.2'","VERSION = '1.7.3'")
replace('tests/test_updater.py','1.7.3','1.7.4')
replace('tests/test_upload_update.py',"'1.7.3'","'1.7.4'")
replace('tests/test_upload_update.py',"'1.7.2'","'1.7.3'")
replace('tests/test_upload_update.py',"'v1.7.3'","'v1.7.4'")
for module in ('private_research','ui_private_dashboard'):
    files[root+'agent/'+module+'.py']=Path('release_src/v173/'+module+'.py').read_bytes()
files[root+'agent/vinted_upload.py']=Path('release_src/v173/vinted_upload.py').read_bytes()
files[root+'tests/test_private_dashboard.py']=Path('release_src/v173/test_private_dashboard.py').read_bytes()
files[root+'tests/test_vinted_upload.py']=Path('release_src/v173/test_vinted_upload.py').read_bytes()
files[root+'UPGRADE_TO_V173.md']=(
    '# v1.7.3 – Fast manual Vinted preparation\n\n'
    '- Adds a focused local Vinted helper for personal used-item drafts.\n'
    '- Shows copy-ready title, description and price, original-photo preview and a downloadable upload bundle.\n'
    '- Opens the Vinted new-listing page; the user selects category/condition and confirms publication manually.\n'
    '- No login automation, private API calls, or unattended publishing.\n'
).encode('utf-8')

out=Path('resell-agent-mvp-v1.7.3.zip')
with ZipFile(out,'w',ZIP_DEFLATED) as output:
    for name,content in files.items():
        if name.startswith(root+'data/') or name.startswith(root+'backups/'):
            raise RuntimeError('Do not include user data in update')
        output.writestr(name,content)
digest=sha256(out.read_bytes()).hexdigest()
Path(str(out)+'.sha256').write_text(digest+'  '+out.name+'\n',encoding='ascii')
print('Built',out,'SHA256='+digest)
