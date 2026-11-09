"""Add automatic stock-photo transformation to the published v1.6.0 workspace."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from hashlib import sha256
import sys

base=Path(sys.argv[1] if len(sys.argv)>1 else 'resell-agent-mvp-v1.6.2.zip')
check=Path(str(base)+'.sha256')
assert check.is_file(),'Published base checksum missing'
assert sha256(base.read_bytes()).hexdigest()==check.read_text(encoding='ascii').split()[0], 'Base release hash mismatch'

ROOT='resell-agent-starter/'
with ZipFile(base) as z:
    files={item.filename:z.read(item.filename) for item in z.infolist() if not item.is_dir()}
def replace(path,old,new):
    key=ROOT+path
    raw=files[key].decode('utf-8')
    if old not in raw:raise RuntimeError('Base changed: '+path+' missing '+old[:95])
    files[key]=raw.replace(old,new).encode('utf-8')
replace('agent/updater.py',"VERSION = '1.6.2'","VERSION = '1.6.3'")
replace('tests/test_updater.py','1.6.3','1.6.4')
replace('tests/test_upload_update.py',"'1.6.3'","'1.6.4'")
replace('tests/test_upload_update.py',"'1.6.2'","'1.6.3'")

def replace_span(path, start_marker, end_marker, replacement):
    key=ROOT+path
    raw=files[key].decode('utf-8')
    i=raw.find(start_marker)
    if i<0:raise RuntimeError('Missing start marker '+path)
    j=raw.find(end_marker,i+len(start_marker))
    if j<0:raise RuntimeError('Missing end marker '+path)
    files[key]=(raw[:i]+replacement+raw[j:]).encode('utf-8')

plain_description_code = "def plain_description(title):\n    \"\"\"Natural Hungarian fallback based only on title; no invented condition facts.\"\"\"\n    short = ' '.join(str(title or '').strip().split())[:160].rstrip(' .!')\n    if not short:\n        return ''\n    head = short if short.casefold().startswith('eladó ') else 'Eladó ' + short\n    head += '.'\n    lower = short.casefold()\n    if 'lego' in lower:\n        if any(word in lower for word in ('vidra', 'vidrá', 'macska', 'kutya', 'róka', 'állat', 'kutyu', 'madár', 'bagoly', 'oroszlán', 'delfin')):\n            middle = ('Nagyon aranyos, részletgazdag LEGO szett, ami összerakva is jól mutat a polcon. '\n                      'Ajándéknak is jó ötlet, főleg ha valaki szereti a LEGO-t vagy az állatokat.')\n        elif any(word in lower for word in ('virág', 'botanic', 'növény', 'orchidea', 'csokor')):\n            middle = ('Mutatós LEGO szett, amit jó élmény összerakni, és a polcon is szépen mutat. '\n                      'Ajándéknak is jó ötlet, ha valaki szereti a LEGO-t vagy a növényeket.')\n        else:\n            middle = ('Jó kis LEGO szett, amit élmény összerakni, és elkészülve is jól mutat. '\n                      'Ajándéknak is jó ötlet LEGO-rajongóknak.')\n    elif any(word in lower for word in ('társasjáték', 'társas játék', 'dobble', 'monopoly', 'activity', 'puzzle')):\n        middle = ('Jó választás, ha egy kis közös játékot keresel otthonra, vagy ajándékba vennéd. '\n                  'Ha érdekel a játék, nyugodtan írj.')\n    elif any(word in lower for word in ('playstation', 'xbox', 'nintendo', 'konzol', 'videójáték', 'videojáték', 'ps5', 'ps4')):\n        middle = ('Ha pont ezt a játékot vagy konzolt keresed, érdemes megnézni. '\n                  'Kérdés esetén szívesen segítek.')\n    elif any(word in lower for word in ('pulóver', 'kabát', 'cipő', 'farmer', 'póló', 'ruha')):\n        middle = ('Jó darab lehet a mindennapokra, ha ilyen fazont keresel. '\n                  'Ha kérdésed van róla, írj bátran.')\n    else:\n        middle = ('Ha pont ilyet keresel, írj nyugodtan, és megbeszéljük a részleteket.')\n    return (head + '\\n\\n' + middle + '\\n\\n'\n            'Ha bármi kérdésed van, írj nyugodtan!\\n\\n'\n            'Hasonló termékekért nézd meg a többi hirdetésemet.')\n"
ai_prompt_code = "    title = str(product.get('title') or '').strip()[:180]\n    brand = str(product.get('brand') or '').strip()[:90]\n    category = str(product.get('category') or '').strip()[:90]\n    condition = str(product.get('condition_text') or '').strip()[:120]\n    facts = ['Termék neve: ' + title]\n    if brand: facts.append('Márka: ' + brand)\n    if category: facts.append('Kategória: ' + category)\n    if condition and condition != 'Unknown / verify':\n        facts.append('Megerősített állapot: ' + condition)\n    prompt = (\n        'Írj rövid, kedves, természetes MAGYAR apróhirdetési szöveget, mintha '\n        'egy hétköznapi magáneladó írná. Ne legyen gépies, marketinges, túlzó '\n        'vagy erőltetett. A cél, hogy érdeklődést keltsen, nem a hangzatos reklám. '\n        'Kezdés például: \"Eladó [termék pontos neve].\" '\n        'Utána 1-2 rövid mondat arról, miért lehet jó választás az adott '\n        'terméktípus; ha LEGO, szólhatsz az építés élményéről és arról, '\n        'hogy elkészülve mutatós. Ne használj minden termékhez azonos szöveget. '\n        'Végén egy barátságos: \"Ha bármi kérdésed van, írj nyugodtan!\" '\n        'Kerüld ezeket a sablonokat: \"A termékkel kapcsolatos kérdéseket '\n        'szívesen fogadom\", \"A részleteket üzenetben egyeztetjük\", '\n        '\"tökéletes választás\", \"kihagyhatatlan\", \"prémium minőség\". '\n        'Ne legyen emoji, hashtag, pontlista vagy markdown. '\n        'Semmilyen állapotot, működést, csomagtartalmat, eredetiséget, '\n        'elérhetőséget, garanciát, szállítást, méretet vagy színt ne állíts, '\n        'ha nincs a megerősített adatok között. '\n        'A végére pontosan ezt írd: '\n        '\"Hasonló termékekért nézd meg a többi hirdetésemet.\" '\n        'Csak a kész hirdetés szövegét add vissza. '\n        'MEGERŐSÍTETT ADATOK: ' + ' | '.join(facts)\n    )\n"
ui_code = "    st.markdown('**Természetesebb hirdetésszöveg**')\n    st.caption('Kérhetsz új, emberibb hangvételű javaslatot. A jelenlegi leírás '\n               'nem változik, amíg jóvá nem hagyod a javaslatot.')\n    proposal_key = 'hunter_human_copy_' + str(selected)\n    if st.button('Természetesebb leírás készítése',\n                 key='hunter_human_copy_button_' + str(selected)):\n        suggestion = hunter.plain_description(product['title'])\n        text_account, text_token = credentials()[1:]\n        if text_account and text_token:\n            try:\n                suggestion = hunter.ai_description(dict(product), text_account, text_token)\n            except ValueError:\n                st.info('Az AI most nem elérhető, a helyi javaslatot mutatom.')\n        st.session_state[proposal_key] = suggestion\n    if proposal_key in st.session_state:\n        st.text_area('Új szövegjavaslat – jóváhagyás előtt',\n                     value=st.session_state[proposal_key], height=175,\n                     disabled=True, key='hunter_copy_preview_' + str(selected))\n        if st.button('Javaslat használata és mentése', type='primary',\n                     key='hunter_human_copy_apply_' + str(selected)):\n            final_text = st.session_state[proposal_key].strip()\n            if final_text:\n                db.update_product(product['id'], description=final_text)\n                for draft in db.rows(\n                    \"SELECT * FROM listings WHERE product_id=? AND status IN ('draft','ready')\",\n                    (product['id'],)):\n                    body = final_text\n                    if draft['marketplace'] in ('eBay', 'Amazon'):\n                        body = body.replace(\n                            '\\\\n\\\\nHasonló termékekért nézd meg a többi hirdetésemet.', '')\n                    db.update_listing(draft['id'], description=body)\n                st.session_state.pop(proposal_key, None)\n                st.session_state.pop('hunter_desc_edit_' + str(selected), None)\n                st.success('Új leírás elmentve a hirdetéspiszkozatokba.')\n                st.rerun()\n\n"
replace_span('agent/hunter.py','def plain_description(title):','TEXT_MODEL=',plain_description_code+'\n\n')
replace_span('agent/hunter.py','    prompt=(\n','    try:\n',ai_prompt_code)
replace('agent/hunter.py','        return text[:1700]',
        """        closing='Hasonló termékekért nézd meg a többi hirdetésemet.'
        cleaned=re.sub(r'\\s*Hasonló termékekért nézd meg a többi hirdetésemet\\.?', '', text,
                       flags=re.IGNORECASE).strip().strip('"')
        return (cleaned[:1550].rstrip()+'\\n\\n'+closing).strip()""")
replace('agent/ui_hunter.py',"    st.markdown('**Automatikus katalóguskép-átalakítás**')",
        ui_code+"    st.markdown('**Automatikus katalóguskép-átalakítás**')")
files[ROOT+'tests/test_listing_tone_v163.py']="import unittest\nfrom unittest.mock import Mock,patch\nfrom agent import hunter\n\nCLOSING = 'Hasonló termékekért nézd meg a többi hirdetésemet.'\n\nclass HungarianListingToneTests(unittest.TestCase):\n    def test_lego_otters_natural(self):\n        text = hunter.plain_description('LEGO Ideas 21366 Úszkáló vidrák')\n        self.assertIn('Eladó LEGO Ideas 21366 Úszkáló vidrák.', text)\n        self.assertIn('összerakva', text)\n        self.assertIn('állatokat', text)\n        self.assertIn('Ha bármi kérdésed van, írj nyugodtan!', text)\n        self.assertTrue(text.endswith(CLOSING))\n        self.assertNotIn('A részleteket üzenetben egyeztetjük', text)\n    def test_board_game_no_unverified_details(self):\n        text = hunter.plain_description('Dobble társasjáték')\n        self.assertIn('közös játékot', text)\n        for forbidden in ('bontatlan', 'hiánytalan', 'hibátlan', 'eredeti', 'garancia'):\n            self.assertNotIn(forbidden, text.casefold())\n    def test_unknown_product_does_not_claim_condition(self):\n        text = hunter.plain_description('USB kamera X7')\n        self.assertTrue(text.startswith('Eladó USB kamera X7.'))\n        self.assertNotIn('hibátlan', text)\n        self.assertNotIn('készleten', text)\n        self.assertEqual(text.count(CLOSING), 1)\n    def test_cloudflare_prompt_is_conversational(self):\n        response = Mock(ok=True, status_code=200)\n        response.json.return_value = {'result': {\n            'response':'Eladó LEGO vidrák. Aranyos szett, jól mutat. '\n                       'Ha kérdésed van, írj nyugodtan!'}}\n        with patch.object(hunter.requests, 'post', return_value=response) as request:\n            text = hunter.ai_description(\n                {'title':'LEGO Ideas Úszkáló vidrák','condition_text':'Unknown / verify'},\n                'a'*32, 'fake-valid-api-token')\n        self.assertTrue(text.endswith(CLOSING))\n        self.assertEqual(text.count(CLOSING), 1)\n        prompt = request.call_args.kwargs['json']['messages'][1]['content']\n        self.assertIn('hétköznapi magáneladó', prompt)\n        self.assertIn('Ne legyen gépies', prompt)\n        self.assertNotIn('Unknown / verify', prompt)\n    def test_title_only_no_duplicate_elado(self):\n        text = hunter.plain_description('Eladó LEGO 21366')\n        self.assertNotIn('Eladó Eladó', text)\n".encode('utf-8')
files[ROOT+'UPGRADE_TO_V163.md']=('Resell Agent v1.6.3: friendly Hungarian listing drafts, '
    'natural product-aware fallback, updated Cloudflare text prompt, '
    'non-destructive text regeneration preview/approval in selected-products dashboard. '
    'Verified data only; existing saved descriptions unchanged until explicitly approved. '
    'All previous functions and APIs preserved.\n').encode('utf-8')
out=Path('resell-agent-mvp-v1.6.3.zip')
with ZipFile(out,'w',ZIP_DEFLATED) as z:
    for key,value in files.items():
        if key.startswith(ROOT+'data/') or key.startswith(ROOT+'backups/'):
            raise ValueError('Refusing to include user data')
        z.writestr(key,value)
digest=sha256(out.read_bytes()).hexdigest()
Path(str(out)+'.sha256').write_text(digest+'  '+out.name+'\n',encoding='ascii')
print('Built '+str(out)+' SHA256='+digest)
