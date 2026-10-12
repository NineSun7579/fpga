"""Documented submodule-style synthesis avoids package IO limits; keep all ports."""
from pathlib import Path
import json,re,shutil
import run
H=Path(__file__).resolve().parent;E=H/'evidence'
def main():
    run.wait_queue();run.verify()
    initial=(E/'mapping_result.json').exists()
    old=E/('mapping_result.json' if initial else 'synthesis_result.json');r=json.loads(old.read_bytes())
    assert any('DRC-0018' in x or "Only one of '-file' or '-project'" in x for x in r['errors'])
    archive=H/'attempts'/('03_io_limit_and_invalid_open_project' if initial else '04_exclusive_cli_modes');archive.mkdir()
    for name in ['synthesize','device_map']:
        if (H/name).exists():shutil.move(str(H/name),str(archive/name))
    for p in list(E.iterdir()):
        if p.name.startswith(('synthesis','mapping')) or p.name=='map.tcl':shutil.move(str(p),str(archive/p.name))
    shutil.copy2(H/'project.pds',archive/'project.pds')
    raw=(H/'project.pds').read_bytes()
    # Leave compile unchanged; reset synth/map phases and set the documented switch.
    start=raw.index(b'(_task tsk_synthesis')
    tail=re.sub(rb'\(_gci_state \(_integer \d+\)\)',b'(_gci_state (_integer 0))',raw[start:])
    if b'(_option disable_io_insertion' not in tail:tail=tail.replace(b'(_command cmd_synthesize',b'(_command cmd_synthesize\n (_option disable_io_insertion (_switch ON))',1)
    (H/'project.pds').write_bytes(raw[:start]+tail)
    hashes=json.loads((E/'input_hashes.json').read_bytes());hashes['project.pds']=run.sha(H/'project.pds');run.save('input_hashes.json',hashes)
    import fitz
    pdf=Path('C:/pango/PDS_2022.2-SP6.4/doc/ADS_Synthesis_User_Guide.pdf')
    d=fitz.open(pdf)
    run.save('disable_io_official_evidence.json',{'pdf':str(pdf),'sha256':run.sha(pdf),'pages':{str(i+1):d[i].get_text() for i in [15,19,51]},'intent':'Submodule-style mapping experiment, all top input/output ports retained; no package IO insertion. No storage packing or timing relaxation.'})
    for label,command,folder,suffix,native in [('synthesis','synthesize -ads -disable_io_insertion','synthesize','syn','snr.db'),('mapping','dev_map -devmap_remove_dups 0 -devmap_const_prop 0 -devmap_control_set_num 0','device_map','map','dmr.db')]:
        script=E/(label+'_noio.tcl');script.write_bytes((command+'\n').encode('ascii'))
        rawlog=run.run(label,[run.PDS,'-project',H/'project.pds','-run','synthesize' if label=='synthesis' else 'dev_map','-work_dir',H])
        db=H/folder/('v7_sdt_top_'+suffix+'.adf');ndb=H/folder/native
        assert db.is_file() and ndb.is_file()
        run.save(label+'_artifact.json',{'adf':str(db),'adf_sha256':run.sha(db),'native_db':str(ndb),'native_db_sha256':run.sha(ndb),'official_done_lines':[l.decode('ascii','backslashreplace') for l in rawlog.splitlines() if b'Process "' in l and b'done.' in l]})
        g=run.export(label,db);run.audit(label,g)
    run.save('final_result.json',{'status':'PENDING_FINAL_AUDIT','options':{'devmap_remove_dups':0,'devmap_const_prop':0,'devmap_control_set_num':0},'disable_io_insertion':True,'no_timing_relaxation':True,'routed':False,'remote_or_program':False,'protected_count':1022})
    import audit_final
    audit_final.main()
if __name__=='__main__':main()
