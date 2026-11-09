"""Add automatic stock-photo transformation to the published v1.6.0 workspace."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from hashlib import sha256
import sys

base=Path(sys.argv[1] if len(sys.argv)>1 else 'resell-agent-mvp-v1.6.1.zip')
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
replace('agent/updater.py',"VERSION = '1.6.1'","VERSION = '1.6.2'")
replace('tests/test_updater.py','1.6.2','1.6.3')
manual_code = "\n\ndef stage_uploaded_update(payload: bytes) -> dict:\n    \"\"\"Stage an uploaded trusted update ZIP without changing the GitHub updater.\n\n    SHA-256 detects later changes; local upload cannot prove publisher identity.\n    \"\"\"\n    import io\n    if not isinstance(payload, bytes) or not payload or len(payload) > MAX_DOWNLOAD:\n        raise ValueError('Update ZIP is empty or exceeds the 20 MB limit.')\n    try:\n        with zipfile.ZipFile(io.BytesIO(payload)) as zf:\n            info = zf.getinfo('resell-agent-starter/agent/updater.py')\n            if info.file_size > 250000:\n                raise ValueError('Update package has an oversized version manifest.')\n            source = zf.read(info).decode('utf-8')\n    except (zipfile.BadZipFile, KeyError, UnicodeError) as exc:\n        raise ValueError('ZIP is not a valid Resell Agent update.') from exc\n    match = re.search(r\"(?m)^VERSION\\s*=\\s*[\\x27\\x22](\\d+\\.\\d+\\.\\d+)[\\x27\\x22]\\s*$\", source)\n    if not match:\n        raise ValueError('ZIP does not identify a valid Resell Agent version.')\n    version = match.group(1)\n    if parse_version(version) <= parse_version(VERSION):\n        raise ValueError('Uploaded ZIP must contain a newer version.')\n    UPDATES.mkdir(parents=True, exist_ok=True)\n    filename = f'resell-agent-mvp-v{version}.zip'\n    tmp = UPDATES / (filename + '.uploading')\n    target = UPDATES / filename\n    try:\n        tmp.write_bytes(payload)\n        validated_archive_members(tmp)\n        os.replace(tmp, target)\n    finally:\n        tmp.unlink(missing_ok=True)\n    meta = {'version': 'v' + version, 'filename': filename,\n            'sha256': hashlib.sha256(payload).hexdigest(),\n            'repo': 'Trusted local ZIP upload', 'source': 'local',\n            'release_url': '', 'downloaded_at': time.time()}\n    atomic_json(STAGED, meta)\n    return meta\n"
ui_code = "\n    st.subheader('Or upload an update ZIP')\n    st.caption('Optional: import a trusted Resell Agent ZIP from your computer. '\n               'It must contain a newer version and pass archive safety checks. '\n               'Local uploads cannot verify publisher authenticity, so only use trusted files.')\n    user_zip = st.file_uploader('Update ZIP', type=['zip'], key='manual_release_zip')\n    if user_zip is not None and st.button('Verify ZIP and stage update'):\n        try:\n            result = updater.stage_uploaded_update(user_zip.getvalue())\n            st.success(f\"Version {result['version']} staged. Use the installation button below.\")\n            st.rerun()\n        except (ValueError, OSError) as exc:\n            st.error(f'Could not use uploaded ZIP: {exc}')\n\n"
replace('agent/updater.py', '\n def request_install() -> None:'.replace(' ', ''), manual_code+'\ndef request_install() -> None:')
replace('agent/ui_updates.py', '    staged = updater.staged_metadata()\n', ui_code+'    staged = updater.staged_metadata()\n')
files[ROOT+'tests/test_upload_update.py'] = "\"\"\"Tests for dashboard-uploaded update packages.\"\"\"\nimport io\nimport tempfile\nimport unittest\nimport zipfile\nfrom pathlib import Path\nfrom unittest.mock import patch\nfrom agent import updater\n\ndef sample(version='1.6.3', extra=None):\n    content = {'app.py': b'pass',\n               'launcher.py': b'pass',\n               'agent/updater.py': (\"VERSION = '\" + version + \"'\\n\").encode(),\n               'requirements.txt': b'requests',\n               'START_WINDOWS.bat': b'@echo off'}\n    content.update(extra or {})\n    buf = io.BytesIO()\n    with zipfile.ZipFile(buf, 'w') as zf:\n        for name, body in content.items():\n            zf.writestr('resell-agent-starter/' + name, body)\n    return buf.getvalue()\n\nclass LocalZipTests(unittest.TestCase):\n    def setUp(self):\n        self.tmp = tempfile.TemporaryDirectory()\n        root = Path(self.tmp.name)\n        self.patches = [patch.object(updater, 'VERSION', '1.6.2'),\n                        patch.object(updater, 'UPDATES', root / 'updates'),\n                        patch.object(updater, 'STAGED', root / 'updates' / 'staged.json')]\n        for item in self.patches: item.start()\n    def tearDown(self):\n        for item in reversed(self.patches): item.stop()\n        self.tmp.cleanup()\n    def test_valid_release_and_integrity(self):\n        staged = updater.stage_uploaded_update(sample())\n        self.assertEqual(staged['version'], 'v1.6.3')\n        self.assertEqual(updater.staged_metadata()['source'], 'local')\n        (updater.UPDATES / staged['filename']).write_bytes(b'tampered')\n        self.assertIsNone(updater.staged_metadata())\n    def test_reject_older_release(self):\n        with self.assertRaises(ValueError): updater.stage_uploaded_update(sample('1.6.1'))\n    def test_reject_protected_file(self):\n        with self.assertRaises(ValueError):\n            updater.stage_uploaded_update(sample(extra={'data/secret.txt':b'secret'}))\n    def test_reject_invalid_zip(self):\n        with self.assertRaises(ValueError): updater.stage_uploaded_update(b'not a zip')\n".encode('utf-8')
files[ROOT+'UPGRADE_TO_V162.md'] = ('Resell Agent v1.6.2: optional trusted ZIP upload in App updates. GitHub Releases remains the default. The existing supervisor preserves user data, backs up before install and rolls back code on failed startup. Local uploads are not publisher-authenticated. No API changes.\n').encode('utf-8')
out=Path('resell-agent-mvp-v1.6.2.zip')
with ZipFile(out,'w',ZIP_DEFLATED) as z:
    for key,value in files.items():
        if key.startswith(ROOT+'data/') or key.startswith(ROOT+'backups/'):
            raise ValueError('Refusing to include user data')
        z.writestr(key,value)
digest=sha256(out.read_bytes()).hexdigest()
Path(str(out)+'.sha256').write_text(digest+'  '+out.name+'\n',encoding='ascii')
print('Built '+str(out)+' SHA256='+digest)
