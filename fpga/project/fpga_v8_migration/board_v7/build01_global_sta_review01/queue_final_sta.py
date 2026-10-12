"""Low priority observer; waits for complete prior lifecycles before acquiring PDS."""
from pathlib import Path
import ctypes, hashlib, importlib.util, json, os, re, subprocess, sys, time, traceback
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
BUILD = HERE.parent / 'source_diagnostics_timing_build_01'
PDS = Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')
SCOPES = ['diagnostic_sync_register_map_01/', 'source_diagnostics_timing_build_02/', 'source_diagnostics_route_03/', 'source_diagnostics_timing_build_01/']
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def write(n,v): (HERE/n).write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
def processes():
    cmd='ConvertTo-Json -InputObject @(Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,CommandLine) -Compress'
    return json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',cmd]) or b'[]')
def blockers(rows):
    busy=[]
    for p in rows:
        if p['ProcessId']==os.getpid():continue
        name=p['Name'].lower();cmd=(p.get('CommandLine') or '').replace('\\','/').lower()
        if name in {'pds.exe','pds_shell.exe','ta.exe'}:busy.append(p)
        elif name in {'python.exe','pythonw.exe'} and any(s in cmd for s in SCOPES) and '.py' in cmd:busy.append(p)
    return busy
def main():
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p];kernel.CreateMutexW.restype=ctypes.c_void_p
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    kernel.GetCurrentProcess.restype=ctypes.c_void_p
    kernel.SetPriorityClass.argtypes=[ctypes.c_void_p,ctypes.c_uint]
    kernel.SetPriorityClass(kernel.GetCurrentProcess(),0x40)
    own=kernel.CreateMutexW(None,True,'Global\\ov56401_build01_global_sta_review01')
    assert own and ctypes.get_last_error()!=183,'Duplicate review controller'
    receipt=json.loads((BUILD/'evidence/pnr_artifact.json').read_bytes());route=Path(receipt['path'])
    inputs=json.loads((BUILD/'evidence/input_hashes.json').read_bytes())
    def verify():
        assert sha(route)==receipt['sha256'],'Actual route drift'
        for name,h in inputs.items():assert sha(BUILD/name)==h,'Frozen input drift: '+name
    verify()
    last=None
    while True:
        busy=blockers(processes());state=tuple(p['ProcessId'] for p in busy)
        if state!=last:
            write('queue_status.json',{'phase':'WAIT_COMPLETE_PRIOR_LIFECYCLES','pid':os.getpid(),'busy':busy,'scopes':SCOPES,'time':time.time(),'holds_pds_slot':False});last=state
            print('Waiting complete controllers/tools:',state,flush=True)
        if busy:time.sleep(5);continue
        # Two full scans avoid a transient tool gap; a live controller always blocks.
        time.sleep(2)
        if blockers(processes()):continue
        lease=kernel.CreateMutexW(None,True,'Global\\ov56401_PDS_single_instance')
        if not lease or ctypes.get_last_error()==183:
            if lease:kernel.CloseHandle(lease)
            time.sleep(5);continue
        if blockers(processes()):kernel.CloseHandle(lease);continue
        break
    try:
        verify()
        dest=HERE/'final_sta';dest.mkdir(exist_ok=False)
        command='report_timing -input_db_file {'+route.as_posix()+'} -force_to_run -delay_type min_max -nworst 1 -max_path 200000 -slack_less_than 0 -input_pins TRUE -report_exception FALSE'
        script=HERE/'report_global.tcl'
        script.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n'+command+'\n',encoding='ascii')
        args=[str(PDS),'-file',str(script),'-work_dir',str(dest),'-project_name','build01_global_sta_review01']
        write('queue_status.json',{'phase':'RUN_FINAL_STA','pid':os.getpid(),'command':args,'route':receipt,'time':time.time(),'holds_pds_slot':True})
        with (HERE/'final_sta.log').open('xb') as f:result=subprocess.run(args,cwd=dest,stdout=f,stderr=subprocess.STDOUT)
        verify()
        raw=(HERE/'final_sta.log').read_bytes()
        errors=[x.decode('ascii','backslashreplace') for x in raw.splitlines() if x.startswith(b'E:') or re.search(rb'Timing-4006|STA-3016|unknown\s+(?:arguments?|options?)',x,re.I)]
        write('final_sta_receipt.json',{'exit_code':result.returncode,'errors':errors,'route_unchanged':sha(route)==receipt['sha256'],'all_original_inputs_verified':True,'time':time.time()})
        assert result.returncode==0 and not errors,'Actual final STA failure'
        spec=importlib.util.spec_from_file_location('original_summary',HERE.parent.parent/'whole_candidate_v2_route_01/summarize_route.py');summary=importlib.util.module_from_spec(spec);spec.loader.exec_module(summary)
        summary.EVIDENCE=HERE/'final_native_tables';summary.EVIDENCE.mkdir()
        db=dest/'report_timing/rtr.db';tables=summary.extract(db,'final_sta');write('final_native_tables.json',tables)
        reports=list((dest/'report_timing').glob('*.rtr'))
        assert len(reports)==1,'Expected unique final detailed report'
        import runpy
        runpy.run_path(str(HERE/'finish_offline.py'),run_name='__main__')
    finally:kernel.CloseHandle(lease);kernel.CloseHandle(own)
if __name__=='__main__':
    try:main()
    except BaseException:
        (HERE/'failure.txt').write_text(traceback.format_exc(),encoding='utf8')
        write('queue_status.json',{'phase':'FAILED_EVIDENCE_PRESERVED','pid':os.getpid(),'time':time.time(),'holds_pds_slot':False})
        raise
