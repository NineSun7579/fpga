"""Build03 local serial physical construction; never programs or accepts delivery."""
from pathlib import Path
import argparse, ctypes, hashlib, json, os, py_compile, re, sys, time, traceback
from preflight import HERE, BOARD, DATA, RUNTIME, load, sha, save, require, verify, map_gate
import physical_flow as flow
E=flow.EVIDENCE

def say(phase,message,**extra):
    flow.status(phase,message_zh=message,**extra)
    print(message,flush=True)

def project_guard(initial=False):
    manifest=load(HERE/'manifest.json');raw=flow.PROJECT.read_bytes()
    registered=[n.decode('ascii') for n in re.findall(rb'\(_file "([^"]+)"',raw)]
    require([n for n in registered if n.startswith(('rtl/','inputs/'))]==manifest['registered_sources'],'186 actual registered sources changed')
    require(b'(_string "v7_sdt_top")' in raw,'Actual top option changed')
    require(not re.search(rb'[A-Za-z]:[\\/]|\.\./',raw),'Nonlocal project source/input binding')
    require(b'constraints_templates/' not in raw and b'constraints_pending/' not in raw,'Runtime project still registers template/old pending constraints')
    outputs={'compile','synthesize','device_map','place_route','generate_bitstream'}
    require(all((HERE/n).is_file() for n in registered if Path(n).parts[0] not in outputs),'Missing project registered asset')
    actual=[n for n in registered if n.startswith('constraints_live/')]
    require(set(actual)=={'constraints_live/'+n for n in ['clock.fdc','cdc.fdc','ddr3.fdc','ov5640.fdc','pcie.fdc','sfp.fdc']},'Constraint root registration changed')
    for name in ['cdc.fdc','ddr3.fdc','ov5640.fdc','pcie.fdc','sfp.fdc']:
        require((HERE/'constraints_live'/name).read_bytes()==(HERE/'constraints_templates'/name).read_bytes(),'Nonclock input changed')
    if initial:
        require(raw==(HERE/'project_template.pds').read_bytes().replace(b'constraints_templates/',b'constraints_live/'),'Initial executable project not exact local template')
        require((HERE/'constraints_live/clock.fdc').read_bytes()==(HERE/'inputs/source/constraints/clock.fdc').read_bytes(),'Initial clocks not logical frozen inputs')
    return {'project_sha256':sha(flow.PROJECT),'registered_sources':186,'registered_files':len(registered),
            'absolute_source_paths':[str((HERE/n).resolve()) for n in manifest['registered_sources']],
            'generated_output_paths':[n for n in registered if Path(n).parts[0] in outputs]}

def immutable_runtime_guard(initial=False):
    ledger=load(E/'runtime_hash_append.json')
    require(ledger['root']==str(HERE) and ledger['candidate_id']=='source_diagnostics_timing_build_03','Runtime root/candidate identity changed')
    for n,h in ledger['runtime_hash_append'].items():require(sha(HERE/n)==h,'Frozen runtime/library/baseline drift: '+n)
    require(sha(HERE/'manifest.json')==ledger['immutable_manifest_sha256'],'741 frozen manifest drift')
    verify();project_guard(initial)
    require(sha(E/'offline_runtime_checks.json')==ledger['offline_checks_sha256'] and load(E/'offline_runtime_checks.json')['status']=='PASS_OFFLINE_RUNTIME_ONLY','Offline runtime checks missing/drifted')
    require(sha(E/'identity_adapter_review.json')==ledger['identity_calibration_sha256'],'Actual read-only calibration receipt drift')

def prepare():
    require(not (E/'runtime_hash_append.json').exists(),'Frozen runtime already sealed; do not reset evidence while queued')
    E.mkdir(parents=True,exist_ok=True);verify()
    if not flow.PROJECT.exists():flow.setup()
    guard=project_guard(True)
    compiled=[]
    for p in RUNTIME.rglob('*.py'):
        py_compile.compile(str(p),doraise=True);compiled.append(p.relative_to(HERE).as_posix())
    from offline_checks import check
    checks=check();save('offline_runtime_checks.json',checks)
    require(checks['status']=='PASS_OFFLINE_RUNTIME_ONLY','Offline runtime checks failed')
    import verify_identity_adapter
    verify_identity_adapter.main()
    require(load(E/'identity_adapter_review.json')['physical_signoff'] is False,'Calibration cannot claim new physical signoff')
    files=[p for p in RUNTIME.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    ledger={'schema':1,'root':str(HERE),'candidate_id':'source_diagnostics_timing_build_03',
            'immutable_manifest_sha256':sha(HERE/'manifest.json'),'source03hash_sha256':sha(HERE/'source03hash.json'),
            'runtime_hash_append':{p.relative_to(HERE).as_posix():sha(p) for p in files},'project':guard,
            'compiled':compiled,'offline_checks_sha256':sha(E/'offline_runtime_checks.json'),
            'identity_calibration_sha256':sha(E/'identity_adapter_review.json'),
            'authorized_scope':'local compile/synthesis/map/PNR/all-corner-signoff/bit/real-source-descriptor only; no remote/device or accepted/reviewer',
            'functional_input_contract':'741 candidate hashes;186 registrations;regression03 actualsrc inverse;primitive-only noprune remains gated by real map02 final',
            'main_consumer_extension':'Separate main review; producer does not patch or import assembler/consumer verifier'}
    save('runtime_hash_append.json',ledger);immutable_runtime_guard(True)
    save('runtime_port_status.json',{'status':'EXECUTABLE_SEALED_LOCAL_ONLY','ledger_sha256':sha(E/'runtime_hash_append.json'),
         'map_gate':map_gate(),'pds_started':False,'bit_generated':False,'device_operations':False})
    say('EXECUTABLE_PREPARED_WAIT_MAP02','build03完整本地runtime已冻结；真实map02 mappingfinalPASS与全局串行空闲后才启动。')

def wait_gate():
    last=None
    while True:
        immutable_runtime_guard(initial=True)
        gate=map_gate();current=flow.processes();busy,observers=flow.classify_processes(current,os.getpid())
        state=(gate['status'],tuple(sorted(p['ProcessId'] for p in busy)))
        if state!=last:
            save('queue_build03.json',{'time':time.time(),'pid':os.getpid(),'map_gate':gate,'busy':busy,'observers_excluded':observers,
                 'policy':'No global PDS slot held while waiting; prior executors and GUI/PDS/TA must exit. Basename controller03 command avoids map02 treating its prerequisite waiter as a prior executor.'})
            say('WAIT_MAP02_AND_PRIOR_FINISHERS','build03门禁='+gate['status']+'；等待前序PID='+str(list(state[1])),gate=gate)
            last=state
        if gate['status']=='BLOCKED':
            save('blocked_reason.json',{'status':'REFUSED_LAUNCH','reason_zh':'map02真实最终mapping/独立审计门禁拒绝，build03未启动PDS',
                 'gate':gate,'pds_started_by_build03':False,'time':time.time()})
            require(False,'Map02 real mapping final gate rejected: '+str(gate))
        if gate['status']=='PASS' and not busy:
            immutable_runtime_guard(True);save('map02_launch_gate.json',gate);return
        time.sleep(5)

def mutex(name):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p];kernel.CreateMutexW.restype=ctypes.c_void_p
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=kernel.CreateMutexW(None,True,name);existed=ctypes.get_last_error()==183
    if existed and handle:kernel.CloseHandle(handle)
    require(handle and not existed,'Controller/global tool mutex already owned: '+name)
    return kernel,handle

def build():
    immutable_runtime_guard(True)
    kernel,lease=mutex('Global\\ov56401_build03_controller')
    try:
        save('controller_launch.json',{'pid':os.getpid(),'parent_pid':os.getppid(),'command':sys.argv,'time':time.time(),
             'cwd':str(Path.cwd()),'controller_sha256':sha(__file__),'ledger_sha256':sha(E/'runtime_hash_append.json'),
             'scope':'Local physical run only; gate can never be satisfied by calibration/unit inputs'})
        wait_gate()
        toolkernel,toollease=mutex('Global\\ov56401_PDS_single_instance')
        try:
            busy,_=flow.classify_processes(flow.processes(),os.getpid());require(not busy,'Global/prior executor became busy before launch')
            immutable_runtime_guard(True);require(map_gate()['status']=='PASS','Mapping gate changed before PDS start')
            save('protected_before.json',load(DATA/'protected_guard.json'));save('sources741_before.json',load(HERE/'sourcehash.json'))
            save('inputs_before.json',flow.snapshot())
            say('START_AUTHORIZED_LOCAL_PHYSICAL','map02真实mappingfinalPASS与前序退出已核验；启动build03新compile/synthesis实际图。')
            comp=flow.stage('compile','compile','compile','v7_sdt_top_comp.adf','Compile')
            syn=flow.stage('synthesize','synthesize','synthesize','v7_sdt_top_syn.adf','Synthesize')
            cg,ca=flow.export_graph('compile',comp,False);sg,sa=flow.export_graph('actual',syn,True)
            flow.endpoint_audit('compile',cg);flow.endpoint_audit('synthesis',sg)
            proof=flow.derive(cg,sg,sa)
            save('actual_new_graph_adapter_test.json',{'passed':True,'compile_graph_sha256':sha(ca/'graph.json'),
                 'synthesis_graph_sha256':sha(sa/'graph.json'),'independent_registers':60,'logical_mailbox_bits':2048,
                 'mailbox_pairs':proof['physical_pairs'],'same_domain_sync_pairs':16,'derived_constraints_sha256':sha(HERE/'constraints_live/clock.fdc')})
            mapped=flow.stage('dev_map','dev_map','device_map','v7_sdt_top_map.adf','Device Map')
            nc,nca=flow.export_graph('compile_post_constraints',HERE/'compile/v7_sdt_top_comp.adf',False)
            ns,nsa=flow.export_graph('actual_post_constraints',HERE/'synthesize/v7_sdt_top_syn.adf',True)
            mg,ma=flow.export_graph('mapped',mapped,False)
            flow.endpoint_audit('mapping',mg,ns)
            before=(HERE/'constraints_live/clock.fdc').read_bytes();post=flow.derive(nc,ns,nsa)
            require(before==(HERE/'constraints_live/clock.fdc').read_bytes(),'Post-map actual graph changed constraints; refuse PNR until separately reviewed remap')
            save('coverageproof_synthesis.json',post);flow.runtime_constraints(post,ns)
            require(load(E/'runtime_U_B_gate.json')['passed'],'Actual364 CDB and clock interaction U-B gate not PASS')
            save('inputs_before_pnr.json',flow.snapshot())
            route=flow.stage('pnr','pnr','place_route','v7_sdt_top_pnr.adf','Place & Route')
            from routed_acceptance import audit_all
            audit_all(route)
            immutable_runtime_guard()
            from prepare_local_delivery import finish_local_delivery
            result=finish_local_delivery(route)
            save('runtime_port_status.json',{'status':result['status'],'pid':os.getpid(),'map_gate_sha256':sha(E/'map02_launch_gate.json'),
                 'actual_result':str(E/'actual_result.json'),'device_operations':False})
            say('LOCAL_BIT_PASS_MAIN_INDEPENDENT_REVIEW_PENDING','build03本地bit及全实际签核完成；真实sources已交主独立审阅，未烧录。')
        finally:toolkernel.CloseHandle(toollease)
    finally:kernel.CloseHandle(lease)

if __name__=='__main__':
    ap=argparse.ArgumentParser();m=ap.add_mutually_exclusive_group(required=True);m.add_argument('--prepare',action='store_true');m.add_argument('--run',action='store_true');a=ap.parse_args()
    try:
        if a.prepare:prepare()
        else:build()
    except BaseException as exc:
        E.mkdir(parents=True,exist_ok=True)
        if (E/'failure.txt').exists():
            dest=E/'failures'/('failure_'+sha(E/'failure.txt')+'.txt');dest.parent.mkdir(exist_ok=True);dest.write_bytes((E/'failure.txt').read_bytes())
        (E/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        if not (E/'blocked_reason.json').exists():save('blocked_reason.json',{'status':'BLOCKED_OR_FAILED','reason':str(exc),
             'failure_sha256':sha(E/'failure.txt'),'actual_phase':load(E/'controller_status.json') if (E/'controller_status.json').exists() else None,
             'remote_or_device_operation':False,'bit_generation_requires_full_real_signoff':True})
        say('FAILED_OR_BLOCKED_EVIDENCE_PRESERVED','build03停止：'+str(exc)+'；实际stage DB与日志全部保留。')
        raise
