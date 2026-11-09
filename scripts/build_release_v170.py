"""Resell Agent 1.7.0: personal, dark, functional private dashboard."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from hashlib import sha256
import sys

base=Path(sys.argv[1] if len(sys.argv)>1 else 'resell-agent-mvp-v1.6.9.zip')
check=Path(str(base)+'.sha256')
assert check.is_file(),'Source release checksum missing'
assert sha256(base.read_bytes()).hexdigest()==check.read_text(encoding='ascii').split()[0], 'Source checksum mismatch'
ROOT='resell-agent-starter/'
with ZipFile(base) as z:
    files={i.filename:z.read(i.filename) for i in z.infolist() if not i.is_dir()}

def replace(path,old,new):
    key=ROOT+path
    raw=files[key].decode('utf-8')
    if old not in raw:
        raise RuntimeError('Version drift in '+path+': '+repr(old[:140]))
    files[key]=raw.replace(old,new).encode('utf-8')

def span(path,start,end,new):
    key=ROOT+path
    raw=files[key].decode('utf-8')
    i=raw.find(start)
    if i<0:raise RuntimeError('Missing start in '+path+' '+repr(start[:85]))
    j=raw.find(end,i+len(start))
    if j<0:raise RuntimeError('Missing end in '+path+' '+repr(end[:85]))
    files[key]=(raw[:i]+new+raw[j:]).encode('utf-8')

replace('agent/updater.py',"VERSION = '1.6.9'","VERSION = '1.7.0'")
replace('tests/test_updater.py','1.6.10','1.7.1')
replace('tests/test_upload_update.py',"'1.6.10'","'1.7.1'")
replace('tests/test_upload_update.py',"'1.6.9'","'1.7.0'")
replace('tests/test_upload_update.py',"'v1.6.10'","'v1.7.1'")

for module in ('private_research','ui_private_dashboard','ui_theme'):
    files[ROOT+'agent/'+module+'.py']=Path('release_src/v170/'+module+'.py').read_bytes()
files[ROOT+'tests/test_private_dashboard.py']=Path(
    'release_src/v170/test_private_dashboard.py').read_bytes()

replace('app.py',
        'from agent import listing_previews',
        'from agent import listing_previews, ui_private_dashboard')
replace('app.py',
        'st.set_page_config(page_title="Resell Agent | Local Control Center", page_icon="📦", layout="wide")',
        'st.set_page_config(page_title="Resell Agent · Privát Dashboard", page_icon="📈", layout="wide")')
span('app.py',
    'with st.sidebar:\n',
    'if page == "Termékvadász":\n',
    """if st.session_state.get('_resell_next_page'):
    st.session_state['resell_private_page']=st.session_state.pop('_resell_next_page')

with st.sidebar:
    st.markdown('## ↗ Resell Agent')
    st.caption('PRIVATE DASHBOARD · v'+updater.VERSION)
    page = st.radio('Főmenü',[
        'Dashboard','Termékfigyelés','Ajánlott termékek',
        'Kiválasztott termékek','Vinted','Jófogás',
        'Beszállítók','Keresési diagnosztikák',
        'Szállítási ellenőrzés','Listing manager',
        'App updates','További eszközök'
    ],key='resell_private_page',label_visibility='collapsed')
    if page=='További eszközök':
        page=st.selectbox('Korábbi modulok',[
            'Command Center','Products & photos','Overview','Add product',
            'Research lab','Supplier monitor','Product finder',
            'Live shopping search','Resale marketplace search',
            'Accounts & limits','Orders','Event Radar','Backups'
        ])
    st.divider()
    st.caption('13 beszállító · Vinted + Jófogás')
    st.caption('4 000 Ft tervezett profit · max. 4 munkanap')
    st.caption('Helyi adatok · nincs automatikus vásárlás vagy közzététel')

if page in ('Dashboard','Ajánlott termékek','Kiválasztott termékek',
            'Vinted','Jófogás','Beszállítók','Keresési diagnosztikák',
            'Szállítási ellenőrzés'):
    ui_private_dashboard.render(page,products,listings)

elif page == 'Termékfigyelés':
    render_hunter()

""")
replace('app.py',
        'targets = st.multiselect("Create draft for", db.PLATFORMS, default=["Jófogás", "Facebook Marketplace"])',
        'targets = st.multiselect("Create draft for", ["Vinted","Jófogás"], default=["Vinted","Jófogás"])')
replace('app.py',
        'elif page == "Listing manager":\n    st.title',
        'elif page == "Listing manager":\n'
        '    listings=[r for r in listings if r["marketplace"] in ("Vinted","Jófogás")]\n'
        '    st.title')
# Existing hunter sidebar still lets users change cloud-copy parameters but
# does not put any other marketplace in the active new Vinted/Jófogás pipeline.
replace('agent/ui_hunter.py',
        "markets=st.session_state.get('hunter_marketplaces',list(db.PLATFORMS))",
        "markets=[m for m in st.session_state.get('hunter_marketplaces',['Vinted','Jófogás']) "
        "if m in ('Vinted','Jófogás')]")
replace('agent/ui_hunter.py',
        "st.multiselect('Piacterek',list(db.PLATFORMS),",
        "st.multiselect('Piacterek',['Vinted','Jófogás'],")
replace('agent/ui_hunter.py',
        "default=list(db.PLATFORMS),key='hunter_marketplaces'",
        "default=['Vinted','Jófogás'],key='hunter_marketplaces'")

files[ROOT+'UPGRADE_TO_V170.md']=(
    '# Resell Agent v1.7.0 – privát sötét irányítópult\n\n'
    '- Dark graphite/teal private dashboard is now the first home screen; '
    'no SaaS landing page, billing or registration.\n'
    '- Central catalogue-photo product list and right-side product inspector, '
    'filters, six real metrics, supplier links and market diagnostic shortcuts.\n'
    '- Primary project scope: 13 previously selected stores, Vinted and Jófogás.\n'
    '- Recommended listing price is exactly supplier price plus all manually '
    'verified costs plus 4,000 HUF pre-tax profit, independently per marketplace.\n'
    '- Exact Pest-county postcode stored locally; shipping commitments are '
    'product-specific and considered current only for 24 hours.\n'
    '- Shipping evidence is entered by the user after checking actual cart '
    'conditions. No fictitious automated exact delivery claims.\n'
    '- Previously saved products, photos, listings, data backups and GitHub '
    'release updater are untouched.\n'
).encode('utf-8')

out=Path('resell-agent-mvp-v1.7.0.zip')
with ZipFile(out,'w',ZIP_DEFLATED) as z:
    for key,value in files.items():
        if key.startswith(ROOT+'data/') or key.startswith(ROOT+'backups/'):
            raise ValueError('Refusing to pack personal data into an app update')
        z.writestr(key,value)
digest=sha256(out.read_bytes()).hexdigest()
Path(str(out)+'.sha256').write_text(digest+'  '+out.name+'\n',encoding='ascii')
print('Built',out,'SHA256='+digest)
