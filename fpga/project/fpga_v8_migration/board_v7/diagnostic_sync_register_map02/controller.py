"""Run real isolated attribute experiment; never write another project's files."""
import json,traceback
from pathlib import Path
import run
H=Path(__file__).resolve().parent;E=H/'evidence'
def artifact(label,folder,suffix,native,raw,marker):
    db=H/folder/('v7_sdt_top_'+suffix+'.adf');ndb=H/folder/native
    assert db.is_file() and ndb.is_file()
    done=[l.decode('ascii','backslashreplace') for l in raw.splitlines() if ('Process "'+marker+'" done.').encode('ascii') in l]
    assert done,(label,'Missing exact official stage marker')
    run.save(label+'_artifact.json',{'adf':str(db),'adf_sha256':run.sha(db),'native_db':str(ndb),'native_db_sha256':run.sha(ndb),'official_done_lines':done})
    return db
def main():
    assert not (E/'final_result.json').exists()
    run.wait_queue();run.verify()
    if (E/'synthesis_export_hashes.json').exists():
        for label in ['compile','synthesis']:
            receipt=json.loads((E/(label+'_artifact.json')).read_bytes())
            assert all(run.sha(Path(receipt[k]))==receipt[k+'_sha256'] for k in ['adf','native_db'])
            exported=json.loads((E/(label+'_export_hashes.json')).read_bytes())
            assert exported['adf_sha256']==receipt['adf_sha256']
            assert run.sha(E/label/'analysis/graph.json')==exported['graph_sha256']
        rawcompile=(E/'compile.log').read_bytes();rawsyn=(E/'synthesis.log').read_bytes()
        run.save('resume_completed_stages.json',{'compile_synthesis_hashes_verified':True,'reason':'Resume mapping only after queue deadlock; no completed stage rerun'})
    else:
        rawcompile=run.run('compile',[run.PDS,'-project',H/'project.pds','-run','compile','-work_dir',H])
        rawsyn=run.run('synthesis',[run.PDS,'-project',H/'project.pds','-run','synthesize','-work_dir',H])
    # The project engine may rerun compile during synthesis. Hash/export the
    # actual final compile and synthesis DBs after both operations, never an old receipt.
    comp=artifact('compile','compile','comp','cmr.db',rawsyn if b'Process "Compile" done.' in rawsyn else rawcompile,'Compile')
    syn=artifact('synthesis','synthesize','syn','snr.db',rawsyn,'Synthesize')
    snapshots={str(p):run.sha(p) for p in [comp,syn,H/'compile/cmr.db',H/'synthesize/snr.db']}
    for label,db in [('compile',comp),('synthesis',syn)]:
        graph=json.loads((E/label/'analysis/graph.json').read_bytes()) if (E/(label+'_export_hashes.json')).exists() else run.export(label,db)
        run.audit(label,graph)
    script=E/'map.tcl'
    script.write_bytes(('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\nadd_constraint {'+(H/'constraints/clock.fdc').as_posix()+'}\ndev_map -force_to_run -input_db_file {'+syn.as_posix()+'} -devmap_remove_dups 0 -devmap_const_prop 0 -devmap_control_set_num 0\n').encode('ascii'))
    run.save('mapping_input_hashes.json',{'stage_DBs':snapshots,'map_tcl_sha256':run.sha(script),'clock_fdc_sha256':run.sha(H/'constraints/clock.fdc'),'project_at_mapping_sha256':run.sha(H/'project.pds')})
    rawmap=run.run('mapping',[run.PDS,'-file',script,'-work_dir',H])
    mapped=artifact('mapping','device_map','map','dmr.db',rawmap,'Device Map')
    graph=run.export('mapping',mapped)
    run.audit('mapping',graph,json.loads((E/'synthesis/analysis/graph.json').read_bytes()))
    assert all(run.sha(Path(p))==v for p,v in snapshots.items()),'Compile/synthesis DB mutated by mapping'
    run.verify()
    run.save('final_result.json',{'status':'PENDING_FINAL_AUDIT','experiment':H.name,'attribute':'syn_noprune=1','attribute_instances':60,'compact_stimulus':True,'disable_io_insertion':False,'options':{'devmap_remove_dups':0,'devmap_const_prop':0,'devmap_control_set_num':0},'no_timing_relaxation':True,'routed':False,'remote_or_program':False,'protected_count':len(json.loads((E/'protected_baseline.json').read_bytes())),'production_gate':'BLOCKED; map01 FAIL unchanged; no production integration or routed timing claim'})
    import audit_final
    audit_final.main()
if __name__=='__main__':
    try:main()
    except BaseException:
        failure={'status':'FAIL','traceback':traceback.format_exc(),'production_gate':'BLOCKED','routed':False,'remote_or_program':False}
        run.save('failure.json',failure);run.save('final_result.json',failure);raise
