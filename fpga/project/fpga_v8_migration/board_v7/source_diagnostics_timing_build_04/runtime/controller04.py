"""Authorized full build04 compile/synthesis/export only. Failures are never overwritten."""
from pathlib import Path
import argparse,ast,ctypes,json,os,re,shutil,subprocess,sys,time,traceback
import xml.etree.ElementTree as ET
from preflight import HERE,RUNTIME,BOARD,require,sha,load,save,verify,log_errors
E=HERE/'evidence/runtime'
B03=BOARD/'source_diagnostics_timing_build_03'
PDS=Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')
def processes():
    cmd='ConvertTo-Json -InputObject @(Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,CommandLine) -Compress'
    return json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',cmd]))
def idle(label):
    ps=processes()
    busy=[p for p in ps if p['Name'].lower() in {'pds.exe','pds_shell.exe','ta.exe'}]
    controllers=[p for p in ps if p['Name'].lower() in {'python.exe','pythonw.exe'} and 'diagnostic_sync_register_map12' in (p.get('CommandLine') or '') and re.search(r'(run_mapping|run_controller|controller).*\.py',p.get('CommandLine') or '',re.I)]
    save(label,{'time':time.time(),'processes':ps,'tool_busy':busy,'map12_controllers':controllers,'map12_fully_exited':not controllers})
    require(not busy and not controllers,'Tool/map12 controller still active; refuse launch')
def mutex():
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p];k.CreateMutexW.restype=ctypes.c_void_p
    k.ReleaseMutex.argtypes=[ctypes.c_void_p];k.CloseHandle.argtypes=[ctypes.c_void_p]
    h=k.CreateMutexW(None,True,'Global\\ov56401_PDS_single_instance');existed=ctypes.get_last_error()==183
    if existed and h:k.CloseHandle(h)
    require(h and not existed,'Global PDS mutex occupied')
    return k,h
def prepare():
    require(not (HERE/'manifest.json').exists(),'Build04 already prepared; no overwrite')
    idle('prepare_idle.json')
    m=load(B03/'manifest.json');require(len(m['local_hashes'])==741 and len(m['registered_sources'])==186,'Build03 inventory invalid')
    frozen={p.relative_to(B03).as_posix():sha(p) for p in B03.rglob('*') if p.is_file()}
    for n,h in m['local_hashes'].items():require(sha(B03/n)==h,'Build03 frozen source differs: '+n)
    for d in ['rtl','inputs','constraints_templates']:
        require(not (HERE/d).exists(),'Copy destination exists: '+d);shutil.copytree(B03/d,HERE/d)
    shutil.copy2(B03/'project_template.pds',HERE/'project_template.pds')
    shutil.copytree(HERE/'constraints_templates',HERE/'constraints_live')
    raw=(HERE/'project_template.pds').read_bytes().replace(b'constraints_templates/',b'constraints_live/')
    require(not re.search(rb'[A-Za-z]:[\\/]|\.\./',raw),'Project contains nonlocal source references')
    (HERE/'project.pds').write_bytes(raw)
    reg=[x.decode('ascii') for x in re.findall(rb'\(_file "([^"]+)"',raw)]
    sources=[x for x in reg if x.startswith(('rtl/','inputs/'))]
    require(sources==m['registered_sources'],'186 project source registrations differ')
    require(b'(_string "v7_sdt_top")' in raw,'Wrong full top')
    origins=[]
    for d in ['analysis_tools']:
        shutil.copytree(B03/'runtime'/d,RUNTIME/d,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        for p in (RUNTIME/d).rglob('*'):
            if p.is_file():origins.append({'source':str(B03/'runtime'/p.relative_to(RUNTIME)),'copy':p.relative_to(HERE).as_posix(),'sha256':sha(p)})
    (RUNTIME/'libraries').mkdir()
    for name in ['endpoints.py','endpoint_detail.py','endpoint_logic.py']:
        src=B03/'runtime/libraries'/name;dst=RUNTIME/'libraries'/name;shutil.copy2(src,dst)
        origins.append({'source':str(src),'copy':dst.relative_to(HERE).as_posix(),'sha256':sha(dst)})
    # Copy only the existing exact compile/synthesis receipt and graph export algorithms.
    src=B03/'runtime/physical_flow.py';text=src.read_text();tree=ast.parse(text)
    names={'snapshot','official_stage_complete','stage','export_graph','hashlib_sha'}
    functions=[ast.get_source_segment(text,n) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    body='\n\n'.join(functions).replace("def stage(label, stage_name, folder, db, mark):","def stage(label, stage_name, folder, db, mark):\n    require(stage_name in {'compile','synthesize'}, 'Only compile/synthesis authorized')")
    header="from controller04 import *\nimport xml.etree.ElementTree as ET\nEVIDENCE=E\nTOOLS=RUNTIME/'analysis_tools'\nPROJECT=HERE/'project.pds'\nrecord=save\nrun=tool\n"
    (RUNTIME/'flow04.py').write_text(header+body+'\n',encoding='utf-8')
    origins.append({'source':str(src),'source_sha256':sha(src),'copy':'runtime/flow04.py','sha256':sha(RUNTIME/'flow04.py'),'adaptation':'Only stage whitelist and independent build04 run/root imports; graph export algorithm exact'})
    protected=load(B03/'runtime/baseline_data/protected_guard.json')
    require(len(protected)==1022,'Protected inventory count changed')
    for n in m['local_hashes']:require((HERE/n).read_bytes()==(B03/n).read_bytes(),'Byte copy differs: '+n)
    source_set=__import__('hashlib').sha256(json.dumps(m['local_hashes'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
    for name,value in [('sourcehash.json',m['local_hashes']),('source04hash.json',{'root':str(HERE),'hashes':m['local_hashes'],'source_set_sha256':source_set})]:
        (HERE/name).write_text(json.dumps(value,indent=2)+'\n',encoding='ascii')
    models=Path('C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation')
    model_hashes={str(models/(n+'.v')):sha(models/(n+'.v')) for n in ['GTP_DFF_C','GTP_DFF_P','GTP_DFF_CE','GTP_DFF_PE']}
    protected.update(model_hashes);protected[str(PDS)]=sha(PDS)
    immutable={p.relative_to(HERE).as_posix():sha(p) for d in ['rtl','inputs','constraints_templates','constraints_live','runtime'] for p in (HERE/d).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    for name in ['project.pds','project_template.pds','sourcehash.json','source04hash.json']:immutable[name]=sha(HERE/name)
    manifest={'schema':1,'candidate_id':HERE.name,'root':str(HERE),'baseline_root':str(B03),'local_hashes':m['local_hashes'],'registered_sources':sources,'registered_files':reg,'immutable_hashes':immutable,'build03_full_hashes':frozen,'protected_hashes':protected,'official_model_hashes':model_hashes,'scope':'compile/synthesis/full-top-export/independent60 only; no mapping/PNR/bit/remote/program/Flash','constraints_qualified':False}
    (HERE/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='ascii')
    save('producer_provenance.json',origins)
    save('full_copy.json',{'source_files':741,'source_byte_comparison':True,'registered_sources':186,'source_set_sha256':source_set,'build03_full_file_count':len(frozen),'immutable_hashes':immutable,'protected_hashes':protected,'manifest_sha256':sha(HERE/'manifest.json')})
    save('initial_project_binding.json',{'root':str(HERE),'project_sha256':sha(HERE/'project.pds'),'project_template_sha256':sha(HERE/'project_template.pds'),'source_paths':[str(HERE/n) for n in sources],'constraints_root':str(HERE/'constraints_live'),'constraints_qualified':False})
    verify();print('build04 741源字节一致、186工程源、本地约束与独立生产器清单准备完成',flush=True)
def tool(label,command,cwd):
    verify();idle(label+'_idle.json')
    require(Path(cwd).resolve().is_relative_to(HERE),'Work dir outside build04')
    require(not (E/(label+'.log')).exists(),'Refuse overwrite log')
    save(label+'_launch.json',{'command':list(map(str,command)),'cwd':str(cwd),'controller_pid':os.getpid(),'parent_pid':os.getppid(),'time':time.time(),'manifest_sha256':sha(HERE/'manifest.json')})
    save(label+'_status.json',{'phase':'RUNNING_'+label.upper(),'pid':os.getpid(),'log':str(E/(label+'.log'))})
    print('真实阶段启动 '+label,flush=True)
    with (E/(label+'.log')).open('xb') as f:
        p=subprocess.Popen(list(map(str,command)),cwd=cwd,stdout=f,stderr=subprocess.STDOUT)
        save(label+'_process.json',{'pid':p.pid,'controller_pid':os.getpid(),'shell':str(PDS),'command':list(map(str,command))})
        code=p.wait()
    raw=(E/(label+'.log')).read_bytes();errors=log_errors(raw)
    for log in Path(cwd).rglob('run.log'):errors += [str(log)+': '+x for x in log_errors(log.read_bytes())]
    marks=[x.decode('ascii','backslashreplace') for x in raw.splitlines() if x.startswith((b'Process "',b'Design '))]
    save(label+'_result.json',{'exit_code':code,'errors':errors,'marks':marks,'log_sha256':sha(E/(label+'.log'))})
    verify();require(code==0 and not errors,'Actual tool failed: '+label)
    print('真实阶段完成 '+label+' exit=0',flush=True);return marks
def endpoint_audit(stage,g):
    sys.path.insert(0,str(RUNTIME/'libraries'));sys.path.insert(0,str(RUNTIME/'analysis_tools'))
    from endpoints import full_top_audit
    proof=full_top_audit(stage,g,save)
    models=load(HERE/'manifest.json')['official_model_hashes'];checks=[]
    for row in proof['rows']:
        rec=g['primitives'][row['cell']];typ=rec['type'];ports=set(rec['ports'])
        require(typ in {'GTP_DFF_C','GTP_DFF_P','GTP_DFF_CE','GTP_DFF_PE'},'Unproven exact primitive model: '+typ)
        model=next(n for n in models if Path(n).stem==typ);raw=Path(model).read_bytes()
        reset='C' if typ in {'GTP_DFF_C','GTP_DFF_CE'} else 'P'
        expected={'Q','D','CLK',reset}|({'CE'} if typ.endswith('E') else set())
        require(ports==expected and b'posedge CLK' in raw and ('posedge '+reset).encode() in raw,'Official model endpoint/polarity mismatch')
        require(re.search(rb'else\s+if\s*\(\s*'+reset.encode()+rb'\s*\)\s*qout\s*<=\s*1\x27b'+(b'0' if reset=='C' else b'1'),raw),'Official async reset/set semantics mismatch')
        checks.append({'cell':row['cell'],'type':typ,'ports':sorted(ports),'official_model':model,'model_sha256':sha(model),'positive_clock_edge':True,'async_active_high':True,'CE':'constant_one_verified' if 'CE' in ports else 'absent_in_exact_always_enabled_model'})
    save(stage+'_official_model_endpoint_audit.json',{'status':'PASS','rows':checks,'graph_sha256':sha(E/('compile' if stage=='compile' else 'actual')/'analysis/graph.json')})
    return proof
def build():
    verify();k,h=mutex()
    try:
        idle('launch_idle.json')
        save('controller_launch.json',{'pid':os.getpid(),'parent_pid':os.getppid(),'command':sys.argv,'shell':sys.executable,'time':time.time(),'global_mutex':'Global\\ov56401_PDS_single_instance','controller_sha256':sha(__file__),'manifest_sha256':sha(HERE/'manifest.json'),'scope':'compile/synthesize/export/60 only'})
        import flow04 as flow
        comp=flow.stage('compile','compile','compile','v7_sdt_top_comp.adf','Compile')
        syn=flow.stage('synthesize','synthesize','synthesize','v7_sdt_top_syn.adf','Synthesize')
        cg,ca=flow.export_graph('compile',comp,False);sg,sa=flow.export_graph('actual',syn,False)
        cp=endpoint_audit('compile',cg);sp=endpoint_audit('synthesis',sg)
        verify()
        require(not any((HERE/d).exists() for d in ['device_map','place_route','generate_bitstream']),'Unauthorized stage output')
        binding={str(p):sha(p) for p in [comp,syn,HERE/'compile/cmr.db',HERE/'synthesize/snr.db',ca/'graph.json',sa/'graph.json']}
        save('final_artifact_binding.json',binding)
        save('actual_result.json',{'status':'PASS_COMPILE_SYNTHESIS_EXPORT_INDEPENDENT60_ONLY','root':str(HERE),'top':'v7_sdt_top','stages':{'compile':{'status':cp['status'],'independent_registers':60,'independent_sync':28,'independent_reset':32,'failed_checks':0},'synthesis':{'status':sp['status'],'independent_registers':60,'independent_sync':28,'independent_reset':32,'failed_checks':0}},'final_artifacts':binding,'manifest_sha256':sha(HERE/'manifest.json'),'build03_full_hashes_unchanged':True,'sources741_byte_identical_build03':True,'mapping_started':False,'pnr_started':False,'bit_generated':False,'remote_or_device_operations':False,'constraints_qualified':False,'next_gate':'Main-session complete60 placement constraints required; no automatic mapping/route admission'})
        print('build04真实compile/synthesis/export与两阶段独立60端点审计PASS；未运行mapping/PNR/bit/设备',flush=True)
    finally:k.ReleaseMutex(h);k.CloseHandle(h)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--prepare',action='store_true');ap.add_argument('--run',action='store_true');a=ap.parse_args()
    try:
        if a.prepare:prepare()
        elif a.run:build()
        else:raise RuntimeError('Specify --prepare or --run')
    except BaseException:
        E.mkdir(parents=True,exist_ok=True)
        p=E/('failure_'+str(time.time_ns())+'.txt');p.write_text(traceback.format_exc(),encoding='utf-8')
        print('build04停止，失败与真实日志/DB保留：'+str(p),flush=True)
        raise
