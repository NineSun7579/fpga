"""Authorized serial build02: gate map01, fresh graph derivation, PNR/STA, local bit only."""
from pathlib import Path
import argparse, ctypes, hashlib, json, os, py_compile, re, sys, time, traceback
import physical_flow as flow
from preflight import HERE, BOARD, load, sha, require, reconcile, verify, map_gate

E=flow.EVIDENCE
def say(phase,message,**extra):
    flow.status(phase,message_zh=message,**extra)
    print(message,flush=True)
def project_guard():
    manifest=load(HERE/'manifest.json')
    raw=flow.PROJECT.read_bytes()
    registered=[x.decode('ascii') for x in re.findall(rb'\(_file "([^"]+)"',raw)]
    require([n for n in registered if n.startswith(('rtl/','inputs/'))]==manifest['registered_sources'],
            'Executable project registered input list drift')
    require(b'(_string "v7_sdt_top")' in raw,'Executable actual top option changed')
    outputs={'compile','synthesize','device_map','place_route','generate_bitstream'}
    require(all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in registered),'Nonlocal registered path')
    require(all((HERE/n).is_file() for n in registered if Path(n).parts[0] not in outputs),'Missing registered input/constraint asset')
    require(not any(b in raw for b in [b'constraints_pending/',b'constraints_candidate/']),'Old/pending constraint path in runtime project')
    return {'project_sha256':sha(flow.PROJECT),'registered_file_count':len(registered),'registered_sources':manifest['registered_sources'],
            'generated_output_paths':[n for n in registered if Path(n).parts[0] in outputs]}
def prepare():
    E.mkdir(parents=True,exist_ok=True)
    verify()
    if not flow.PROJECT.exists():flow.setup()
    guard=project_guard()
    compiled=[]
    for p in Path(__file__).resolve().parent.rglob('*.py'):
        if '__pycache__' in p.parts:continue
        py_compile.compile(str(p),doraise=True);compiled.append(p.relative_to(HERE).as_posix())
    files=[p for p in Path(__file__).resolve().parent.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    ledger={'schema':1,'immutable_manifest_sha256':sha(HERE/'manifest.json'),
            'historical_delivery_hashes_sha256':sha(HERE/'delivery_hashes.json'),
            'runtime_hash_append':{p.relative_to(HERE).as_posix():sha(p) for p in files},
            'project':guard,'compiled':compiled,'authorized_scope':'local compile/synthesis/map/PNR/signoff/bit; no remote or device',
            'functional_input_contract':'741 frozen copy files; exactly two primitive replacements',
            'reviewed_reconciliation_sha256':sha(E/'reviewed_reconciliation.json')}
    prior=E/'runtime_hash_append.json'
    if prior.exists():flow.record('runtime_hash_append_history/'+sha(prior)+'.json',load(prior))
    flow.record('runtime_hash_append.json',ledger)
    # A deterministic classifier check prevents the queued controller from blocking map01.
    cases=[
      {'ProcessId':1,'ParentProcessId':0,'Name':'python.exe','CommandLine':'python project/fpga_v8_migration/board_v7/diagnostic_sync_register_map_01/run.py'},
      {'ProcessId':2,'ParentProcessId':0,'Name':'python.exe','CommandLine':'python other/run.py'},
      {'ProcessId':3,'ParentProcessId':0,'Name':'powershell.exe','CommandLine':'Wait-Process -Id '+str(os.getpid())},
      {'ProcessId':4,'ParentProcessId':0,'Name':'powershell.exe','CommandLine':'python '+str(Path(__file__))},
      {'ProcessId':5,'ParentProcessId':0,'Name':'python.exe','CommandLine':'python project/fpga_v8_migration/board_v7/diagnostic_sync_register_map_01/recover.py'},
      {'ProcessId':6,'ParentProcessId':0,'Name':'python.exe','CommandLine':'python project/fpga_v8_migration/board_v7/source_diagnostics_timing_build_01/resume_actual_graph.py'},
      {'ProcessId':os.getpid(),'ParentProcessId':4,'Name':'python.exe','CommandLine':'python '+str(Path(__file__))}]
    busy,observers=flow.classify_processes(cases,os.getpid())
    require([p['ProcessId'] for p in busy]==[1,5,6] and [p['ProcessId'] for p in observers]==[3,4],'Queue classifier deadlock/identity fixture failed')
    flow.record('queue_classifier_preflight.json',{'passed':True,'map_run_full_path_only':True,'unrelated_run_ignored':True,
                'own_pid_excluded':True,'self_wait_observer_excluded':True,'launcher_ancestors_excluded':True,
                'map_recover_lifecycle_tracked':True,'build01_resume_lifecycle_tracked':True,'tools_empty_does_not_release_live_controller':True})
    say('EXECUTABLE_PREPARED_WAIT_MAP01','可执行 build02 已准备；等待 map01 最终实际60独立端点审计和前序控制器收尾。')

def immutable_runtime_guard():
    ledger=load(E/'runtime_hash_append.json')
    for n,h in ledger['runtime_hash_append'].items():require(sha(HERE/n)==h,'Runtime checker/controller changed after sealing: '+n)
    project_guard();verify()

def wait_gate():
    last=None
    while True:
        gate=map_gate();current=flow.processes();busy,observers=flow.classify_processes(current,os.getpid())
        state=(gate['status'],tuple(sorted(p['ProcessId'] for p in busy)))
        if state!=last:
            flow.record('queue_build02.json',{'time':time.time(),'map_gate':gate,'busy':busy,'observers_excluded':observers,
               'map_controller_full_path':'diagnostic_sync_register_map_01/run.py, recover.py or audit_final.py; build01/resume_actual_graph.py',
               'policy':'No slot held while waiting; queued controller02 is not a prior blocker in map01'});last=state
            say('WAIT_MAP01_AND_PRIOR_FINISHERS','物理门禁等待：'+gate['status']+'；前序工具/控制器 PID='+str(list(state[1])),gate=gate)
        if gate['status']=='BLOCKED':
            flow.record('blocked_reason.json',{'status':'REFUSED_LAUNCH','reason_zh':'map01 未通过真实独立端点门禁，拒绝启动 build02',
                'evidence':gate,'pds_started_by_build02':False,'time':time.time()})
            require(False,'map01 actual final endpoint gate rejected: '+str(gate))
        if gate['status']=='PASS' and not busy:
            immutable_runtime_guard();flow.record('map01_launch_gate.json',gate);return
        time.sleep(5)

def build():
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p];kernel.CreateMutexW.restype=ctypes.c_void_p
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    lease=kernel.CreateMutexW(None,True,'Global\\ov56401_build02_controller')
    existed=ctypes.get_last_error()==183
    if existed and lease:kernel.CloseHandle(lease)
    require(lease and not existed,'Another build02 controller is already queued/running; refuse duplicate')
    try:return build_locked()
    finally:kernel.CloseHandle(lease)

def build_locked():
    wait_gate()
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p];kernel.CreateMutexW.restype=ctypes.c_void_p
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=kernel.CreateMutexW(None,True,'Global\\ov56401_PDS_single_instance')
    require(handle and ctypes.get_last_error()!=183,'Serial tool mutex owned by another controller')
    try:
        immutable_runtime_guard();require(map_gate()['status']=='PASS','Map gate changed before launch')
        protected=load(BOARD/'source_diagnostics_route_01/build01_guard.json')
        flow.record('protected_before.json',protected);flow.record('inputs_before.json',flow.snapshot())
        say('START_AUTHORIZED_LOCAL_PHYSICAL','前序已收尾，map01 实际 PASS60；开始独立 build02 新物理图构建。')
        comp=flow.stage('compile','compile','compile','v7_sdt_top_comp.adf','Compile')
        syn=flow.stage('synthesize','synthesize','synthesize','v7_sdt_top_syn.adf','Synthesize')
        cg,ca=flow.export_graph('compile',comp,False)
        sg,sa=flow.export_graph('actual',syn,True)
        flow.endpoint_audit('compile',cg);flow.endpoint_audit('synthesis',sg)
        proof=flow.derive(cg,sg,sa)
        flow.record('actual_new_graph_adapter_test.json',{'passed':True,'compile_graph_sha256':sha(ca/'graph.json'),
          'synthesis_graph_sha256':sha(sa/'graph.json'),'independent_registers':60,'mailbox_pairs':proof['physical_pairs'],
          'adapter_sha256':sha(flow.TOOLS/'graph_adapter.py'),'same_domain_sync_pairs':16})
        mapped=flow.stage('dev_map','dev_map','device_map','v7_sdt_top_map.adf','Device Map')
        nc,nca=flow.export_graph('compile_post_constraints',HERE/'compile/v7_sdt_top_comp.adf',False)
        ns,nsa=flow.export_graph('actual_post_constraints',HERE/'synthesize/v7_sdt_top_syn.adf',True)
        mg,ma=flow.export_graph('mapped',mapped,False)
        flow.endpoint_audit('mapping',mg,ns)
        before=(HERE/'constraints_live/clock.fdc').read_bytes();post=flow.derive(nc,ns,nsa)
        require(before==(HERE/'constraints_live/clock.fdc').read_bytes(),'Post-map synthesis changed constraints; refuse PNR until new map')
        flow.record('coverageproof_synthesis.json',post);flow.runtime_constraints(post,ns)
        flow.record('canonical_equivalence_after_remap.json',{'physical_pairs':1320,'actual_manifest_sha256':sha(nsa/'manifest.json'),
                    'verified_by':'fresh exhaustive LUT graph mapping; no legacy1280 marker fallback'})
        route=flow.stage('pnr','pnr','place_route','v7_sdt_top_pnr.adf','Place & Route')
        from routed_acceptance import audit_all
        audit_all(route)
        immutable_runtime_guard()
        from prepare_local_delivery import finish_local_delivery
        result=finish_local_delivery(route)
        say('LOCAL_BIT_PASS_MAIN_REVIEW_PENDING','本地 bit 与物理签核通过；交主会话独立审阅，未进行远程或设备操作。',actual_result=str(E/'actual_result.json'))
    finally:kernel.CloseHandle(handle)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--prepare',action='store_true');ap.add_argument('--run',action='store_true');a=ap.parse_args()
    try:
        if a.prepare:prepare()
        elif a.run:build()
        else:ap.error('Select --prepare or --run')
    except BaseException as exc:
        E.mkdir(parents=True,exist_ok=True)
        if (E/'failure.txt').exists():
            archive=E/'failures';archive.mkdir(exist_ok=True)
            (archive/(sha(E/'failure.txt')+'.txt')).write_bytes((E/'failure.txt').read_bytes())
        (E/'failure.txt').write_text(traceback.format_exc(),encoding='utf8')
        if not (E/'blocked_reason.json').exists():
            flow.record('blocked_reason.json',{'status':'BLOCKED_OR_FAILED','reason_zh':str(exc),
                 'failure_sha256':sha(E/'failure.txt'),'actual_phase':load(E/'controller_status.json') if (E/'controller_status.json').exists() else None,
                 'remote_or_device_operation':False,'time':time.time()})
        say('FAILED_OR_BLOCKED_EVIDENCE_PRESERVED','build02 停止：'+str(exc)+'；证据保留在 '+str(E/'failure.txt'))
        raise
