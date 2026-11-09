"""Upgrade the verified published v1.5.1 to the integrated v1.6.0 workspace."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from hashlib import sha256
import sys

base=Path(sys.argv[1] if len(sys.argv)>1 else 'resell-agent-mvp-v1.5.1.zip')
checksum=Path(str(base)+'.sha256')
assert checksum.is_file(),'Base release checksum missing'
assert sha256(base.read_bytes()).hexdigest()==checksum.read_text(encoding='ascii').split()[0],'Base file checksum mismatch'

ROOT='resell-agent-starter/'
with ZipFile(base) as z:
    files={i.filename:z.read(i.filename) for i in z.infolist() if not i.is_dir()}

def replace(path,old,new):
    target=ROOT+path
    text=files[target].decode('utf-8')
    if old not in text:raise RuntimeError(f'Unexpected base code in {path}; missing {old[:100]}')
    files[target]=text.replace(old,new).encode('utf-8')

replace('agent/updater.py',"VERSION = '1.5.1'","VERSION = '1.6.0'")
replace('tests/test_updater.py','1.5.2','1.6.1')

replace('app.py','from agent.ui_command_center import render_hub',
    'from agent.ui_command_center import render_hub\nfrom agent.ui_hunter import render_hunter')

replace('app.py',
'''st.markdown("""<style>
.block-container {max-width: 1220px; padding-top: 2rem}
[data-testid='stMetric'] {background: rgba(125,125,125,0.08);border: 1px solid rgba(125,125,125,0.12);border-radius: 12px;padding: 16px}
small {opacity: .8}
</style>""", unsafe_allow_html=True)''',
'''st.markdown("""<style>
.block-container{max-width:1500px;padding-top:1.4rem;padding-bottom:3rem}
section[data-testid='stSidebar']{background:#111b2a}
section[data-testid='stSidebar'] [data-testid='stRadio'] label{border-radius:12px}
[data-testid='stMetric']{background:#152235;border:1px solid #2a3b52;border-radius:16px;padding:18px}
[data-testid='stMetricValue']{font-weight:760}
div[data-testid='stVerticalBlockBorderWrapper']{border-radius:15px}
.stButton button{border-radius:11px}
.stDownloadButton button{border-radius:11px}
small{opacity:.83}
</style>""", unsafe_allow_html=True)''')

replace('app.py',
'''    page = st.radio("Navigation", ["Command Center", "Overview", "Add product", "Research lab", "Supplier monitor", "Product finder", "Live shopping search", "Resale marketplace search", "Products & photos", "Listing manager", "Accounts & limits", "Orders", "Event Radar", "Backups", "App updates"], label_visibility="collapsed")''',
'''    page = st.radio("Főmenü", [
        "Termékvadász", "Command Center", "Products & photos",
        "Listing manager", "App updates", "További eszközök"
    ],label_visibility="collapsed")
    if page=="További eszközök":
        page=st.selectbox("Korábbi modulok",[
            "Overview", "Add product", "Research lab", "Supplier monitor",
            "Product finder", "Live shopping search", "Resale marketplace search",
            "Accounts & limits", "Orders", "Event Radar", "Backups"
        ])''')

replace('app.py',
'''if page == "Command Center":
    render_hub(products)''',
'''if page == "Termékvadász":
    render_hunter()

elif page == "Command Center":
    render_hub(products)''')

replace('app.py',
'''    st.caption("Local database · No AI token costs")
    st.info("Live research requires an optional Serper key. The Command Center unifies opportunities, drafts and orders. Live publishing is only available after approved integration setup.", icon="ℹ️")''',
'''    st.caption("Serper keresés · Cloudflare AI · helyi adatbázis")
    st.caption("Kiválasztás → piszkozatok → ellenőrzés → engedélyezett közzététel")''')

for module in ('hunter','ui_hunter'):
    files[ROOT+'agent/'+module+'.py']=Path('release_src/v160/'+module+'.py').read_bytes()
files[ROOT+'tests/test_hunter.py']=Path('release_src/v160/test_hunter.py').read_bytes()

files[ROOT+'UPGRADE_TO_V160.md']=(
    '# Resell Agent v1.6.0 - Termekvadasz workspace\n\n'
    'Modernized dark local interface with Termekvadasz as default starting page. '
    'Batch Hungarian Serper shopping searches across Christmas, electronics, gaming, '
    'home and toys; up to 9 searches per click, capped by the existing monthly API '
    'budget. Real Shopping results only, stored with merchant, price, source URL and '
    'catalog thumbnail for visual discovery. Live product stock, supplier shipping '
    'and resale profitability are NOT claimed or invented.\n\n'
    'Select candidates as visual cards or in bulk; each selected product gets a '
    'real database record and platform-specific editable listing drafts. Optional '
    'Cloudflare Gemma 4 text generation writes concise, factual Hungarian listings '
    'without using local PC GPU. One product photo can be uploaded and an '
    'illustrative AI preview created on Cloudflare. No ChatGPT conversation is '
    'needed to operate the program.\n\n'
    'eBay official Inventory API integration remains opt-in and requires seller '
    'OAuth, business policies, location key, published HTTPS actual product images, '
    'category aspects, verified stock, explicit sale prices and seller permission. '
    'Sandbox does not mark products live. Vinted/Facebook/Jofogas/Vatera/Hardverapro/'
    'Amazon automatic posting is NOT connected; these channels get drafts/exports. '
    'Actual marketplace fulfillment and purchases are NOT automated.\n\n'
    'Preserves all existing data and legacy tools in Tovabbi eszkozok. '
    'API credentials stay in local Streamlit session or environment variables; '
    'never hardcoded in packages. This is a substantial integrated first stage, '
    'not an end-to-end unattended business release.\n'
).encode('utf-8')

out=Path('resell-agent-mvp-v1.6.0.zip')
with ZipFile(out,'w',ZIP_DEFLATED) as z:
    for path,content in files.items():
        if path.startswith(ROOT+'data/') or path.startswith(ROOT+'backups/'):
            raise ValueError('User data cannot be included in release')
        z.writestr(path,content)
digest=sha256(out.read_bytes()).hexdigest()
Path(str(out)+'.sha256').write_text(digest+'  '+out.name+'\n',encoding='ascii')
print('Built '+out.name+' sha256 '+digest)
