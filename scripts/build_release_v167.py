"""Resell Agent v1.6.7: strict source-preserving four-shot photo workflow."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from hashlib import sha256
import sys

base=Path(sys.argv[1] if len(sys.argv)>1 else 'resell-agent-mvp-v1.6.6.zip')
check=Path(str(base)+'.sha256')
assert check.is_file(),'Published release checksum missing'
assert sha256(base.read_bytes()).hexdigest()==check.read_text(encoding='ascii').split()[0], 'Verified source checksum mismatch'
ROOT='resell-agent-starter/'
with ZipFile(base) as z:
    files={i.filename:z.read(i.filename) for i in z.infolist() if not i.is_dir()}

def replace(path,old,new):
    key=ROOT+path
    source=files[key].decode('utf-8')
    if old not in source:
        raise RuntimeError(f'Cannot patch {path}: '+repr(old[:125]))
    files[key]=source.replace(old,new).encode('utf-8')

def insert_once(path,needle,insertion):
    key=ROOT+path
    source=files[key].decode('utf-8')
    if needle not in source:raise RuntimeError(f'Cannot insert in {path}: {needle[:125]!r}')
    files[key]=source.replace(needle,insertion+needle,1).encode('utf-8')

replace('agent/updater.py',"VERSION = '1.6.6'","VERSION = '1.6.7'")
replace('tests/test_updater.py','1.6.7','1.6.8')
replace('tests/test_upload_update.py',"'1.6.7'","'1.6.8'")
replace('tests/test_upload_update.py',"'1.6.6'","'1.6.7'")
replace('tests/test_upload_update.py',"'v1.6.7'","'v1.6.8'")

for module in ('source_photo_series','ui_faithful_photos'):
    files[ROOT+'agent/'+module+'.py']=Path('release_src/v167/'+module+'.py').read_bytes()
files[ROOT+'tests/test_source_photo_series.py']=Path('release_src/v167/test_source_photo_series.py').read_bytes()

# Source-derived previews sit between real uploads and AI images. They never
# get the "original" badge and catalogue photos never become seller photos.
lookup="""
    # Exact-pixel source crops remain visibly distinct from originals and AI.
    from . import source_photo_series
    for shot in source_photo_series.read(pid):
        if shot['bytes'] and (shot['status']=='approved' or
                              (include_pending and shot['status']=='pending')):
            src_label=('Saját fotóból vágott – változatlan feliratok' if
                       shot['source_type']=='original' else
                       'Katalógusképből vágott előnézet – nem saját fotó')
            approval=(' · jóváhagyva' if shot['status']=='approved'
                      else ' · jóváhagyásra vár')
            add(shot['bytes'],src_label+approval,'faithful')
            if len(out)>=limit:return out

"""
insert_once('agent/listing_previews.py',
    '    # Approved AI illustrations are separate from original photos in all exports.',
    lookup)

# Keep the existing public python API compatible, but the dashboard now
# explicitly requests source-preserving crops instead of speculative AI shots.
replace('agent/ui_hunter.py',
        'token=cloud_token,use_ai=use_ai)',
        'token=cloud_token,use_ai=use_ai,auto_photo=False)')
replace('agent/ui_market_radar.py',
        'token=cloud_token,use_ai=use_ai)',
        'token=cloud_token,use_ai=use_ai,auto_photo=False)')

# If the UI chooses safe mode, auto-stage an honest four-picture series.
stage="""
    if not auto_photo:
        try:
            from . import source_photo_series
            staged_safe=source_photo_series.create(pid,hunter_id=hunter_id)
            photo_status=('source_pending' if staged_safe['gallery'] else 'missing')
        except (ValueError,OSError):
            photo_status='source_missing'
"""
insert_once('agent/hunter.py',
        "    return {'product_id':pid,'drafts':ready,'description_source':origin,",
        stage)

replace('agent/ui_hunter.py',
        ', listing_previews, photo_shot_plan',
        ', listing_previews, photo_shot_plan, ui_faithful_photos')
# Put the transparent source-preserving editor first, with legacy AI behind
# a collapsed optional panel.
path=ROOT+'agent/ui_hunter.py'
source=files[path].decode('utf-8')
start=source.find("    st.markdown('**4 különálló termékkép")
end=source.find("    drafts=db.rows('SELECT * FROM listings WHERE product_id=? ORDER BY marketplace'",start)
if start<0 or end<0:raise RuntimeError('Cannot locate the legacy four-photo editor')
legacy=source[start:end]
# Block any near-duplicate AI photo and require explicit logo/lettering check.
original="""                        if picture['status']=='pending':
                            if st.button('Kép jóváhagyása',
"""
revised="""                        if picture['status']=='pending':
                            markings_ok=st.checkbox(
                                'Összevetettem a forrással: logó, betűk és minták változatlanok',
                                key=f'hunter_ai_markings_ok_{selected}_{number}')
                            if number in duplicates:
                                st.warning('Ez a kép túl hasonló egy másikhoz. Készíts eltérő változatot.')
                            if st.button('Kép jóváhagyása',
"""
if original not in legacy:raise RuntimeError('AI approval guard marker missing')
legacy=legacy.replace(original,revised)
old="""                                key=f'hunter_four_approve_{selected}_{number}',
                                use_container_width=True):"""
new="""                                key=f'hunter_four_approve_{selected}_{number}',
                                disabled=(not markings_ok or number in duplicates),
                                use_container_width=True):"""
if old not in legacy:raise RuntimeError('AI approval button marker missing')
legacy=legacy.replace(old,new)
wrapped="\n".join(('    '+line if line else line) for line in legacy.split('\n'))
replacement=("    ui_faithful_photos.render(product['id'],selected,product['title'])\n"
             "    with st.expander('Opcionális AI-illusztrációk – csak manuális ellenőrzés után',"
             " expanded=False):\n"+wrapped)
files[path]=(source[:start]+replacement+source[end:]).encode('utf-8')

files[ROOT+'UPGRADE_TO_V167.md']=(
    '# Resell Agent v1.6.7 – Identity-safe four-photo series\n\n'
    '* Default selection flow now prepares lossless source-photo crops instead '
    'of redrawing logos or inventing a product-side with AI.\n'
    '* Four distinct purposes: full product, detail, alternate genuine source '
    '(or truthful alternate crop), real packaging photo if uploaded '
    '(otherwise a second visible detail).\n'
    '* Fine-tune the close-up centre with in-dashboard sliders.\n'
    '* Original uploads remain byte-for-byte unchanged; derived PNGs use '
    'unmodified source pixels and remain locally backed up in data/.\n'
    '* Supplier catalogue previews are visibly labelled and cannot be '
    'approved as seller-owned photos.\n'
    '* Optional legacy AI image variations remain available but are '
    'collapsed and require both manual lettering verification and '
    'non-duplicate outputs before approval.\n'
    '* Listing preview cards and galleries show the source-derived images.\n'
    '* No changes to API keys, updater, product prices or published listings.\n'
).encode('utf-8')
out=Path('resell-agent-mvp-v1.6.7.zip')
with ZipFile(out,'w',ZIP_DEFLATED) as z:
    for name,data in files.items():
        if name.startswith(ROOT+'data/') or name.startswith(ROOT+'backups/'):
            raise ValueError('Refusing to ship user data in release ZIP')
        z.writestr(name,data)
digest=sha256(out.read_bytes()).hexdigest()
Path(str(out)+'.sha256').write_text(digest+'  '+out.name+'\n',encoding='ascii')
print('Built',out,'SHA256='+digest)
