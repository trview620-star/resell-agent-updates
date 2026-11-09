"""Build the one-product Christmas trial from published, verified v1.4.1."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from hashlib import sha256
import sys

base=Path(sys.argv[1] if len(sys.argv)>1 else 'resell-agent-mvp-v1.4.1.zip')
checksum=Path(str(base)+'.sha256')
assert checksum.is_file(),'Base release checksum missing'
assert sha256(base.read_bytes()).hexdigest()==checksum.read_text(encoding='ascii').split()[0], 'Base ZIP hash mismatch'
ROOT='resell-agent-starter/'
with ZipFile(base) as z:
    files={f.filename:z.read(f.filename) for f in z.infolist() if not f.is_dir()}
def replace(path,old,new):
    key=ROOT+path
    content=files[key].decode('utf-8')
    if old not in content:raise RuntimeError(f'Unexpected base content in {path}: {old[:70]}')
    files[key]=content.replace(old,new).encode('utf-8')

replace('agent/updater.py',"VERSION = '1.4.1'","VERSION = '1.5.0'")
replace('tests/test_updater.py','1.4.2','1.5.1')
replace('agent/ui_command_center.py',
    'from .backup import make_backup',
    'from .backup import make_backup\nfrom .ui_christmas_trial import render_christmas_trial')
replace('agent/ui_command_center.py',
    "'Operations + Events'])",
    "'Operations + Events','Christmas Pilot'])")
replace('agent/ui_command_center.py',
    '    with tabs[5]:_operations(products)',
    '    with tabs[5]:_operations(products)\n    with tabs[6]:render_christmas_trial(products)')

for mod in ('christmas_trial','ui_christmas_trial'):
    files[ROOT+'agent/'+mod+'.py']=Path('release_src/v150/'+mod+'.py').read_bytes()
files[ROOT+'tests/test_christmas_trial.py']=Path('release_src/v150/test_christmas_trial.py').read_bytes()
files[ROOT+'UPGRADE_TO_V150.md']=b'''# Resell Agent v1.5.0 - Christmas one-product pilot

This release adds Command Center -> Christmas Pilot.
A single click runs at most one Serper Google Shopping search for a real, exact-model
MagicHome red Advent wreath 25 cm SKU 8090234 (if Serper key supplied) and one
Cloudflare FLUX.2 Klein image request with text-only prompt. No local GPU required.
If no Serper match, the UI uses an explicitly dated example supplier quote and warns
that actual checkout price and shipping must be reverified. The photo is an
AI illustration, NOT a photo of the exact supplier item. No third-party source
photo is copied.
After review, approve and save ONE candidate and ONE illustrative PNG in the
separate data/ai_previews/product-id folder. The candidate has unknown stock,
an unverified selling price, zero completed-sale evidence and is NOT qualified
for automatic listing. No marketplace publication, ordering or spending occurs.
The pilot never generates repeatedly in the background. No secrets are logged
or included in release ZIP. Cloudflare API tokens remain in session memory.
Retains all prior features and user data.
'''
out=Path('resell-agent-mvp-v1.5.0.zip')
with ZipFile(out,'w',ZIP_DEFLATED) as archive:
    for name,content in files.items():
        if name.startswith(ROOT+'data/') or name.startswith(ROOT+'backups/'):
            raise ValueError('Private user data cannot ship')
        archive.writestr(name,content)
digest=sha256(out.read_bytes()).hexdigest()
Path(str(out)+'.sha256').write_text(digest+'  '+out.name+'\n',encoding='ascii')
print('Built '+out.name+' sha256 '+digest)
