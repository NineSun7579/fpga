"""Verify preserved receipt and exact production-byte extracts after execution."""
from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parent
sha = lambda data: hashlib.sha256(data).hexdigest()
manifest = json.loads((root / 'production_manifest.json').read_text())
source = (root.parent / 'src/main.cpp').read_bytes()
assert sha(source) == manifest['source_sha256']
for entry in manifest['extracts']:
    chunk = (root / (entry['name'] + '.inc')).read_bytes()
    assert len(chunk) == entry['bytes'] + 1
    assert chunk[-1:] == b'\n'
    assert sha(chunk[:-1]) == entry['sha256']
    assert chunk[:-1] in source
    assert source[:source.index(chunk[:-1])].count(b'\n') + 1 == entry['first_line']
receipt = json.loads((root / 'receipt.json').read_text())
for name, digest in receipt['files'].items():
    assert sha((root / name).read_bytes()) == digest, name
assert len(receipt['steps']) == 6
assert all(entry['exit_code'] == 0 for entry in receipt['steps'])
assert b'LOCAL_GATE_SELFTEST_PASS' in (root / 'test.log').read_bytes()
report = dict(result='LOCAL_RECEIPT_AUDIT_PASS', source_sha256=sha(source),
              receipt_sha256=sha((root / 'receipt.json').read_bytes()),
              verified_receipt_files=len(receipt['files']),
              verified_production_extracts=len(manifest['extracts']),
              documentation_sha256={name: sha((root / name).read_bytes())
                                    for name in ['README.md', 'audit.py']})
(root / 'audit.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
