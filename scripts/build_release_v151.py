"""Build simple Christmas product page patch from published v1.5.0."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from hashlib import sha256
import sys

base=Path(sys.argv[1] if len(sys.argv)>1 else 'resell-agent-mvp-v1.5.0.zip')
checksum=Path(str(base)+'.sha256')
assert checksum.is_file(),'Published base release checksum missing'
assert sha256(base.read_bytes()).hexdigest()==checksum.read_text(encoding='ascii').split()[0], 'Base ZIP does not match published checksum'
ROOT='resell-agent-starter/'
with ZipFile(base) as z:
    files={f.filename:z.read(f.filename) for f in z.infolist() if not f.is_dir()}

def replace(path,old,new):
    key=ROOT+path
    content=files[key].decode('utf-8')
    if old not in content:
        raise RuntimeError('Unexpected source in '+path+' missing '+old[:80])
    files[key]=content.replace(old,new).encode('utf-8')

replace('agent/updater.py',"VERSION = '1.5.0'","VERSION = '1.5.1'")
replace('tests/test_updater.py','1.5.1','1.5.2')
replace('agent/ui_command_center.py',"'Christmas Pilot'])","'Karácsony'])")

files[ROOT+'agent/christmas_trial.py']=Path('release_src/v151/christmas_trial.py').read_bytes()
files[ROOT+'agent/ui_christmas_trial.py']=Path('release_src/v151/ui_christmas_trial.py').read_bytes()
files[ROOT+'tests/test_christmas_trial.py']=Path('release_src/v151/test_christmas_trial.py').read_bytes()

files[ROOT+'UPGRADE_TO_V151.md']=(
    '# Resell Agent v1.5.1 — Letisztult karácsonyi próbahirdetés\n\n'
    'One product, one picture, one naturally worded Hungarian advert. '
    'Single generate button, editable title/description, one approval/save action. '
    'Technical source facts and token inputs are hidden under expandable settings. '
    'No SKU, supplier warnings, AI disclosures or API jargon are placed in the '
    'buyer-facing description. All necessary warnings remain visible in seller UI. '
    'Optional product photo upload guides Cloudflare to preserve the exact product '
    'better and generate natural home surroundings. With no uploaded reference, '
    'the generated image is clearly an illustrative concept, not an authentic item photo. '
    'No real-world publishing, order placement or stock claims. All local user data '
    'is preserved by the release updater.\n'
).encode('utf-8')

out=Path('resell-agent-mvp-v1.5.1.zip')
with ZipFile(out,'w',ZIP_DEFLATED) as z:
    for name,content in files.items():
        if name.startswith(ROOT+'data/') or name.startswith(ROOT+'backups/'):
            raise ValueError('Do not package user data')
        z.writestr(name,content)
digest=sha256(out.read_bytes()).hexdigest()
Path(str(out)+'.sha256').write_text(digest+'  '+out.name+'\n',encoding='ascii')
print('Built '+out.name+' sha256 '+digest)
