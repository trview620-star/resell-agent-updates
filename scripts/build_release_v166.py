"""Resell Agent v1.6.6: product photo previews in listings and category-aware shots."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from hashlib import sha256
import sys

base=Path(sys.argv[1] if len(sys.argv)>1 else 'resell-agent-mvp-v1.6.5.zip')
check=Path(str(base)+'.sha256')
assert check.is_file(),'Published source checksum missing'
assert sha256(base.read_bytes()).hexdigest()==check.read_text(encoding='ascii').split()[0], 'Published base checksum mismatch'

ROOT='resell-agent-starter/'
with ZipFile(base) as z:
    files={i.filename:z.read(i.filename) for i in z.infolist() if not i.is_dir()}

def replace(path,old,new):
    key=ROOT+path
    raw=files[key].decode('utf-8')
    if old not in raw:
        raise RuntimeError('Base changed: '+path+' missing '+repr(old[:125]))
    files[key]=raw.replace(old,new).encode('utf-8')

replace('agent/updater.py',"VERSION = '1.6.5'","VERSION = '1.6.6'")
replace('tests/test_updater.py','1.6.6','1.6.7')
replace('tests/test_upload_update.py',"'1.6.6'","'1.6.7'")
replace('tests/test_upload_update.py',"'1.6.5'","'1.6.6'")
replace('tests/test_upload_update.py',"'v1.6.6'","'v1.6.7'")

for module in ('listing_previews','photo_shot_plan'):
    files[ROOT+'agent/'+module+'.py']=Path('release_src/v166/'+module+'.py').read_bytes()
files[ROOT+'tests/test_listing_previews.py']=Path('release_src/v166/test_listing_previews.py').read_bytes()

# The product identity must not be intentionally changed by the model:
# AI previews are always reviewed, while actual photos remain byte-for-byte.
replace('agent/auto_stock_photo.py',
        'from . import db, cloudflare_photos',
        'from . import db, cloudflare_photos, photo_shot_plan')
replace('agent/auto_stock_photo.py',
        "'prompt':(None,PROMPT),'width':(None,'1024'),'height':(None,'768')",
        "'prompt':(None,photo_shot_plan.prompt_for(row['title'],1)),"
        "'width':(None,'1024'),'height':(None,'768')")

replace('agent/stock_photo_gallery.py',
        'from . import db, auto_stock_photo as stock, cloudflare_photos',
        'from . import db, auto_stock_photo as stock, cloudflare_photos, photo_shot_plan')
replace('agent/stock_photo_gallery.py',
        "    prompt=stock.PROMPT+' '+EXTRA_PROMPTS[slot]",
        "    record=db.row('SELECT title FROM products WHERE id=?',(product_id,))\n"
        "    title=record['title'] if record else ''\n"
        "    prompt=photo_shot_plan.prompt_for(title,slot)")

# Product cards in the selected-products view.
replace('agent/ui_hunter.py',
        'from . import db, hunter, shopping, free_photo_import, cloudflare_photos, auto_stock_photo, condition_copy, stock_photo_gallery, supplier_links, ui_market_radar, market_intelligence',
        'from . import db, hunter, shopping, free_photo_import, cloudflare_photos, auto_stock_photo, condition_copy, stock_photo_gallery, supplier_links, ui_market_radar, market_intelligence, listing_previews, photo_shot_plan')
replace('agent/ui_hunter.py',
        "    ids={r['id']:r for r in rows}",
        "    listing_previews.render_selected_cards(rows,page_size=9)\n"
        "    ids={r['id']:r for r in rows}")
replace('agent/ui_hunter.py',
        "    st.markdown('**'+product['title']+'**')",
        "    st.markdown('**'+product['title']+'**')\n"
        "    listing_previews.render_gallery(product['id'],hunter_id=selected)")
replace('agent/ui_hunter.py',
        "    pictures=stock_photo_gallery.slots(selected)",
        "    pictures=stock_photo_gallery.slots(selected)\n"
        "    duplicates=photo_shot_plan.difference_warning([\n"
        "        (p['slot'],p['bytes']) for p in pictures if p['bytes']])\n"
        "    if duplicates:\n"
        "        st.warning('Hasonló képek találhatók: '+', '.join(map(str,duplicates))+\n"
        "            '. Ezekhez érdemes másik változatot készíteni jóváhagyás előtt.')")
replace('agent/ui_hunter.py',
        "st.markdown(f'**{number}/4. kép**')",
        "st.markdown(f'**{number}/4. kép · {photo_shot_plan.role(number)}**')")

# The classic Listing manager also displays images directly next to listings.
replace('app.py',
        'from agent.ui_theme import render_theme, top_bar',
        'from agent.ui_theme import render_theme, top_bar\n'
        'from agent import listing_previews')
replace('app.py',
        'elif page == "Listing manager":',
        'elif page == "Listing manager":')
replace('app.py',
        '    if product:\n        with st.form("draft_builder"):',
        '    if product:\n'
        '        listing_previews.render_gallery(product["id"])\n'
        '        with st.form("draft_builder"):')
replace('app.py',
        '    if listings:\n        listing_options = {r["id"]: r for r in listings}',
        '    if listings:\n'
        '        listing_previews.render_listing_cards(listings,page_size=9)\n'
        '        listing_options = {r["id"]: r for r in listings}')
replace('app.py',
        'selected_id = st.selectbox("Choose listing to edit", list(listing_options), format_func=lambda k: f"#{k} — {listing_options[k][\'marketplace\']} — {listing_options[k][\'product_name\']}")',
        'selected_id = st.selectbox("Choose listing to edit", list(listing_options), format_func=lambda k: f"#{k} — {listing_options[k][\'marketplace\']} — {listing_options[k][\'product_name\']}", key="listing_edit_id")')
replace('app.py',
        '        selected = listing_options[selected_id]\n',
        '        selected = listing_options[selected_id]\n'
        '        listing_previews.render_gallery(selected["product_id"])\n')

# Old regression tests assumed an invariant generic wooden tabletop prompt.
# A wreath still uses a wooden surface; a headset must use a desk.
files[ROOT+'UPGRADE_TO_V166.md']=(
    '# v1.6.6 – Product photo previews\n\n'
    '- See source-labelled thumbnail cards directly in Kiválasztottak and Listing manager.\n'
    '- Up to 4 images near each selected listing; first priority goes to original seller uploads.\n'
    '- Approved AI pictures, pending AI previews and supplier catalog thumbnails remain clearly distinguished.\n'
    '- Four distinct shot-role prompts with category-specific home settings. Gaming headsets use gaming desks, not kitchens.\n'
    '- Image similarity flags aid review. Generative AI cannot guarantee pixel-perfect logos or text: inspect before approval.\n'
    '- Missing images show an honest placeholder. Source photos, local database, and all existing APIs remain unchanged.\n'
    '- Existing in-app GitHub release / ZIP updater preserved.\n'
).encode('utf-8')

out=Path('resell-agent-mvp-v1.6.6.zip')
with ZipFile(out,'w',ZIP_DEFLATED) as z:
    for key,value in files.items():
        if key.startswith(ROOT+'data/') or key.startswith(ROOT+'backups/'):
            raise ValueError('User data must not be shipped in an update')
        z.writestr(key,value)
digest=sha256(out.read_bytes()).hexdigest()
Path(str(out)+'.sha256').write_text(digest+'  '+out.name+'\n',encoding='ascii')
print('Built',out,'SHA256='+digest)
