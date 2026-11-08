"""Build the v0.5.7 resale-market lead research update from the published base."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from hashlib import sha256
import sys

base = Path(sys.argv[1] if len(sys.argv) > 1 else 'resell-agent-mvp-v0.5.6.zip')
check = Path(str(base) + '.sha256')
assert check.is_file(), 'Published base checksum is missing'
assert sha256(base.read_bytes()).hexdigest() == check.read_text(encoding='ascii').split()[0], 'Base checksum mismatch'
ROOT = 'resell-agent-starter/'
with ZipFile(base) as z:
    files = {i.filename: z.read(i.filename) for i in z.infolist() if not i.is_dir()}
assert ROOT+'agent/updater.py' in files

def replace(path, before, after):
    key = ROOT + path
    content = files[key].decode('utf-8')
    assert before in content, f'Unexpected base content in {path}'
    files[key] = content.replace(before, after).encode('utf-8')

replace('agent/updater.py', "VERSION = '0.5.6'", "VERSION = '0.5.7'")
replace('tests/test_updater.py', '0.5.7', '0.5.8')
replace('app.py', 'from agent.ui_shopping import render_shopping',
        'from agent.ui_shopping import render_shopping\nfrom agent.ui_resale_search import render_resale_search')
replace('app.py', '"Live shopping search", "Products & photos"',
        '"Live shopping search", "Resale marketplace search", "Products & photos"')
replace('app.py', 'elif page == "Live shopping search":\n    render_shopping()',
        'elif page == "Live shopping search":\n    render_shopping()\n\nelif page == "Resale marketplace search":\n    render_resale_search(products)')
files[ROOT+'agent/resale_search.py'] = Path('release_src/v057/resale_search.py').read_bytes()
files[ROOT+'agent/ui_resale_search.py'] = Path('release_src/v057/ui_resale_search.py').read_bytes()
files[ROOT+'tests/test_resale_search.py'] = Path('release_src/v057/test_resale_search.py').read_bytes()
files[ROOT+'UPGRADE_TO_V057.md'] = (
    '# Resell Agent v0.5.7 — Resale marketplace search\n\n'
    'Adds publicly indexed listing leads across the seven target marketplaces via your existing Serper key.\n\n'
    'All snippet amounts are unverified asking-price clues. Manually verify product, exact variant, condition and price before saving.\n'
    'The app does not automatically infer verified completed sales. Enter those with evidence in Product research lab.\n'
    'Queries share the 200-search monthly app budget. The data directory remains untouched.\n'
).encode('utf-8')
archive = Path('resell-agent-mvp-v0.5.7.zip')
with ZipFile(archive, 'w', ZIP_DEFLATED) as z:
    for name, content in files.items():
        if name.startswith(ROOT + 'data/'):
            raise RuntimeError('Private data must not be in the release')
        z.writestr(name, content)
digest = sha256(archive.read_bytes()).hexdigest()
Path(str(archive) + '.sha256').write_text(f'{digest}  {archive.name}\n', encoding='ascii')
print('Built', archive.name, digest)
