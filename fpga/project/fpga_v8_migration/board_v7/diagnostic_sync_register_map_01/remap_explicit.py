"""Force exact documented integer options against the actual isolated synthesis DB."""
from pathlib import Path
import json,shutil
import run
H=Path(__file__).resolve().parent;E=H/'evidence'
def main():
    run.wait_queue();run.verify()
    a=H/'attempts/06_default_map_options_unproven';a.mkdir()
    for n in ['mapping','mapping.log','mapping_result.json','mapping_launch.json','mapping_artifact.json','mapping_export_hashes.json','mapping_export.log','mapping_export_result.json','mapping_export_launch.json','mapping_topology.json','mapping_endpoint_details.json','final_result.json']:
        if (E/n).exists():shutil.move(str(E/n),str(a/n))
    shutil.move(str(H/'device_map'),str(a/'device_map'))
    # Later official -run stages recompiled earlier DBs. Preserve original exports and snapshot the actual latest upstream DBs.
    for label,folder,suffix,native in [('compile','compile','comp','cmr.db'),('synthesis','synthesize','syn','snr.db')]:
        for p in list(E.iterdir()):
            if p.name==label or p.name.startswith(label+'_export') or p.name==label+'_artifact.json':shutil.move(str(p),str(a/p.name))
        db=H/folder/('v7_sdt_top_'+suffix+'.adf');ndb=H/folder/native
        run.save(label+'_artifact.json',{'adf':str(db),'adf_sha256':run.sha(db),'native_db':str(ndb),'native_db_sha256':run.sha(ndb),'official_done_lines':['Process "'+('Compile' if label=='compile' else 'Synthesize')+'" done.'],'provenance':'Latest upstream DB generated during actual mapping.log in attempt06; prior individual-stage DB snapshot retained there.'})
        run.export(label,db)
    db=H/'synthesize/v7_sdt_top_syn.adf';before=run.sha(db)
    script=E/'map_explicit.tcl'
    command='dev_map -force_to_run -input_db_file {'+db.as_posix()+'} -top_module v7_sdt_top -devmap_remove_dups 0 -devmap_const_prop 0 -devmap_control_set_num 0'
    script.write_bytes((command+'\n').encode('ascii'))
    raw=run.run('mapping',[run.PDS,'-file',script,'-work_dir',H,'-project_name','project'])
    assert run.sha(db)==before,'Mapping altered upstream synthesis DB'
    mapped=H/'device_map/v7_sdt_top_map.adf';ndb=H/'device_map/dmr.db';assert mapped.exists() and ndb.exists()
    run.save('mapping_artifact.json',{'adf':str(mapped),'adf_sha256':run.sha(mapped),'native_db':str(ndb),'native_db_sha256':run.sha(ndb),'official_done_lines':[l.decode('ascii','backslashreplace') for l in raw.splitlines() if b'Process "' in l and b'done.' in l],'explicit_command':command})
    run.export('mapping',mapped)
    run.save('final_result.json',{'status':'PENDING_FINAL_AUDIT','options':{'devmap_remove_dups':0,'devmap_const_prop':0,'devmap_control_set_num':0},'disable_io_insertion':False,'compact_stimulus':True,'no_timing_relaxation':True,'routed':False,'remote_or_program':False,'protected_count':1022})
    import audit_final
    audit_final.main()
if __name__=='__main__':main()
