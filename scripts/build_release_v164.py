"""Build Resell Agent v1.6.4: verified new/sealed condition and 4-image gallery."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from hashlib import sha256
import sys

base=Path(sys.argv[1] if len(sys.argv)>1 else 'resell-agent-mvp-v1.6.3.zip')
check=Path(str(base)+'.sha256')
assert check.is_file(), 'Published base checksum missing'
assert sha256(base.read_bytes()).hexdigest()==check.read_text(encoding='ascii').split()[0], 'Base release hash mismatch'

ROOT='resell-agent-starter/'
with ZipFile(base) as z:
    files={i.filename:z.read(i.filename) for i in z.infolist() if not i.is_dir()}

def replace(path,old,new):
    key=ROOT+path
    raw=files[key].decode('utf-8')
    if old not in raw: raise RuntimeError('Base changed: '+path+' missing '+old[:115])
    files[key]=raw.replace(old,new).encode('utf-8')

def span(path,start,end,replacement):
    key=ROOT+path
    raw=files[key].decode('utf-8')
    i=raw.find(start)
    if i<0: raise RuntimeError('Cannot find start '+path+' '+start[:70])
    j=raw.find(end,i+len(start))
    if j<0: raise RuntimeError('Cannot find end '+path+' '+end[:70])
    files[key]=(raw[:i]+replacement+raw[j:]).encode('utf-8')

replace('agent/updater.py',"VERSION = '1.6.3'","VERSION = '1.6.4'")
replace('tests/test_updater.py','1.6.4','1.6.5')
replace('tests/test_upload_update.py',"'1.6.4'","'1.6.5'")
replace('tests/test_upload_update.py',"'1.6.3'","'1.6.4'")
replace('tests/test_upload_update.py',"'v1.6.4'","'v1.6.5'")

for module in ('condition_copy','stock_photo_gallery'):
    files[ROOT+'agent/'+module+'.py']=Path('release_src/v164/'+module+'.py').read_bytes()
for test in ('test_condition_copy','test_stock_photo_gallery'):
    files[ROOT+'tests/'+test+'.py']=Path('release_src/v164/'+test+'.py').read_bytes()

# The hunter continues to use existing shopping and Cloudflare APIs.
replace('agent/hunter.py','from . import db, shopping',
        'from . import db, shopping, condition_copy')
replace('agent/hunter.py',"        title=product['title'][:80]",
        "        title=condition_copy.title_for(product['title'],condition_copy.state_of(product))")
replace('agent/hunter.py',"        body=desc",
        "        body=condition_copy.description_for(desc,condition_copy.state_of(product),market)")
replace('agent/hunter.py',
        "            photo_status=staged['status'] if staged else 'missing'",
        """            photo_status=staged['status'] if staged else 'missing'
            if staged and photo_status in ('pending','approved'):
                from . import stock_photo_gallery
                try:
                    stock_photo_gallery.generate_remaining(hunter_id,account,token)
                except (ValueError,OSError):
                    pass  # First approved/pending photo and drafts stay available.""")

# The condition editor always checks supplier evidence before claiming a sealed pack.
replace('agent/ui_hunter.py',
        'from . import db, hunter, shopping, free_photo_import, cloudflare_photos, auto_stock_photo',
        'from . import db, hunter, shopping, free_photo_import, cloudflare_photos, auto_stock_photo, condition_copy, stock_photo_gallery')
condition_ui=Path('release_src/v164/ui_condition_fragment.txt').read_text(encoding='utf-8')
condition_ui=condition_ui.replace(
    "            st.success('Állapot elmentve a címekhez és a leírásokhoz.')",
    "            st.session_state.pop('hunter_desc_edit_'+str(selected),None)\n"
    "            st.success('Állapot elmentve a címekhez és a leírásokhoz.')")
replace('agent/ui_hunter.py',
        "    notes=st.text_area('Hirdetésszöveg – szerkeszthető'",
        condition_ui+"    notes=st.text_area('Hirdetésszöveg – szerkeszthető'")
replace('agent/ui_hunter.py',
        "            db.update_product(product['id'],description=notes.strip())",
        "            edited_copy=condition_copy.description_for(notes.strip(),condition_copy.state_of(product))\n"
        "            db.update_product(product['id'],description=edited_copy)")
replace('agent/ui_hunter.py',
        "                db.update_listing(l['id'],description=notes.strip())",
        "                db.update_listing(l['id'],description=condition_copy.description_for(\n"
        "                    edited_copy,condition_copy.state_of(product),l['marketplace']))")
replace('agent/ui_hunter.py',
        "            final_text = st.session_state[proposal_key].strip()",
        "            final_text = condition_copy.description_for(\n"
        "                st.session_state[proposal_key].strip(),condition_copy.state_of(product))")
replace('agent/ui_hunter.py',
        "                    body = final_text",
        "                    body = condition_copy.description_for(final_text,\n"
        "                        condition_copy.state_of(product),draft['marketplace'])")

# Display four individual preview cards, not a collage, with separate review actions.
gallery_ui=Path('release_src/v164/ui_gallery_fragment.txt').read_text(encoding='utf-8')
span('agent/ui_hunter.py',
     "    st.markdown('**Automatikus katalóguskép-átalakítás**')",
     "    drafts=db.rows('SELECT * FROM listings WHERE product_id=? ORDER BY marketplace'",
     gallery_ui)

# Upgrade the old one-photo test to assert the requested 4-image behavior.
replace('tests/test_auto_stock_photo.py','self.assertEqual(download.call_count,1)',
        'self.assertEqual(download.call_count,2)')
replace('tests/test_auto_stock_photo.py','self.assertEqual(post.call_count,1)',
        'self.assertEqual(post.call_count,4)')

files[ROOT+'UPGRADE_TO_V164.md']=(
    '# Resell Agent v1.6.4\n\n'
    '- Buyer-facing Hungarian drafts may show Új or Új, bontatlan in title and description, '
    'but only after explicit supplier-evidence confirmation. Shopping data alone never verifies it.\n'
    '- Four separately generated AI illustrative images per product, each with preview, '
    'individual approval and optional regeneration. AI imagery cannot prove sealed condition.\n'
    '- No edits to published listings, no automatic purchases, unchanged Cloudflare and Serper APIs.\n'
    '- GitHub Releases and in-dashboard ZIP updating remain unchanged.\n'
    '- All data, photos, backups and credentials remain outside the release ZIP.\n'
).encode('utf-8')
out=Path('resell-agent-mvp-v1.6.4.zip')
with ZipFile(out,'w',ZIP_DEFLATED) as z:
    for key,value in files.items():
        if key.startswith(ROOT+'data/') or key.startswith(ROOT+'backups/'):
            raise ValueError('Refusing to include user data')
        z.writestr(key,value)
digest=sha256(out.read_bytes()).hexdigest()
Path(str(out)+'.sha256').write_text(digest+'  '+out.name+'\n',encoding='ascii')
print('Built',out,'SHA256='+digest)
