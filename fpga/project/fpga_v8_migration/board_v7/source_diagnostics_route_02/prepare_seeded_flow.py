from pathlib import Path
import json,hashlib,shutil,re,datetime
HERE=Path(__file__).resolve().parent
archive=HERE/'failed_standard_05';assert not archive.exists();archive.mkdir()
hashes={}
for folder in ['physical_standard_05','compile','constraint_check']:
    if (HERE/folder).exists():
        shutil.copytree(HERE/folder,archive/folder)
for p in [HERE/'standard_flow.pds',HERE/'physical_constraints/clock.fdc']:
    shutil.copy2(p,archive/p.name)
for p in archive.rglob('*'):
    if p.is_file():hashes[str(p.relative_to(archive))]=hashlib.sha256(p.read_bytes()).hexdigest()
(archive/'manifest.json').write_text(json.dumps(hashes,indent=2))
recovered=HERE/'recovered_actual_syn.adf';assert recovered.is_file()
(HERE/'synthesize').mkdir(exist_ok=True)
db=HERE/'synthesize/v7_sdt_top_syn.adf';shutil.copy2(recovered,db)
# Register a real existing synthesis output, rather than the unverified input_db_file option.
now=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
raw=(HERE/'standard_flow.pds').read_bytes()
for cmd in [b'cmd_compile',b'cmd_synthesize']:
    pattern=rb'(\(_command '+cmd+rb'\s*\(_gci_state \(_integer )\d+(\)\))'
    raw,n=re.subn(pattern,rb'\g<1>2\g<2>',raw);assert n==1
addition=b'\n            (_db_output (_file "synthesize/v7_sdt_top_syn.adf" (_format adif) (_timespec "'+now.encode()+b'")))'
raw=raw.replace(b'(_command cmd_synthesize',b'(_command cmd_synthesize'+addition)
raw=raw.replace(b'(_command cmd_devmap\n            (_gci_state (_integer 2))',b'(_command cmd_devmap\n            (_gci_state (_integer 0))')
(HERE/'seeded_flow.pds').write_bytes(raw)
(HERE/'seeded_manifest.json').write_text(json.dumps({'registered_actual_db':str(db),'db_sha256':hashlib.sha256(db.read_bytes()).hexdigest(),'recovered_source_sha256':hashlib.sha256(recovered.read_bytes()).hexdigest(),'seeded_project_sha256':hashlib.sha256(raw).hexdigest(),'constraint_sha256':hashlib.sha256((HERE/'physical_constraints/clock.fdc').read_bytes()).hexdigest(),'validation_pending':True},indent=2))
print('Prepared actual DB as normal synthesis _db_output; no custom DB-input command options',flush=True)
