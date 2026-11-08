"""Build the v0.5.5 auto-update test package from the existing v0.5.4 release."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import sys

source = Path(sys.argv[1] if len(sys.argv) > 1 else 'ResellAgent-v054.zip')
root = 'resell-agent-starter/'
with ZipFile(source) as z:
    files = {i.filename: z.read(i.filename) for i in z.infolist() if not i.is_dir()}

def replace(rel, old, new):
    key = root + rel
    value = files[key].decode('utf-8')
    if old not in value:
        raise RuntimeError(f'Unexpected base release: {rel} missing {old!r}')
    files[key] = value.replace(old, new).encode('utf-8')

replace('agent/updater.py', "VERSION = '0.5.4'", "VERSION = '0.5.5'")
replace('agent/updater.py',
    "archive_url, checksum_url = assets.get(filename), assets.get(filename + '.sha256')",
    "archive_url = assets.get(filename)\n    checksum_url = assets.get(filename + '.sha256') or assets.get(filename + '-checksum.txt')")
replace('agent/updater.py',
    "raise ValueError(f'Latest release must include {filename} and {filename}.sha256.')",
    "raise ValueError(f'Latest release must include {filename} plus {filename}.sha256 or {filename}-checksum.txt.')")
replace('agent/ui_updates.py',
    'After this one-time v0.5.4 installation, future versions can download from a GitHub Releases repository you trust. No more manually replacing ZIP contents.',
    'Automatic update checks are available. Trusted releases are downloaded, checksum verified, backed up and installed by the local supervisor.')
replace('agent/ui_updates.py',
    'Use a repository you own or explicitly trust. Releases must contain a versioned ZIP and matching .sha256 asset.',
    'Use a repository you own or explicitly trust. Releases must contain a versioned ZIP and a matching SHA-256 checksum asset.')
replace('agent/ui_updates.py',
    "3. Upload both `resell-agent-mvp-v0.5.5.zip` and `resell-agent-mvp-v0.5.5.zip.sha256`.\n4. The checksum file must contain the ZIP's SHA-256 digest (optionally followed by the ZIP filename).",
    '3. Upload both the versioned ZIP and its SHA-256 checksum file as **release Assets**, not release-note attachments.\n4. Checksum file: `resell-agent-mvp-vX.Y.Z.zip.sha256` or `resell-agent-mvp-vX.Y.Z.zip-checksum.txt`. The content must contain the SHA-256 digest, optionally followed by the ZIP filename.')
key = root + 'tests/test_updater.py'
files[key] = files[key].decode('utf-8').replace('0.5.5', '0.5.6').encode('utf-8')
files[root + 'UPGRADE_TO_V055.md'] = (
    '# Resell Agent v0.5.5 - update test\n\nUse the built-in updater in v0.5.4 to download, verify and install this release.\n'
    'This release adds compatibility with SHA-256 checksum TXT release assets.\n'
    'Keep the local database backed up and confirm the app reports v0.5.5 after restarting.\n'
).encode('utf-8')
archive = Path('resell-agent-mvp-v0.5.5.zip')
with ZipFile(archive, 'w', ZIP_DEFLATED) as z:
    for name, data in files.items():
        z.writestr(name, data)
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
Path(str(archive)+'.sha256').write_text(f'{digest}  {archive.name}\n', encoding='ascii')
print(f'Created {archive.name} with SHA-256: {digest}')
