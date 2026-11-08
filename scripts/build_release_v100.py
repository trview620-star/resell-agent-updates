"""Build integrated release from immutable, published v0.5.7 ZIP."""
from __future__ import annotations
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from hashlib import sha256
import sys

base=Path(sys.argv[1] if len(sys.argv)>1 else 'resell-agent-mvp-v0.5.7.zip')
checksum=Path(str(base)+'.sha256')
assert checksum.is_file(),'Published base checksum missing'
assert sha256(base.read_bytes()).hexdigest()==checksum.read_text(encoding='ascii').split()[0], 'Wrong base ZIP'
ROOT='resell-agent-starter/'
with ZipFile(base) as archive:
    files={i.filename:archive.read(i.filename) for i in archive.infolist() if not i.is_dir()}
def replace(path,old,new):
    key=ROOT+path
    text=files[key].decode('utf-8')
    assert old in text, f'Expected base content missing: {path} / {old[:80]}'
    files[key]=text.replace(old,new).encode('utf-8')
replace('agent/updater.py',"VERSION = '0.5.7'","VERSION = '1.0.0'")
replace('tests/test_updater.py','0.5.8','1.0.1')
replace('app.py','from agent.ui_updates import render_updates',
    'from agent.ui_updates import render_updates\nfrom agent.ui_command_center import render_hub')
replace('app.py','["Overview", "Add product"','["Command Center", "Overview", "Add product"')
replace('app.py','if page == "App updates":',
    'if page == "Command Center":\n    render_hub(products)\n\nelif page == "App updates":')
replace('app.py','"""Resell Agent v0.5.4 — local dashboard with verified release updater."""',
    '"""Resell Agent v1.0.0 — integrated local reselling control center."""')
replace('app.py','Shopping search requires an optional SerpApi key. Publishing and purchasing are not automatic.',
    'Live research requires an optional Serper key. The Command Center unifies opportunities, drafts and orders. Live publishing is only available after approved integration setup.')
for module in ('opportunities','event_radar','photo_studio','local_ai','publisher','ui_command_center'):
    files[ROOT+'agent/'+module+'.py']=Path('release_src/v100/'+module+'.py').read_bytes()
files[ROOT+'tests/test_command_center.py']=Path('release_src/v100/test_command_center.py').read_bytes()
files[ROOT+'UPGRADE_TO_V100.md'] = b'''# Resell Agent v1.0.0 - integrated Command Center

This release groups the existing supplier feed finder, Serper Shopping research, resale listing leads,
profit math, original photo enhancement, local Ollama, seven-platform draft exports, event matching,
capacity tracking, order deadlines and backup tools into a single Command Center page.

NEW: Qualified/Needs evidence/Reject opportunity ranking. Qualification requires at least two
recent entered completed-sale comparisons, a recent recorded supplier quote, recorded availability
and projected margin. Verify all recorded evidence; this is not automatic proof of demand.
NEW: Light-only enhanced photos saved separately, originals unchanged.
NEW: One-click seven-marketplace draft packet ZIP. The ZIP contains ready-to-review drafts, not live listings.
NEW: Advanced seller-invoked eBay Inventory API connector with sandbox option; live use requires correct OAuth
permissions, business policies, category aspects and images.
NEW: Open-order shipping deadline and cross-listing conflict alerts.

Still NOT automatic: universal publishing to Vinted, Facebook, Jofogas, Vatera, Hardverapro, Amazon;
automatic detection of all platform sales; supplier purchasing; background cross-market repricing.
API connection accounts and safe end-to-end tests are necessary.

Run through App updates; the updater backs up your data before installing.
'''
archive=Path('resell-agent-mvp-v1.0.0.zip')
with ZipFile(archive,'w',ZIP_DEFLATED) as z:
    for name,content in files.items():
        if name.startswith(ROOT+'data/') or name.startswith(ROOT+'backups/'):
            raise ValueError('Personal data found in distribution')
        z.writestr(name,content)
digest=sha256(archive.read_bytes()).hexdigest()
Path(str(archive)+'.sha256').write_text(digest+'  '+archive.name+'\n',encoding='ascii')
print('Built verified package '+archive.name+' '+digest)
