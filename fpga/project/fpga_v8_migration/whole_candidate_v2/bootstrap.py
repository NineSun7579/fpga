"""Snapshot review tooling only; every write is confined to this new directory."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / 'whole_candidate'
for name in ['build_candidate.py', 'audit_candidate.py', 'run_pds.py', 'summarize_pds.py']:
    target = HERE / name
    assert not target.exists(), target
    target.write_bytes((OLD / name).read_bytes())
(HERE / 'artifacts').mkdir(exist_ok=True)
(HERE / 'artifacts/tooling_provenance.json').write_text(json.dumps({
    name: hashlib.sha256((OLD / name).read_bytes()).hexdigest()
    for name in ['build_candidate.py', 'audit_candidate.py', 'run_pds.py', 'summarize_pds.py']
}, indent=2), encoding='ascii')
