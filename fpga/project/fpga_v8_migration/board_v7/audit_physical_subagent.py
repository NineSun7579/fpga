from pathlib import Path
import hashlib,json,shutil,re
import fitz

HERE=Path(__file__).resolve().parent
OUT=HERE/'physical_subagent_evidence_01'
OUT.mkdir(exist_ok=False)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,v): (OUT/n).write_text(json.dumps(v,indent=2,ensure_ascii=False),encoding='utf8')

source=HERE/'source_diagnostics_route_01/physical_04'
shutil.copytree(source,OUT/'route01_physical04_failed')
save('route01_physical04_archive.json',{'files':{str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()},'exit_code':1,'mapped_db_exists':False,'routed_db_exists':False,'failure':'Flow-0182: option top_module is not support for the device; Actual mapped DB missing'})
for name in ['Pango_Design_Suite_User_Guide','User_Constraint_Editor_User_Guide']:
    doc=fitz.open('C:/pango/PDS_2022.2-SP6.4/doc/'+name+'.pdf')
    hits=[]
    for i,page in enumerate(doc):
        text=page.get_text()
        terms=['pds_shell','-run','dev_map','get_pins','hierarchical']
        if any(t in text for t in terms): hits.append({'pdf_page':i+1,'text':text})
    save(name+'_extract.json',hits)
guard=HERE/'source_diagnostics_route_01/build01_guard.json'
manifest=json.loads(guard.read_bytes())
changed=[];missing=[]
for name,expected in manifest.items():
    p=Path(name)
    if not p.is_file():missing.append(name)
    elif sha(p)!=expected:changed.append(name)
save('build01_protection_check.json',{'manifest':str(guard),'checked':len(manifest),'changed':changed,'missing':missing})
old=HERE.parent/'whole_candidate_v7_route_01'
names=['impl.tcl','project.pds','pnr_shell.log','flow_result.json','device_map/fpga_v8_cooperative_top_v2_rfg01_map.adf','place_route/fpga_v8_cooperative_top_v2_rfg01_pnr.adf']
save('old_v7_evidence.json',{name:{'bytes':(old/name).stat().st_size,'sha256':sha(old/name)} for name in names})
marks=[line.decode('ascii','backslashreplace') for line in (old/'pnr_shell.log').read_bytes().splitlines() if line.startswith(b'Process "') or line.startswith(b'Design ')]
save('old_v7_stage_marks.json',marks)
print(json.dumps({'output':str(OUT),'protected_checked':len(manifest),'changed':changed,'missing':missing},ensure_ascii=False),flush=True)
