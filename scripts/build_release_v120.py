"""Build separate AI angle preview feature from published verified v1.1.0 ZIP."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from hashlib import sha256
import sys

base=Path(sys.argv[1] if len(sys.argv)>1 else 'resell-agent-mvp-v1.1.0.zip')
check=Path(str(base)+'.sha256')
assert check.is_file(), 'Published v1.1.0 checksum missing'
assert sha256(base.read_bytes()).hexdigest()==check.read_text(encoding='ascii').split()[0], 'Wrong base ZIP'
ROOT='resell-agent-starter/'
with ZipFile(base) as archive:
    files={i.filename:archive.read(i.filename) for i in archive.infolist() if not i.is_dir()}
def replace(path,old,new):
    key=ROOT+path
    text=files[key].decode('utf-8')
    assert old in text, f'Expected content absent in {path}: {old[:70]}'
    files[key]=text.replace(old,new).encode('utf-8')

replace('agent/updater.py',"VERSION = '1.1.0'","VERSION = '1.2.0'")
replace('tests/test_updater.py','1.1.1','1.2.1')
replace('agent/ui_command_center.py',
        'from .backup import make_backup',
        'from .backup import make_backup\nfrom .ui_ai_listing_photos import render_ai_photo_page')
replace('agent/ui_command_center.py',
'''    tabs=st.tabs(['Opportunities','Photo + AI','Listing publisher','Operations + Events'])
    with tabs[0]:_research(products)
    with tabs[1]:_studio(products)
    with tabs[2]:_publish(products)
    with tabs[3]:_operations(products)''',
'''    tabs=st.tabs(['Opportunities','Photo + AI','AI Listing Photos','Listing publisher','Operations + Events'])
    with tabs[0]:_research(products)
    with tabs[1]:_studio(products)
    with tabs[2]:render_ai_photo_page(products)
    with tabs[3]:_publish(products)
    with tabs[4]:_operations(products)''')

for module in ('ai_listing_photos','ui_ai_listing_photos'):
    files[ROOT+'agent/'+module+'.py']=Path('release_src/v120/'+module+'.py').read_bytes()
files[ROOT+'tests/test_ai_listing_photos.py']=Path('release_src/v120/test_ai_listing_photos.py').read_bytes()
files[ROOT+'UPGRADE_TO_V120.md']=b'''# Resell Agent v1.2.0 - Four individual AI listing photo previews

New: Command Center -> AI Listing Photos. Four independent images, each 1536x1024 PNG.
Views: front three-quarter, straight front, side profile, rear three-quarter.
Natural-looking home setting is generated automatically. No collage or slider settings.
Select one original photo, supply your own OpenAI Image API key (unless OPENAI_API_KEY
environment variable exists), then explicitly click Generate. It invokes four paid
image-edit requests. User can review each, approve/download or regenerate one angle
using optional textual feedback. Approved PNGs can be exported as separate image
files in a ZIP or saved in data/ai_previews (not original photos and not published).
Generation is opt-in and never starts in background. API key is not saved to SQLite.
No changes to auto-publishing.

Requires OpenAI API billing and image model access. Ollama Gemma3 is an analysis model
and cannot generate new photorealistic views. ChatGPT Plus does not include API credit.
AI angles are illustrative; unseen sides may be inaccurate. Do not misrepresent
condition, packaging, included items or ownership on a sales listing.
'''
out=Path('resell-agent-mvp-v1.2.0.zip')
with ZipFile(out,'w',ZIP_DEFLATED) as z:
    for filename,content in files.items():
        if filename.startswith(ROOT+'data/') or filename.startswith(ROOT+'backups/'):
            raise ValueError('Private user data in package')
        z.writestr(filename,content)
digest=sha256(out.read_bytes()).hexdigest()
Path(str(out)+'.sha256').write_text(digest+'  '+out.name+'\n',encoding='ascii')
print('Built',out.name,digest)
