"""Resume native08 through the exact physical mapping, without duplicate exports.

An existing exact09 controller owns remap/PNR/audit. Follow its real receipts;
never start another PDS or touch its project, inputs or analysis while running.
"""
from pathlib import Path
import subprocess, sys, json, shutil, time, traceback
import continue_fixed as cf
from run_native_fixed08 import OUT, ROOT, HERE, PDS, sha
from audit_actualmapping08 import main as local_audit

EXACT=ROOT/'physical_exact_09'

def save(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2),encoding='utf8')

def controllers():
    command="ConvertTo-Json -InputObject @(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'resume_exact09.py' } | Select-Object ProcessId,CommandLine) -Compress"
    r=subprocess.run(['powershell','-NoProfile','-Command',command],capture_output=True,check=True)
    return json.loads(r.stdout)

def wait_idle():
    while cf.busy() or controllers():
        print('WAIT existing serial PDS/controller; no active file edits',flush=True)
        time.sleep(10)

def ensure_original_export():
    actual=OUT/'actual';analysis=actual/'analysis';dump=actual/'synthesis_export/synthesis_dump.txt'
    if dump.exists():
        result=json.loads((OUT/'export_new_syn_result.json').read_bytes())
        pending=json.loads((OUT/'new_synthesis_pending.json').read_bytes())
        assert result['exit_code']==0 and not result['errors'] and dump.stat().st_size
        if (analysis/'manifest.json').exists():
            assert json.loads((analysis/'manifest.json').read_bytes())['source_dump_sha256']==sha(dump)
        save('export_reuse_receipt.json',{'historical_db_sha256':pending['after'],'dump_sha256':sha(dump),
            'current_db_matches':(HERE/'synthesize/v7_sdt_top_syn.adf').exists() and sha(HERE/'synthesize/v7_sdt_top_syn.adf')==pending['after'],
            'success_receipt_sha256':sha(OUT/'export_new_syn_result.json'),'reexported':False})
        return
    wait_idle();cf.idle();actual.mkdir(exist_ok=True);analysis.mkdir(exist_ok=True);dump.parent.mkdir(exist_ok=True)
    db=HERE/'synthesize/v7_sdt_top_syn.adf';h=sha(db);script=actual/'export.tcl'
    script.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n.switch_db -input {'+db.as_posix()+'} -output {'+dump.as_posix()+'}\n',encoding='ascii')
    cf.OUT=OUT;cf.run('export_new_syn',[str(PDS),'-file',str(script),'-work_dir',str(actual),'-project_name','native08_syn_graph'],actual)
    assert sha(db)==h and dump.stat().st_size
    save('new_synthesis_pending.json',{'after':h,'pnr_started':False})
    origin=ROOT/'native_probe_07/synthesize_actual/analysis'
    # The locally repaired derivation is retained, not overwritten by the old 320 assumption.
    for n in ['parse_objects.py','resolve_manifest.py','classify_paths.py','B_one_pair.sdc']:
        if not (analysis/n).exists():shutil.copy2(origin/n,analysis/n)
    for n in ['parse_objects.py','resolve_manifest.py']:
        with (OUT/('resume_'+n[:-3]+'.log')).open('wb') as log:
            r=subprocess.run([sys.executable,str(analysis/n)],stdout=log,stderr=subprocess.STDOUT)
        assert r.returncode==0

def follow_exact():
    save('serial_continuation.json',{'owner':'resume_exact09.py','path':str(EXACT),'duplicate_pds_started':False,
        'old_failure_archive':str(OUT/'actualmapping_failure_archive'),'status':'waiting for real PNR'})
    print('FOLLOW existing exact09 remap/PNR owner; no duplicate launch',flush=True)
    while controllers():
        if (EXACT/'pnr_launch.json').exists():
            result={'owner':'resume_exact09.py','path':str(EXACT),'pnr_launch':json.loads((EXACT/'pnr_launch.json').read_bytes()),
                'status':'PNR requested; require Process started/done and routed artifact','duplicate_pds_started':False}
            log=EXACT/'pnr.log'
            if log.exists() and b'Process "Place & Route" started.' in log.read_bytes():
                result['status']='real Place & Route started; controller continues routed full-coverage gates'
                save('serial_continuation.json',result)
        time.sleep(10)
    artifact=EXACT/'pnr_artifact.json'
    if not artifact.exists():
        raise RuntimeError('Exact09 controller stopped before routed artifact; inspect '+str(EXACT/'failure.txt'))
    route=json.loads(artifact.read_bytes());assert sha(Path(route['path']))==route['sha256']
    result=json.loads((EXACT/'pnr_result.json').read_bytes())
    assert result['exit_code']==0 and not result['errors']
    assert 'Process "Place & Route" started.' in result['marks'] and 'Process "Place & Route" done.' in result['marks']
    validated=json.loads((EXACT/'new_syn_validated.json').read_bytes())
    assert validated['physical_pairs']==1320 and validated['canonical_pairs']==1280
    save('serial_continuation.json',{'status':'real PNR completed','routed_artifact':route,'validated_mapping':validated,
        'duplicate_pds_started':False,'acceptance_gates_path':str(EXACT/'acceptance_gates.json'),
        'failure_path':str(EXACT/'failure.txt'),'remote_or_program':False})
    print('REAL PNR COMPLETED; acceptance is recorded by existing exact09 controller',flush=True)

def main():
    assert (OUT/'dev_map_artifact.json').exists()
    ensure_original_export()
    local_audit()
    if (EXACT/'dev_map_launch.json').exists():
        follow_exact();return
    wait_idle();cf.idle()
    # Exact09 regenerates phase-aware FDC, serially remaps, exports only the new DB,
    # proves all 1320 physical pairs and runs real PNR plus strict routed gates.
    r=subprocess.run([sys.executable,'-u',str(Path(__file__).with_name('resume_exact09.py'))])
    assert r.returncode==0,'Inspect physical_exact_09/failure.txt; no gate waiver'
    follow_exact()

if __name__=='__main__':
    try:main()
    except BaseException:
        (OUT/('resume_finish_failure_'+str(time.time_ns())+'.txt')).write_text(traceback.format_exc())
        raise
