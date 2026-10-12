"""Resume only mapping, with proven explicit DB/constraint API; preserve all evidence."""
from pathlib import Path
import json, shutil, time, traceback
import run
H=Path(__file__).resolve().parent
E=H/'evidence'

def main():
    # Wait for the already-started map01 recovery as well as actual PDS idle.
    while any(p['Name'].lower() in {'pds.exe','pds_shell.exe','ta.exe'} or
              (p['Name'].lower() in {'python.exe','pythonw.exe'} and any(s in (p.get('CommandLine') or '') for s in ['resume_noio.py','resume_compact.py']))
              for p in run.processes()):
        time.sleep(5)
    run.wait_queue();run.verify()
    syn=H/'synthesize/v7_sdt_top_syn.adf'
    art=json.loads((E/'synthesis_artifact.json').read_bytes())
    # Project-mode predecessors may have rerun a stage and changed serialized DB
    # bytes. Preserve the stale receipt/export, never silently relabel its graph.
    refresh=[]
    for label,folder,suffix,native,marker in [('compile','compile','comp','cmr.db','Compile'),('synthesis','synthesize','syn','snr.db','Synthesize')]:
        receipt=json.loads((E/(label+'_artifact.json')).read_bytes())
        db=H/folder/('v7_sdt_top_'+suffix+'.adf');ndb=H/folder/native
        if run.sha(db)==receipt['adf_sha256'] and run.sha(ndb)==receipt['native_db_sha256']:continue
        logs=[p for p in [E/'mapping.log',E/'synthesis.log',E/'compile.log'] if p.exists() and ('Process "'+marker+'" done.').encode('ascii') in p.read_bytes()]
        assert logs,'No real stage completion evidence for changed '+label+' DB'
        old=H/'attempts'/('completed_'+label+'_receipt_before_project_rerun_'+str(int(time.time())))
        old.mkdir()
        shutil.copy2(db,old/db.name);shutil.copy2(ndb,old/native)
        completion=old/'project_continuation_completion.log';shutil.copy2(logs[0],completion)
        for p in list(E.iterdir()):
            if p.name.startswith(label) and p.name not in {label+'.log',label+'_launch.json',label+'_result.json',label+'_noio.tcl'}:
                shutil.move(str(p),str(old/p.name))
        run.save(label+'_artifact.json',{'adf':str(db),'adf_sha256':run.sha(db),'native_db':str(ndb),'native_db_sha256':run.sha(ndb),'official_done_lines':['Process "'+marker+'" done.'],'completion_log':str(completion),'completion_log_sha256':run.sha(completion),'previous_receipt':receipt,'reason':'Earlier project-mode continuation regenerated stage DB; original receipt and export preserved; current DB independently re-exported'})
        graph=run.export(label,db);run.audit(label,graph)
        refresh.append({'stage':label,'archive':str(old),'old_adf_sha256':receipt['adf_sha256'],'current_adf_sha256':run.sha(db)})
    assert run.sha(syn)==json.loads((E/'synthesis_artifact.json').read_bytes())['adf_sha256']
    frozen={str(p):run.sha(p) for p in [syn,H/'synthesize/snr.db',H/'compile/v7_sdt_top_comp.adf',H/'constraints/clock.fdc']}
    archive=H/'attempts'/('05_mapping_options_not_executed_'+str(int(time.time())))
    archive.mkdir()
    for name in ['device_map']:
        if (H/name).exists():shutil.move(str(H/name),str(archive/name))
    for p in list(E.iterdir()):
        if p.name.startswith('mapping') or p.name in {'final_result.json','failure.json'}:
            shutil.move(str(p),str(archive/p.name))
    if (H/'REPORT.md').exists():shutil.copy2(H/'REPORT.md',archive/'REPORT.md')
    script=E/'map.tcl'
    script.write_bytes(('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n'
        'add_constraint {'+(H/'constraints/clock.fdc').as_posix()+'}\n'
        'dev_map -force_to_run -input_db_file {'+syn.as_posix()+'} -devmap_remove_dups 0 -devmap_const_prop 0 -devmap_control_set_num 0\n').encode('ascii'))
    sources=[H.parent/'physical_subagent_evidence_01/fixed_06/stage_map13/map.tcl',H.parent/'diagnostic_sync_register_timing_candidate/docs/stored_stage_api12_shell.log']
    run.save('mapping_recovery_receipt.json',{'archive':str(archive),'unchanged_stage_inputs':frozen,'prior_project_regeneration_review':refresh,'script_sha256':run.sha(script),'official_api_evidence':{str(p):run.sha(p) for p in sources},'reason':'Explicit synthesized DB and five-clock constraint context; all three supported integer options actually executed. No RTL changes by this recovery.'})
    print('真实 mapping：保留 compile/synthesis，使用已验证 DB/约束接口及三个整数选项',flush=True)
    raw=run.run('mapping',[run.PDS,'-file',script,'-work_dir',H])
    done=[l.decode('ascii','backslashreplace') for l in raw.splitlines() if b'Process "Device Map" done.' in l]
    assert done,'Missing official Device Map completion'
    db=H/'device_map/v7_sdt_top_map.adf';native=H/'device_map/dmr.db'
    assert db.is_file() and native.is_file()
    run.save('mapping_artifact.json',{'adf':str(db),'adf_sha256':run.sha(db),'native_db':str(native),'native_db_sha256':run.sha(native),'official_done_lines':done})
    g=run.export('mapping',db)
    reference=json.loads((E/'synthesis/analysis/graph.json').read_bytes())
    topology=run.audit('mapping',g,reference)
    assert all(run.sha(Path(p))==v for p,v in frozen.items()),'Completed stage input drift'
    run.verify()
    run.save('final_result.json',{'status':'PENDING_FINAL_AUDIT','options':{'devmap_remove_dups':0,'devmap_const_prop':0,'devmap_control_set_num':0},'disable_io_insertion':b'(_option disable_io_insertion (_switch ON))' in (H/'project.pds').read_bytes(),'compact_stimulus':(E/'compact_stimulus_receipt.json').exists(),'no_timing_relaxation':True,'routed':False,'remote_or_program':False,'protected_count':len(json.loads((E/'protected_baseline.json').read_bytes()))})
    import audit_final
    audit_final.main()
    print('独立 audit 完成；真实独立寄存器数：',topology['independent_registers'],flush=True)

if __name__=='__main__':
    try:main()
    except BaseException:
        run.save('failure.json',{'traceback':traceback.format_exc(),'remote_or_program':False})
        run.save('final_result.json',{'status':'FAIL','tool_or_recovery_failure':True,'traceback':traceback.format_exc(),'remote_or_program':False,'routed':False})
        raise
