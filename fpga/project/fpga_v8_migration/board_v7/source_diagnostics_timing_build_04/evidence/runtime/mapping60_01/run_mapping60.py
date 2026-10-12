"""One authorized production60 mapping attempt; immutable original build and failures."""
from pathlib import Path
import ctypes,hashlib,json,os,re,shutil,subprocess,sys,time,traceback,tkinter
import xml.etree.ElementTree as ET
sys.dont_write_bytecode=True
E=Path(__file__).resolve().parent
B=E.parents[2]; BOARD=B.parent; PREP=BOARD/'production60_target_prepare01'
sys.path[:0]=[str(B/'runtime'),str(B/'runtime/libraries'),str(B/'runtime/analysis_tools')]
import preflight
from endpoints import full_top_audit
from endpoint_detail import parameters
from graph_adapter import Resolver,canon,parameter
PDS=Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')
W=E/'isolated_mapping_work';T=tkinter.Tcl()
def sha(p):return preflight.sha(p)
def require(x,msg):
    if not x:raise RuntimeError(msg)
def load(p):return json.loads(Path(p).read_bytes())
def save(n,o):
    p=E/n;require(not p.exists(),'Refuse overwrite '+str(p));p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(o,indent=2,ensure_ascii=True)+'\n',encoding='ascii')
def tree(root):return {p.relative_to(root).as_posix():sha(p) for p in root.rglob('*') if p.is_file()}
def processes():
    return json.loads(subprocess.check_output(['powershell','-NoProfile','-Command','ConvertTo-Json -InputObject @(Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,CommandLine) -Compress']))
def idle(label):
    ps=processes();busy=[p for p in ps if p['Name'].lower() in {'pds.exe','pds_shell.exe','ta.exe'}]
    save(label+'_idle.json',{'time':time.time(),'processes':ps,'busy':busy});require(not busy,'PDS/GUI/TA busy')
def guard():
    preflight.verify()
    require(tree(BOARD/'source_diagnostics_timing_build_03')==GUARDS['build03'],'Build03 full tree drift')
    require(tree(BOARD/'diagnostic_sync_register_map02')==GUARDS['map02'],'Map02 full tree drift')
    for n,h in GUARDS['build04'].items():require(sha(B/n)==h,'Original build04 drift '+n)
    actual={p.relative_to(B).as_posix() for p in B.rglob('*') if p.is_file() and not p.is_relative_to(E)}
    require(actual==set(GUARDS['build04']),'Original build04 file set changed')
def reject(raw):
    return [x.decode('ascii','backslashreplace') for x in raw.splitlines() if
      re.search(rb'Timing-4006|STA-3016|\b(?:unknown|unrecognized|unsupported|ignored|ignoring)\b',x,re.I)
      or re.match(rb'\s*(?:E:|\*\*\s*(?:ERROR|FATAL)\b|(?:ERROR|FATAL)\b)',x,re.I)
      or re.search(rb'\b(?:Tcl|constraint|location|UCE).*\b(?:error|failed|failure)\b',x,re.I)]
def tool(label,cmd,cwd):
    guard();idle(label)
    inputs={str(p):sha(p) for p in [PDS,Path(__file__),Path(cmd[cmd.index('-file')+1])]}
    save(label+'_launch.json',{'time':time.time(),'command':list(map(str,cmd)),'cwd':str(cwd),'controller_pid':os.getpid(),'input_hashes':inputs,'mutex':'Global\\ov56401_PDS_single_instance'})
    log=E/(label+'.log');require(not log.exists(),'Existing tool log')
    print('REAL_TOOL_START '+label,flush=True)
    with log.open('xb') as f:
        p=subprocess.Popen(list(map(str,cmd)),cwd=cwd,stdout=f,stderr=subprocess.STDOUT)
        save(label+'_process.json',{'pid':p.pid,'controller_pid':os.getpid(),'command':list(map(str,cmd))});code=p.wait()
    raw=log.read_bytes();bad=reject(raw);native=[]
    for q in Path(cwd).rglob('run.log'):
        if q.is_relative_to(W/'synthesize'):continue
        bad.extend(str(q)+': '+x for x in reject(q.read_bytes()))
    db=W/'device_map/dmr.db'
    if label=='mapping' and db.exists():
        for table in ET.parse(db).getroot().iter('table'):
            if 'message' not in table.get('id','').lower():continue
            for row in table.findall('row'):
                vals=[d.text or '' for d in row.findall('data')]
                if any(v.strip().lower() in {'error','fatal'} for v in vals) or reject(' '.join(vals).encode('utf-8')):native.append(vals)
    save(label+'_receipt.json',{'exit_code':code,'rejected_lines':bad,'native_errors':native,'log_sha256':sha(log),'command':list(map(str,cmd)),'native_db_sha256':sha(db) if db.exists() else None})
    guard();require(code==0 and not bad and not native,'Actual '+label+' failed; see receipt/log; no rerun')
    print('REAL_TOOL_FINISH '+label+' exit='+str(code),flush=True);return raw
def locs(rec):
    ans=[]
    def visit(v):
        if not isinstance(v,list):return
        if len(v)==3 and v[:2]==['ATTRIBUTE','PAP_LOC']:
            require(isinstance(v[2],list) and v[2][0]=='STRING','Unknown PAP_LOC format');ans.append({'value':v[2][1].strip('"'),'entry':v})
        for x in v:visit(x)
    visit(rec.get('attributes',[]));visit(rec.get('cdb_entries',[]));return ans
def exact_clock_paths(g,rows):
    r=Resolver(g);out=[]
    for row in rows:
        name=row['clock_root_expected'];alias=name if name!='ddrphy_sysclk' else 'ddr3/u_ddrphy_top/ddrphy_sysclk'
        roots={n for n,aa in g['net_aliases'].items() if alias in {canon(a) for a in aa}}
        require(len(roots)==1,'Exact clock root missing '+alias)
        n=g['pin_net'][row['CLK']];seen=set();edges=[]
        while n not in roots:
            require(n not in seen,'Clock identity cycle');seen.add(n);ds=r.drivers(n);require(len(ds)==1,'Clock identity driver ambiguity '+n)
            pin=ds[0];cell=pin.rsplit('/',1)[0];rec=g['primitives'][cell];typ=rec['type'];inputpin=r.identity_input(pin,clock=False)
            if inputpin is None:
                if typ in {'gopIBUF','gopIBUF_Cell_1','gopIBUF_Cell_2'}:
                    require(pin==cell+'/O' and parameter(rec,'CP_DYN_IN')=='OFF' and parameter(rec,'IOB_MODE').startswith('IBUF'),'Unproved IBUF clock identity');inputpin=cell+'/I'
                elif typ=='gopCLKBUFG':
                    require(pin==cell+'/CLKOUT','Unproved CLKBUFG output');inputpin=cell+'/CLK'
                elif typ=='gopHCKB':
                    require(pin==cell+'/CLKOUT' and parameter(rec,'CP_MODE_SEL')=='DISABLE','Unproved HCKB clock identity');inputpin=cell+'/CLKIN'
                elif typ=='gopIOL_Cell_9':
                    checks={'BUF_MODE':'IBUF','CP_IDLY_EN':'FALSE','CP_IDYN_EN':'FALSE','CP_ZHOLD_EN':'FALSE','CP_DYN_CLKPOL':'FALSE','CP_IDFFEN':'FALSE','CP_ILTHEN':'FALSE','CP_DDRI_EN':'FALSE','CP_DES_DDREN':'FALSE','CP_DES_SDREN':'FALSE','CP_D_POL0':'FALSE','CP_D_SEL0':0,'CP_D_SEL1':0,'CP_D_SEL2':0,'CP_D_SEL3':0}
                    require(pin==cell+'/DI_TO_CLK' and all(parameter(rec,k)==v for k,v in checks.items()),'Unproved IOL clock identity');inputpin=cell+'/DI'
                    require(not any(cell+'/'+p in g['pin_net'] for p in ['ICLK','ICLKB','ICLKDIV','DYN_CLKPOL','IDLY_SEL']),'IOL clock active state')
                else:raise RuntimeError('Unknown exact clock identity primitive '+typ+' '+cell)
            require(inputpin in g['pin_net'] and rec['ports'][inputpin.rsplit('/',1)[1]]['direction']=='INPUT','Clock identity input unconnected')
            edges.append({'net':n,'driver':pin,'type':typ,'identity_input':inputpin,'decoded_parameters':parameters(rec)})
            n=g['pin_net'][inputpin]
        out.append({'cell':row['cell'],'clock_pin':row['CLK'],'root_alias':alias,'root_net':n,'identity_path':edges,'passed':True})
    return out
def main():
    global GUARDS
    require(not W.exists(),'One attempt only')
    m=preflight.verify()
    GUARDS={'build03':tree(BOARD/'source_diagnostics_timing_build_03'),'map02':tree(BOARD/'diagnostic_sync_register_map02'),
      'build04':{p.relative_to(B).as_posix():sha(p) for p in B.rglob('*') if p.is_file() and not p.is_relative_to(E)},
      'source741':m['local_hashes'],'source_full_tree':m['full_source_copy_hashes'],'protected':m['protected_hashes']}
    save('protection_before.json',GUARDS)
    require(len(GUARDS['build03'])==874 and len(m['local_hashes'])==741 and len(m['registered_sources'])==186,'Protection inventory count')
    final=load(B/'evidence/runtime/final_artifact_binding.json')
    for p,h in final.items():require(sha(p)==h,'Final artifact hash drift '+p)
    review=load(B/'evidence/runtime/final_receipt_review.json');require(review['status']=='PASS_LOCAL_COMPILE_SYNTHESIS_EXPORT_60_RECEIPT_REVIEW','Build04 receipt not PASS')
    draft=load(PREP/'constraint_draft_binding.json');ref=BOARD/'diagnostic_sync_register_map12/independent_review01'
    for p,key in [(PREP/'production60_site_DRAFT.lcf','draft_sha256'),(PREP/'site_candidate_plan.json','site_plan_sha256'),(ref/'independent_result.json','review_sha256'),(ref/'production60_syntax_reference.json','syntax_reference_sha256')]:require(sha(p)==draft[key],'Draft binding mismatch '+key)
    parser=B/'runtime/analysis_tools/parse_objects.py';pa=B/'evidence/runtime/actual/analysis/parse_objects.py'
    require(sha(parser)==sha(pa),'Parser differs from final actual synthesis parser')
    parserbinding=load(B/'evidence/runtime/actual_graph_artifact.json');require(sha(parser)==parserbinding['parser_sha256'],'Parser final receipt binding')
    sgfile=B/'evidence/runtime/actual/analysis/graph.json';sg=load(sgfile)
    require(sha(sgfile)==parserbinding['graph_sha256'],'Synthesis graph binding')
    proof=full_top_audit('synthesis_mapping_preflight',sg,save)
    targets=[]
    for line in (PREP/'production60_site_DRAFT.lcf').read_text(encoding='ascii').splitlines():
        if not line.strip() or line.lstrip().startswith('#'):continue
        parts=T.splitlist(line);require(len(parts)==4 and parts[0]=='define_attribute' and parts[2]=='PAP_LOC' and parts[1].startswith('i:'),'Invalid exact Tcl LCF command')
        targets.append({'target':parts[1][2:],'site':parts[3]})
    bycell={r['cell']:r for r in proof['rows']}
    require(len(targets)==60 and len(bycell)==60 and len({r['target'] for r in targets})==60 and len({r['site'] for r in targets})==60,'60 distinct target/site count')
    require({r['target'] for r in targets}==set(bycell),'LCF targets are not exact actual synthesis instances')
    planned={r['target']:r['site'] for r in load(PREP/'site_candidate_plan.json')['rows']}
    require(planned=={r['target']:r['site'] for r in targets},'Target/site plan mismatch')
    rows=[]
    for t in targets:
        row=bycell[t['target']];rec=sg['primitives'][row['cell']];typ=rec['type'];ports=set(rec['ports']);reset='C' if row['chain'] in {'ack_sync','req_sync','overrun_sync'} else 'P'
        require(typ=='GTP_DFF_'+reset and ports=={'D','Q','CLK',reset},'Exact C/P no-CE synthesis model mismatch '+row['cell'])
        model=next(Path(n) for n in m['official_model_hashes'] if Path(n).stem==typ);require(sha(model)==m['official_model_hashes'][str(model)],'Official model drift')
        rows.append({**t,'synthesis_row':row,'no_CE_model':str(model),'model_sha256':sha(model)})
    require(len(proof['rows'])==60 and len({r['cell'] for r in proof['rows']})==60,'60 storage required')
    save('fresh60_binding.json',{'status':'PASS_EXACT_SYNTHESIS60_BINDING','rows':rows,'synthesis_graph_sha256':sha(sgfile),'parser_sha256':sha(parser),'draft_binding_sha256':sha(PREP/'constraint_draft_binding.json'),'review_sha256':sha(ref/'independent_result.json'),'sync':28,'reset':32})
    print('PREFLIGHT_EXACT60_PASS 28sync+32reset',flush=True)
    idle('formal_launch')
    k=ctypes.WinDLL('kernel32',use_last_error=True);k.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p];k.CreateMutexW.restype=ctypes.c_void_p;k.ReleaseMutex.argtypes=[ctypes.c_void_p];k.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=k.CreateMutexW(None,True,'Global\\ov56401_PDS_single_instance');exists=ctypes.get_last_error()==183
    if exists and handle:k.CloseHandle(handle)
    require(handle and not exists,'Global PDS mutex occupied')
    try:
        idle('mutex_acquired');W.mkdir();(W/'constraints').mkdir()
        shutil.copytree(B/'synthesize',W/'synthesize');shutil.copy2(B/'project.pds',W/'project.pds')
        shutil.copy2(B/'constraints_live/clock.fdc',W/'constraints/clock.fdc');shutil.copy2(PREP/'production60_site_DRAFT.lcf',W/'constraints/production60.lcf')
        native=tree(B/'synthesize');require(tree(W/'synthesize')==native,'Full native synthesis copy differs')
        save('synthesis_reuse_provenance.json',{'full_stage_tree':native,'source':str(B/'synthesize'),'copy':str(W/'synthesize'),'final_artifact_binding':final,'parser':str(parser),'parser_sha256':sha(parser)})
        syn=W/'synthesize/v7_sdt_top_syn.adf';script=E/'actual_map.tcl'
        script.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\nadd_constraint {'+(W/'constraints/clock.fdc').as_posix()+'}\nadd_constraint {'+(W/'constraints/production60.lcf').as_posix()+'}\ndev_map -force_to_run -input_db_file {'+syn.as_posix()+'} -override_pcf true -devmap_remove_dups 0 -devmap_const_prop 0 -devmap_control_set_num 0\n',encoding='ascii')
        inputs={str(p):sha(p) for p in [script,syn,W/'synthesize/snr.db',W/'constraints/clock.fdc',W/'constraints/production60.lcf',W/'project.pds',parser,PDS]}
        save('mapping_input_hashes.json',inputs)
        started=time.time();raw=tool('mapping',[PDS,'-file',script,'-work_dir',W,'-project_name','v7_sdt_top'],W)
        require(b'Process "Device Map" done.' in raw or b'Process "DevMap" done.' in raw,'Missing actual mapping completion')
        require(tree(W/'synthesize')==native,'Reused full synthesis stage changed')
        save('project_post_mapping.json',{'original_project_sha256':inputs[str(W/'project.pds')],'after_project_sha256':sha(W/'project.pds'),'rewritten':sha(W/'project.pds')!=inputs[str(W/'project.pds')],'post_project_bytes_ascii':(W/'project.pds').read_bytes().decode('ascii')})
        require(all(sha(p)==h for p,h in inputs.items()),'Mapping input drift (including recorded project)')
        db=W/'device_map/v7_sdt_top_map.adf';dmr=W/'device_map/dmr.db';pcf=W/'device_map/v7_sdt_top.pcf'
        require(all(p.is_file() and p.stat().st_size and p.stat().st_mtime>=started-2 for p in [db,dmr,pcf]),'Missing fresh ADF/dmr/PCF')
        save('mapping_artifact.json',{str(p):sha(p) for p in [db,dmr,pcf]})
        dest=E/'mapping';ana=dest/'analysis';ana.mkdir(parents=True);dump=dest/'synthesis_export/synthesis_dump.txt';dump.parent.mkdir()
        export=dest/'export.tcl';export.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n.switch_db -input {'+db.as_posix()+'} -output {'+dump.as_posix()+'}\n',encoding='ascii')
        before=sha(db);tool('mapping_export',[PDS,'-file',export,'-work_dir',dest,'-project_name','v7_sdt_top_mapping60'],dest);require(sha(db)==before,'Export changed mapped ADF')
        shutil.copy2(parser,ana/'parse_objects.py');res=subprocess.run([sys.executable,'-B',ana/'parse_objects.py'],cwd=ana,capture_output=True);(ana/'parser.log').write_bytes(res.stdout+res.stderr);require(res.returncode==0,'Actual fulltop parser failed')
        g=load(ana/'graph.json');save('graph_binding.json',{'adf_sha256':sha(db),'dmr_sha256':sha(dmr),'pcf_sha256':sha(pcf),'dump_sha256':sha(dump),'graph_sha256':sha(ana/'graph.json'),'parser_sha256':sha(ana/'parse_objects.py')})
        # Exact mapped type gate precedes semantics; no arbitrary storage-type acceptance.
        from graph_adapter import classify
        cl=classify(g);types=sorted({r['type'] for r in cl['rows']})
        save('mapped_primitive_types.json',{'types':types,'rows':[{'cell':r['cell'],'type':r['type']} for r in cl['rows']]})
        require(set(types)=={'gopQ'},'Unknown/unproven exact mapped primitive type '+repr(types))
        mp=full_top_audit('mapping',g,save)
        save('mapped_exact_clock_identity.json',{'rows':exact_clock_paths(g,mp['rows']),'passed':True,'basis':'Every intermediate actual clock primitive is an exact, parameter-proven identity; no roots-only acceptance'})
        require(len(mp['rows'])==60 and len({r['cell'] for r in mp['rows']})==60,'Missing distinct mapped storage')
        sync=sum(r['chain'] in {'ack_sync','req_sync','overrun_sync'} for r in mp['rows']);require(sync==28 and len(mp['rows'])-sync==32,'28/32 mapped counts')
        bindings=[];pcfrows=[]
        for line in pcf.read_text(encoding='ascii').splitlines():
            if not line.strip() or line.lstrip().startswith('#'):continue
            parts=T.splitlist(line)
            if parts and parts[0]=='def_inst_site':
                require(len(parts) in {3,4},'Unknown def_inst_site command');pcfrows.append({'cell':parts[1].lstrip('\\'),'site':parts[2],'impl':parts[3] if len(parts)==4 else None,'line':line})
        mapped={(r['camera'],r['chain'],r['bit']):r for r in mp['rows']}
        for t in rows:
            sr=t['synthesis_row'];mr=mapped[(sr['camera'],sr['chain'],sr['bit'])];cell=mr['cell'];matches=[r for r in pcfrows if r['cell']==cell];entries=locs(g['primitives'][cell])
            ok=bool(matches and entries) and {r['site'] for r in matches}=={t['site']} and {r['value'] for r in entries}=={t['site']}
            bindings.append({'target':t['target'],'cell':cell,'site':t['site'],'actual_pcf':matches,'PAP_LOC_CDB':entries,'passed':ok})
        save('native_pcf_exact60_audit.json',{'rows':bindings,'passed':all(r['passed'] for r in bindings),'method':'Tcl token equality; actual mapped cell equality; every PAP_LOC/CDB entry; no substring','pcf_sha256':sha(pcf)})
        require(all(r['passed'] for r in bindings),'Actual mapped PCF/PAP_LOC site failure')
        guard();save('protection_after.json',{'status':'PASS','build03_files':len(GUARDS['build03']),'source741':741,'registered_sources':186,'full_source_tree':len(m['full_source_copy_hashes']),'original_build04_unchanged':True,'map02_unchanged':True,'protected_unchanged':True})
        save('final_result.json',{'status':'PASS_MAPPING_EXPORT_AUDIT60_ONLY','sync':sync,'reset':32,'distinct_storage':60,'mapping_receipt':load(E/'mapping_receipt.json'),'graph_binding':load(E/'graph_binding.json'),'pnr':False,'bit':False,'remote':False,'program':False,'next_gate':'Main review: complete timing/IO/bit'})
    finally:k.ReleaseMutex(handle);k.CloseHandle(handle)
if __name__=='__main__':
    try:main()
    except BaseException:
        save('actual_failure.json',{'status':'FAIL','traceback':traceback.format_exc(),'no_source_change_or_rerun':True})
        save('failure_artifact_hashes.json',{'work_files':tree(W) if W.exists() else {},'logs':{str(p):sha(p) for p in E.rglob('*.log') if p.is_file()}})
        if 'GUARDS' in globals():
            try:guard();save('protection_after_failure.json',{'status':'PASS','original_build04_unchanged':True,'build03_full_tree_unchanged':True,'map02_full_tree_unchanged':True,'source741_and186_unchanged':True})
            except BaseException:save('protection_failure.json',{'traceback':traceback.format_exc()})
        if not (E/'final_result.json').exists():save('final_result.json',{'status':'FAIL','actual_mapping_started':(E/'mapping_process.json').exists(),'actual_export_started':(E/'mapping_export_process.json').exists(),'failure':str(E/'actual_failure.json'),'pnr':False,'bit':False,'remote':False,'program':False,'no_rerun':True})
        print(traceback.format_exc(),flush=True);sys.exit(1)
