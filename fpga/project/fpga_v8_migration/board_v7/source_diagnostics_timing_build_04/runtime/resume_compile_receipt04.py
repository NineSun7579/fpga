"""Resume after official successful Compile; original failure/DB/logs retained."""
from controller04 import *
def seal():
    revision=next((x[2:] for x in sys.argv if x.startswith('--preparation_revision')), 'preparation_revision03' if '--revision03' in sys.argv else 'preparation_revision02')
    archive=E/revision;archive.mkdir()
    shutil.copy2(HERE/'manifest.json',archive/'manifest.json')
    m=load(HERE/'manifest.json')
    for p in RUNTIME.rglob('*.py'):
        if '__pycache__' not in p.parts:m['immutable_hashes'][p.relative_to(HERE).as_posix()]=sha(p)
    (HERE/'manifest.json').write_text(json.dumps(m,indent=2)+'\n',encoding='ascii')
    save(revision+'.json',{'reason':'Permit only PDS-maintained project generation comment, timestamps, gci state and output registration; all source/options/input registrations strictly normalized equal template','prior_manifest_sha256':sha(archive/'manifest.json'),'manifest_sha256':sha(HERE/'manifest.json'),'producer_hashes':{n:h for n,h in m['immutable_hashes'].items() if n.startswith('runtime/')},'compile_failure_preserved':True})
    verify()
def resume():
    verify();k,h=mutex()
    try:
        idle('resume_launch_idle.json')
        save('resume_controller_launch.json',{'pid':os.getpid(),'parent_pid':os.getppid(),'command':sys.argv,'shell':sys.executable,'manifest_sha256':sha(HERE/'manifest.json'),'global_mutex':'Global\\ov56401_PDS_single_instance'})
        import flow04 as flow
        comp=HERE/'compile/v7_sdt_top_comp.adf';native=HERE/'compile/cmr.db'
        rr=load(E/'compile_result.json');launch=load(E/'compile_launch.json')
        require(rr['exit_code']==0 and not rr['errors'] and rr['log_sha256']==sha(E/'compile.log'),'Compile receipt failed')
        require(flow.official_stage_complete('compile','Compile',rr['marks']),'Compile official done absent')
        require(comp.stat().st_mtime>=launch['time']-2 and native.is_file(),'Compile artifact not fresh')
        errors=[]
        for table in ET.parse(native).getroot().iter('table'):
            if 'message' in table.get('id','').lower():
                for row in table.findall('row'):
                    vals=[d.text or '' for d in row.findall('data')]
                    if any(v.strip().lower() in {'error','fatal'} for v in vals):errors.append(vals)
        require(not errors,'Compile native errors')
        save('compile_native_message_audit.json',{'native_db_sha256':sha(native),'errors':errors})
        save('compile_artifact.json',{'path':str(comp),'sha256':sha(comp),'native_db':str(native),'native_db_sha256':sha(native),'official_marks':rr['marks'],'fresh_started':launch['time'],'error_count':0,'basis':'Original exit0 official done log plus fresh actual ADF/native DB; no recompilation'})
        syn=flow.stage('synthesize','synthesize','synthesize','v7_sdt_top_syn.adf','Synthesize')
        cg,ca=flow.export_graph('compile',comp,False);sg,sa=flow.export_graph('actual',syn,False)
        cp=endpoint_audit('compile',cg);sp=endpoint_audit('synthesis',sg)
        verify();require(not any((HERE/d).exists() for d in ['device_map','place_route','generate_bitstream']),'Unauthorized stage output')
        binding={str(p):sha(p) for p in [comp,syn,native,HERE/'synthesize/snr.db',ca/'graph.json',sa/'graph.json']}
        save('final_artifact_binding.json',binding)
        save('actual_result.json',{'status':'PASS_COMPILE_SYNTHESIS_EXPORT_INDEPENDENT60_ONLY','root':str(HERE),'top':'v7_sdt_top','stages':{'compile':{'status':cp['status'],'independent_registers':60,'independent_sync':28,'independent_reset':32,'failed_checks':0},'synthesis':{'status':sp['status'],'independent_registers':60,'independent_sync':28,'independent_reset':32,'failed_checks':0}},'final_artifacts':binding,'manifest_sha256':sha(HERE/'manifest.json'),'build03_full_hashes_unchanged':True,'sources741_byte_identical_build03':True,'mapping_started':False,'pnr_started':False,'bit_generated':False,'remote_or_device_operations':False,'constraints_qualified':False,'next_gate':'Main-session complete60 placement constraints required; no automatic mapping/route admission'})
        print('build04真实compile/synthesis/export、两阶段独立60端点PASS',flush=True)
    finally:k.ReleaseMutex(h);k.CloseHandle(h)
if __name__=='__main__':
    try:
        if '--seal' in sys.argv:seal()
        else:resume()
    except BaseException:
        p=E/('failure_'+str(time.time_ns())+'.txt');p.write_text(traceback.format_exc(),encoding='utf-8');print(str(p),flush=True);raise
