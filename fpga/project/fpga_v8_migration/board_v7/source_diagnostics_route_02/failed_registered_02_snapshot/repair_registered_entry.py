from pathlib import Path
import json,hashlib,shutil,re
HERE=Path(__file__).resolve().parent
archive=HERE/'failed_registered_02_snapshot'
assert not archive.exists()
files=[p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
hashes={}
for p in files:
    rel=p.relative_to(HERE);target=archive/rel;target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(p,target);hashes[str(rel)]=hashlib.sha256(p.read_bytes()).hexdigest()
(archive/'archive_manifest.json').write_text(json.dumps(hashes,indent=2))
p=HERE/'project.pds';raw=p.read_bytes()
raw=re.sub(rb'\(_gci_state \(_integer \d+\)\)',b'(_gci_state (_integer 0))',raw)
raw=raw.replace(b'(_file "recovered_actual_syn.adf"\n                      (_format text)',b'(_file "recovered_actual_syn.adf"\n                      (_format adif)')
p.write_bytes(raw)
print('Archived empty-success registration; reset states; DB format adif; retry actual device_map selector',flush=True)
