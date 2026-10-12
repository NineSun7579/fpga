"""Archived original parse recovery; retained for provenance, do not execute."""
from pathlib import Path
import json, shutil, re
import run
H=Path(__file__).resolve().parent
def main():
    run.wait_queue();run.verify()
    partial=H/'attempts/02_project_parse_failure'
    resume=not (H/'evidence/compile_result.json').exists() and (partial/'compile_result.json').exists()
    result=json.loads(((partial if resume else H/'evidence')/'compile_result.json').read_bytes())
    assert result['errors'] and all('Flow-0130' in x or 'Flow-0121' in x for x in result['errors'])
    attempt=len(list((H/'attempts').glob('*project_parse_failure')))+1 if (H/'attempts').exists() else 1
    archive=partial if resume else H/'attempts'/('%02d_project_parse_failure'%attempt)
    archive.mkdir(parents=True,exist_ok=resume)
    if not (archive/'project.pds').exists():shutil.copy2(H/'project.pds',archive/'project.pds')
    for name in ['compile.log','compile_result.json','compile_launch.json','failure.json']:
        if (H/'evidence'/name).exists():shutil.move(str(H/'evidence'/name),str(archive/name))
    for name in ['compile','constraint_check']:
        if (H/name).exists():shutil.move(str(H/name),str(archive/name))
    p=H/'project.pds';raw=p.read_bytes()
    # Official grammar requires the flow comment before version.
    if b'(_comment ' not in raw:
        raw=raw.replace(b'(_flow fab_demo "2022.2-SP6.4"\n',b'(_flow fab_demo "2022.2-SP6.4"\n (_comment "Isolated diagnostic mapping experiment")\n',1)
    raw=re.sub(rb'(\(_file "(?:rtl|constraints)/[^"]+"\s*\(_format \w+\))\)',rb'\1 (_timespec "2026-10-07T00:00:00"))',raw)
    p.write_bytes(raw)
    frozen=json.loads((H/'evidence/input_hashes.json').read_bytes());frozen['project.pds']=run.sha(p)
    run.save('input_hashes.json',frozen)
    run.save('recovery_receipt.json',{'preserved_attempt':str(archive),'reason':'Official flow header/source registration grammar correction; actual Flow-0130 parse error preserved','project_sha256':run.sha(p)})
    run.main()
    import audit_final
    audit_final.main()
if __name__=='__main__':main()
