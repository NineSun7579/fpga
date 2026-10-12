"""Seal existing successful evidence without re-running simulation."""
from pathlib import Path
import json,hashlib
P=Path(__file__).resolve().parent
checks={
 'compile.log':'Errors: 0, Warnings: 0',
 'elaboration.log':'TOP_ELAB_PASS',
 'top_simulation.log':'SDT_ALL_PASS checks=14540',
 'source_regression.log':'SFD_ALL_PASS',
 'unit_regression/tb_v7_sdb.log':'SDB_ALL_PASS checks=11986',
 'unit_regression/corrected_bus.log':'SDB_ALL_PASS checks=11986',
 'unit_regression/tb_v7_sfd_candidate.log':'SFD_ALL_PASS',
}
for name,token in checks.items():
 text=(P/name).read_text()
 assert token in text and '** Fatal' not in text and '** Error:' not in text,name
for name in ['input_pins.json','source_hashes.json','compiled_hashes.json']:
 for path,digest in json.loads((P/name).read_text()).items():
  assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest,path
audit=json.loads((P/'audit.json').read_text())
assert not audit['new_module_conflicts'] and audit['elaborated_instances']==932
assert len(json.loads((P/'physical_hierarchy.json').read_text()))==68
files=set(P/name for name in checks)
files.update(f for f in P.iterdir() if f.is_file() and f.suffix in ['.py','.v','.sv','.vh','.md','.json','.csv','.diff','.f','.do','.txt'] and f.name!='verification.json')
(P/'verification.json').write_text(json.dumps({'result':'PASS','checked_logs':checks,'artifacts':{str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(files)}},indent=2))
print('SDT_EVIDENCE_PASS',len(files),'artifacts')
