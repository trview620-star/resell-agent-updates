"""Release v1.7.1: private dashboard with correct draft prices."""
from pathlib import Path
from hashlib import sha256
from zipfile import ZipFile,ZIP_DEFLATED
import sys

base=Path(sys.argv[1] if len(sys.argv)>1 else 'resell-agent-mvp-v1.7.0.zip')
checksum=Path(str(base)+'.sha256')
assert checksum.is_file(),'Missing previous release SHA-256'
assert sha256(base.read_bytes()).hexdigest()==checksum.read_text(encoding='ascii').split()[0], 'Previous release checksum mismatch'
ROOT='resell-agent-starter/'
with ZipFile(base) as source:
    files={x.filename:source.read(x.filename) for x in source.infolist() if not x.is_dir()}

def replace(path,before,after):
    name=ROOT+path
    raw=files[name].decode('utf-8')
    if before not in raw:
        raise RuntimeError('Expected text missing in '+path+': '+repr(before[:105]))
    files[name]=raw.replace(before,after).encode('utf-8')

replace('agent/updater.py',"VERSION = '1.7.0'","VERSION = '1.7.1'")
replace('tests/test_updater.py','1.7.1','1.7.2')
replace('tests/test_upload_update.py',"'1.7.1'","'1.7.2'")
replace('tests/test_upload_update.py',"'1.7.0'","'1.7.1'")
replace('tests/test_upload_update.py',"'v1.7.1'","'v1.7.2'")

for module in ('private_research','ui_private_dashboard'):
    files[ROOT+'agent/'+module+'.py']=Path('release_src/v171/'+module+'.py').read_bytes()
files[ROOT+'tests/test_private_dashboard.py']=Path(
    'release_src/v171/test_private_dashboard.py').read_bytes()

files[ROOT+'UPGRADE_TO_V171.md']=(
    '# v1.7.1 – Fixed profit also applied to drafts\n\n'
    '- The private dark dashboard now writes the confirmed supplier+costs+4,000 Ft '
    'selling price into any newly prepared, still unpriced Vinted/Jófogás draft.\n'
    '- Existing manually priced or published listings are never silently overwritten.\n'
    '- Missing cost evidence leaves the draft price unverified instead of inventing zero shipping.\n'
    '- All 13 supplier filters, exact-postcode delivery evidence and prior photo, '
    'backup, pricing diagnostics and update workflows remain available.\n'
).encode('utf-8')

out=Path('resell-agent-mvp-v1.7.1.zip')
with ZipFile(out,'w',ZIP_DEFLATED) as output:
    for name,content in files.items():
        if name.startswith(ROOT+'data/') or name.startswith(ROOT+'backups/'):
            raise RuntimeError('Do not include user data in an update')
        output.writestr(name,content)
digest=sha256(out.read_bytes()).hexdigest()
Path(str(out)+'.sha256').write_text(digest+'  '+out.name+'\n',encoding='ascii')
print('Built',out,'SHA256='+digest)
