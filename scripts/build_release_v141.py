"""Build v1.4.1 diagnostic release from the verified published v1.4.0."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from hashlib import sha256
import sys

base=Path(sys.argv[1] if len(sys.argv)>1 else 'resell-agent-mvp-v1.4.0.zip')
checksum=Path(str(base)+'.sha256')
assert checksum.is_file(), 'Published base checksum missing'
assert sha256(base.read_bytes()).hexdigest()==checksum.read_text(encoding='ascii').split()[0], 'Base ZIP checksum mismatch'
ROOT='resell-agent-starter/'
with ZipFile(base) as archive:
    files={f.filename:archive.read(f.filename) for f in archive.infolist() if not f.is_dir()}

def replace(path,old,new):
    key=ROOT+path
    content=files[key].decode('utf-8')
    if old not in content:raise RuntimeError('Unexpected source for '+path)
    files[key]=content.replace(old,new).encode('utf-8')

replace('agent/updater.py',"VERSION = '1.4.0'","VERSION = '1.4.1'")
replace('tests/test_updater.py','1.4.1','1.4.2')
files[ROOT+'agent/cloudflare_photos.py']=Path('release_src/v141/cloudflare_photos.py').read_bytes()
files[ROOT+'tests/test_cloudflare_diagnostics.py']=Path('release_src/v141/test_cloudflare_diagnostics.py').read_bytes()
files[ROOT+'UPGRADE_TO_V141.md']=b'''# v1.4.1 - Cloudflare HTTP 400 diagnostics

This update helps diagnose why Cloudflare rejects image editing requests.
It displays Cloudflare structured validation code and sanitized message for HTTP 400.
The actual issue may be invalid multipart fields, image constraints, unavailable model,
or account setup. No live API call or credential was used in prepublication tests.
The message is redacted to avoid exposing API keys or account IDs.
Credentials remain stored only in Streamlit session memory and are not in GitHub releases.
No changes to original photos or other product data.
'''
out=Path('resell-agent-mvp-v1.4.1.zip')
with ZipFile(out,'w',ZIP_DEFLATED) as archive:
    for name,content in files.items():
        if name.startswith(ROOT+'data/') or name.startswith(ROOT+'backups/'):
            raise ValueError('Refusing to package user data')
        archive.writestr(name,content)
digest=sha256(out.read_bytes()).hexdigest()
Path(str(out)+'.sha256').write_text(digest+'  '+out.name+'\n',encoding='ascii')
print(out,digest)
