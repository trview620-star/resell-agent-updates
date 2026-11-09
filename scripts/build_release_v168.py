"""Resell Agent v1.6.8 - source preview replacement and loading fixes."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from hashlib import sha256
import sys
base=Path(sys.argv[1] if len(sys.argv)>1 else 'resell-agent-mvp-v1.6.7.zip')
check=Path(str(base)+'.sha256')
assert check.is_file(),'Missing release checksum'
assert sha256(base.read_bytes()).hexdigest()==check.read_text(encoding='ascii').split()[0], 'Source checksum mismatch'
ROOT='resell-agent-starter/'
with ZipFile(base) as z:
    files={i.filename:z.read(i.filename) for i in z.infolist() if not i.is_dir()}

def replace(path,a,b):
    name=ROOT+path
    old=files[name].decode('utf-8')
    if a not in old:raise RuntimeError('Version drift: '+path+': '+repr(a[:105]))
    files[name]=old.replace(a,b).encode('utf-8')

replace('agent/updater.py',"VERSION = '1.6.7'","VERSION = '1.6.8'")
replace('tests/test_updater.py','1.6.8','1.6.9')
replace('tests/test_upload_update.py',"'1.6.8'","'1.6.9'")
replace('tests/test_upload_update.py',"'1.6.7'","'1.6.8'")
replace('tests/test_upload_update.py',"'v1.6.8'","'v1.6.9'")

files[ROOT+'agent/source_photo_series.py']=Path('release_src/v168/source_photo_series.py').read_bytes()
files[ROOT+'agent/ui_faithful_photos.py']=Path('release_src/v168/ui_faithful_photos.py').read_bytes()
files[ROOT+'tests/test_source_photo_series.py']=Path('release_src/v168/test_source_photo_series.py').read_bytes()

replace('agent/listing_previews.py',
        'for shot in source_photo_series.read(pid):',
        'for shot in source_photo_series.read(pid,limit=max(1,limit-len(out))):')

files[ROOT+'UPGRADE_TO_V168.md']=(
    '# Resell Agent v1.6.8 – original-photo replacement\n\n'
    '- Replace catalog-only photo previews with real uploaded photos after an order arrives.\n'
    '- Regenerate an unapproved first image as well as the optional close-ups.\n'
    '- Do not overwrite approved images; each image remains independently reviewable.\n'
    '- Minimise loading large preview images in product and listing cards.\n'
    '- All previous source-preserving, four-shot, category-sensitive, '
    'Top 50, supplier-link, human-copy and dashboard updater features preserved.\n'
).encode('utf-8')

out=Path('resell-agent-mvp-v1.6.8.zip')
with ZipFile(out,'w',ZIP_DEFLATED) as z:
    for name,data in files.items():
        if name.startswith(ROOT+'data/') or name.startswith(ROOT+'backups/'):
            raise ValueError('User data must never be placed in application release ZIP')
        z.writestr(name,data)
digest=sha256(out.read_bytes()).hexdigest()
Path(str(out)+'.sha256').write_text(digest+'  '+out.name+'\n',encoding='ascii')
print('Built',out,'SHA256='+digest)
