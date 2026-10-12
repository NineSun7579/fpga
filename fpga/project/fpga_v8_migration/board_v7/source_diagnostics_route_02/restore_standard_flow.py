from pathlib import Path
import json,hashlib,re,shutil
HERE=Path(__file__).resolve().parent
archive=HERE/'failed_custom_db_registration'
assert not archive.exists();archive.mkdir()
for p in [HERE/'project.pds',HERE/'run_native_physical.py']:
    shutil.copy2(p,archive/p.name)
for n in ['physical_registered_03','physical_registered_04']:
    shutil.copytree(HERE/n,archive/n)
hashes={str(p.relative_to(archive)):hashlib.sha256(p.read_bytes()).hexdigest() for p in archive.rglob('*') if p.is_file()}
(archive/'manifest.json').write_text(json.dumps(hashes,indent=2))
raw=(HERE/'project.pds').read_bytes()
def remove_expr(raw,token):
    while token in raw:
        start=raw.index(token);i=start;depth=0;quoted=False
        while i<len(raw):
            ch=raw[i]
            if ch==34:quoted=not quoted
            if not quoted:
                if ch==40:depth+=1
                elif ch==41:
                    depth-=1
                    if depth==0:break
            i+=1
        raw=raw[:start]+raw[i+1:]
    return raw
for opt in [b'(_option force_to_run',b'(_option input_db_file']:
    raw=remove_expr(raw,opt)
raw=re.sub(rb'\(_gci_state \(_integer \d+\)\)',b'(_gci_state (_integer 0))',raw)
(HERE/'standard_flow.pds').write_bytes(raw)
print('Standard TC05-style registered flow; normal source dependencies; actual dump preserved separately',flush=True)
