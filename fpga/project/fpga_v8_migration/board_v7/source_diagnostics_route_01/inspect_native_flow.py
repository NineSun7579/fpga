from pathlib import Path
from pypdf import PdfReader
import json, hashlib, shutil
HERE = Path(__file__).resolve().parent
OUT = HERE / 'physical_flow_audit_05'
OUT.mkdir(exist_ok=True)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
archive = OUT / 'failed_current_snapshot'
archive.mkdir(exist_ok=True)
files = [p for folder in ['physical_02','physical_03'] for p in (HERE/folder).rglob('*') if p.is_file()]
files += [p for p in HERE.iterdir() if p.suffix in ('.py','.tcl','.pds')]
files += list((HERE/'physical_constraints').glob('*'))
manifest = {}
for p in files:
    rel = p.relative_to(HERE); target = archive/rel
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists(): shutil.copy2(p,target)
    manifest[str(rel)] = {'current_sha256':sha(p),'snapshot_sha256':sha(target),'bytes':p.stat().st_size}
(OUT/'archive_manifest.json').write_text(json.dumps(manifest,indent=2))
dbs = [dict(path=str(p.relative_to(HERE)),bytes=p.stat().st_size,sha256=sha(p)) for p in HERE.rglob('*') if p.is_file() and p.suffix in ('.adf','.db') and OUT not in p.parents]
(OUT/'db_inventory.json').write_text(json.dumps(dbs,indent=2))
docs=Path('C:/pango/PDS_2022.2-SP6.4/doc')
for name,terms in [('Pango_Design_Suite_User_Guide.pdf',['-run','dev_map','device_map','input_db_file','of_flow']),('Timing_Analyzer_User_Guide.pdf',['-hierarchical','-hsc','get_pins','separator']),('User_Constraint_Editor_User_Guide.pdf',['get_pins','hierarchical'])]:
    chunks=[]
    for i,page in enumerate(PdfReader(docs/name).pages):
        text=page.extract_text() or ''
        if any(t in text for t in terms):chunks.append('PAGE '+str(i+1)+'\n'+text)
    (OUT/(name+'.txt')).write_text('\n'.join(chunks),encoding='utf8')
print('audit',OUT, 'DBs',len(dbs),flush=True)
