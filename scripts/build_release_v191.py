"""Build v1.9.1 with one-click multi-source market diagnostics."""
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import sys

base=Path(sys.argv[1] if len(sys.argv)>1 else 'resell-agent-mvp-v1.9.0.zip')
checksum=Path(str(base)+'.sha256')
assert checksum.is_file(),'Missing previous release SHA-256'
assert sha256(base.read_bytes()).hexdigest()==checksum.read_text(encoding='ascii').split()[0],'Previous release checksum mismatch'
root='resell-agent-starter/'
with ZipFile(base) as source:files={x.filename:source.read(x.filename) for x in source.infolist() if not x.is_dir()}

def replace(path,before,after):
    name=root+path;raw=files[name].decode('utf-8')
    if before not in raw:raise RuntimeError(f'Expected text missing in {path}: {before}')
    files[name]=raw.replace(before,after).encode('utf-8')

replace('agent/updater.py',"VERSION = '1.9.0'","VERSION = '1.9.1'")
replace('tests/test_updater.py','1.9.1','1.9.2')
replace('tests/test_upload_update.py',"'1.9.1'","'1.9.2'")
replace('tests/test_upload_update.py',"'1.9.0'","'1.9.1'")
replace('tests/test_upload_update.py',"'v1.9.1'","'v1.9.2'")
files[root+'agent/demand_workbench.py']=Path('release_src/v180/demand_workbench.py').read_bytes()
files[root+'tests/test_demand_workbench.py']=Path('release_src/v180/test_demand_workbench.py').read_bytes()
files[root+'agent/product_studio.py']=Path('release_src/v190/product_studio.py').read_bytes()
files[root+'agent/ui_product_studio.py']=Path('release_src/v190/ui_product_studio.py').read_bytes()
files[root+'tests/test_product_studio.py']=Path('release_src/v190/test_product_studio.py').read_bytes()
files[root+'UPGRADE_TO_V191.md']=('''# v1.9.1 – Automatic multi-source diagnostics

- A product search no longer requires manually typed eBay sales counts; those remain optional and must be confirmed if entered.
- One search action queries the 13 approved suppliers plus Google-indexed results for Google Trends, Vinted, Jófogás and eBay Sold.
- The interface labels indexed snippets accurately: they are not complete active-listing counts, official Trends indices, or proof of completed sales.
- Google Trends chart is prefilled for the current product. Google Shopping supplier matches and previous verified supplier-price checks remain separate.
- Existing eBay evidence and verified supplier checks are preserved when migrating the local database to optional sales fields.
- Existing data and user files are excluded from the update archive.
''').encode()
out=Path('resell-agent-mvp-v1.9.1.zip')
with ZipFile(out,'w',ZIP_DEFLATED) as z:
    for name,content in files.items():
        if name.startswith(root+'data/') or name.startswith(root+'backups/'):raise RuntimeError('Do not include user data in release')
        z.writestr(name,content)
digest=sha256(out.read_bytes()).hexdigest()
Path(str(out)+'.sha256').write_text(digest+'  '+out.name+'\n',encoding='ascii')
print('Built',out,'SHA256='+digest)
