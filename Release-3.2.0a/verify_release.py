"""Portable integrity check for the staged Release-3.2.0a sources (no workspace access)."""
import hashlib
import json
import re
import sys
from pathlib import Path

root = Path('D:/race/ov56401/project/cam5_resolution/release_3_2_0a/fpga_repo/Release-3.2.0a').resolve()
manifest = json.loads((root / 'SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
failures = []
for record in manifest['files']:
    path = root / record['path']
    if not path.is_file():
        failures.append('missing ' + record['path'])
        continue
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != record['sha256']:
        failures.append('hash mismatch ' + record['path'])
    if path.stat().st_size != record['bytes']:
        failures.append('size mismatch ' + record['path'])

# No absolute workspace paths inside the portable artifacts.
for path in (root / 'fpga50').rglob('*'):
    if path.suffix in ('.tcl', '.json', '.md'):
        data = path.read_text(errors='ignore')
        if 'D:\\race' in data or '/race/' in data:
            failures.append('absolute path in ' + path.relative_to(root).as_posix())

# Repo-level hygiene for the staged area.
assert '.git' not in {p.name for p in root.rglob('*')}
for pattern in ('*.bak*', '*.pyc', '*.sbit', '*.rtr', '*.log', '*.bin', '*.rgb565', '__pycache__'):
    for path in root.rglob('*'):
        if path.is_file() and path.name.endswith(pattern.strip('*')) or (path.is_dir() and path.name == pattern):
            failures.append('excluded artifact ' + path.relative_to(root).as_posix())

if failures:
    print('FAILURES')
    print('\n'.join(failures))
    sys.exit(1)
print('SOURCE_RELEASE_OK', len(manifest['files']), 'files,', sum(r['bytes'] for r in manifest['files']), 'bytes')
