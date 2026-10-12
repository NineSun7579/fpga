"""Explicit serial twoFF experiment, preserving all prepared/frozen inputs."""
from pathlib import Path
import argparse,ctypes,hashlib,json,os,re,shutil,subprocess,sys,time,traceback
H=Path(__file__).resolve().parent
M=H.parent/'diagnostic_sync_register_map02'
E=H/'evidence'
PDS=Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,obj):(E/name).write_text(json.dumps(obj,indent=2,ensure_ascii=True)+'\n',encoding='ascii')
def check_prepared():
    expected=json.loads((E/'prepared_hashes.json').read_bytes())
    assert all(sha(H/p)==v for p,v in expected.items()),'Prepared input drift'
def check_protected():
    for name in ['protected_baseline.json','active_run_input_guard.json','build02_guard.json','map01_guard.json']:
        guard=json.loads((M/'evidence'/name).read_bytes())
        assert all(Path(p).is_file() and sha(p)==v for p,v in guard.items()),('Protected input drift',name)
def processes():
    cmd='ConvertTo-Json -InputObject @(Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,CommandLine) -Compress'
    return json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',cmd]))
def idle():
    last=None
    while True:
        current=processes();busy=[];observers=[]
        for p in current:
            if p['ProcessId']==os.getpid():continue
            command=p.get('CommandLine') or '';name=p['Name'].lower()
            wait=re.search(r'(?i)Wait-Process\b[^;\r\n]*',command)
            normalized=command.replace('\\','/').lower()
            self_wait=wait and str(os.getpid()) in re.findall(r'\d+',wait[0])
            gate_wait='source_diagnostics_timing_build_0' in normalized and bool(re.search(r'controller0[23]\.py',command))
            own=H.name.lower() in normalized
            if name in {'pds.exe','pds_shell.exe','ta.exe'}:busy.append(p)
            elif self_wait or gate_wait:observers.append(p)
            elif not own and 'board_v7/' in normalized and re.search(r'\w+\.py',command) and name in {'python.exe','pythonw.exe','powershell.exe','pwsh.exe','cmd.exe'}:busy.append(p)
        key=sorted(p['ProcessId'] for p in busy)
        if key!=last:
            save('queue_actual.json',{'busy':busy,'dependent_observers':observers,'time':time.time()})
            print('等待前序完整退出' if busy else '全机 PDS/GUI idle',key,flush=True);last=key
        if not busy:return
        time.sleep(5)
def tool(arm,label,command):
    check_prepared();check_protected()
    log=arm/'evidence'/(label+'.log');assert not log.exists()
    with log.open('xb') as f:result=subprocess.run(list(map(str,command)),cwd=arm,stdout=f,stderr=subprocess.STDOUT)
    raw=log.read_bytes()
    rejected=[x.decode('ascii','backslashreplace') for x in raw.splitlines() if x.startswith(b'E:') or re.match(rb'\s*(?:\*\*\s*)?(?:ERROR|FATAL)\b',x) or re.search(rb'(unknown|unsupported|unrecognized|ignor\w*|invalid).*(option|attribute|target|instance|impl|site)|(option|attribute).*not supported|Tcl.*(?:error|fail)',x,re.I)]
    receipt={'command':list(map(str,command)),'exit':result.returncode,'rejected_lines':rejected,'log_sha256':sha(log)}
    (log.with_suffix('.json')).write_text(json.dumps(receipt,indent=2),encoding='ascii')
    assert result.returncode==0 and not rejected,(label,receipt)
    check_prepared();check_protected();return raw
def exported(arm,stage,db):
    dest=arm/'evidence'/stage;dest.mkdir()
    analysis=dest/'analysis';analysis.mkdir()
    dump=dest/'synthesis_export/synthesis_dump.txt';dump.parent.mkdir()
    script=dest/'export.tcl'
    script.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n.switch_db -input {'+db.as_posix()+'} -output {'+dump.as_posix()+'}\n',encoding='ascii')
    before=sha(db);tool(arm,stage+'_export',[PDS,'-file',script,'-work_dir',dest,'-project_name','probe03_'+stage])
    assert sha(db)==before
    parser=analysis/'parse_objects.py';shutil.copy2(H/'execution/parse_objects.py',parser)
    result=subprocess.run([sys.executable,str(parser)],cwd=analysis,capture_output=True)
    (analysis/'parser.log').write_bytes(result.stdout+result.stderr);assert result.returncode==0
    graph=analysis/'graph.json'
    (dest/'hashes.json').write_text(json.dumps({'adf_sha256':before,'dump_sha256':sha(dump),'graph_sha256':sha(graph),'parser_sha256':sha(parser)},indent=2),encoding='ascii')
    return json.loads(graph.read_bytes())
def params(rec):
    def leaf(v):return leaf(v[-1]) if isinstance(v,list) else v.strip('"')
    return {p[1]:leaf(p[-1]) for p in rec.get('default_parameters',[])+rec.get('parameters',[]) if len(p)>=3}
def audit_graph(g,stage):
    pn=g['pin_net'];pr=g['primitives'];np=g['netpins'];aliases=g['net_aliases'];rows=[]
    def drivers(n):return [p for p in np.get(n,[]) if pr[p.rsplit('/',1)[0]]['ports'][p.rsplit('/',1)[1]]['direction']=='OUTPUT']
    def roots(n,seen=None):
        seen=set() if seen is None else set(seen)
        if n in seen:return set()
        seen.add(n);ans={x for x in ['clk','rst','d'] if any(a in {x,'/'+x,'/@'+x} for a in aliases.get(n,[]))}
        for d in drivers(n):
            c=d.rsplit('/',1)[0];r=pr[c]
            if any(w in r['type'].upper() for w in ['DFF','SRL','LUT6Q','GOPQ']):continue
            for p,v in r['ports'].items():
                if v['direction']=='INPUT' and c+'/'+p in pn:ans|=roots(pn[c+'/'+p],seen)
        return ans
    for index in range(2):
        target='ff'+str(index)
        cells=[c for c,r in pr.items() if (c==target or c.startswith(target+'/')) and ('D' in r['ports']) and ('CLK' in r['ports'] or any(v['clock'] for v in r['ports'].values()))]
        row={'target':target,'cells':cells,'checks':{'one_actual_storage_cell':len(cells)==1}}
        if len(cells)==1:
            c=cells[0];r=pr[c];p=params(r);physical=stage=='mapping';clk='CLK' if 'CLK' in r['ports'] else next(k for k,v in r['ports'].items() if v['clock']);reset='RS' if physical else 'C'
            q='Q' if 'Q' in r['ports'] else 'Q0'
            row.update({'actual_cell':c,'type':r['type'],'parameters':p,'attributes':r['attributes'],'cdb_entries':r.get('cdb_entries',[]),'D_net':pn.get(c+'/D'),'Q_net':pn.get(c+'/'+q),'clock_net':pn.get(c+'/'+clk),'reset_net':pn.get(c+'/'+reset)})
            row['checks'].update({'distinct_FF_not_pack':not any(w in r['type'].upper() for w in ['SRL','LUT6QQ','RAM']),'all_endpoints_connected':all(c+'/'+k in pn for k in ['D',clk,reset,q]),'correct_clock_domain':roots(pn.get(c+'/'+clk))=={'clk'},'correct_reset_source':roots(pn.get(c+'/'+reset))=={'rst'},'INIT_and_GRS':p.get('FF_INIT',p.get('FF0_INIT'))=='0' and p.get('GRS_EN')=='TRUE' if physical else p.get('INIT')=='0' and p.get('GRS_EN')=='TRUE'})
            if physical:row['checks'].update({'async_clear':p.get('FF_RS',p.get('FF0_RS'))=='RESET' and p.get('RS_MODE')=='ASYNC','positive_clock_and_reset_polarity':p.get('CLK_POL')=='FALSE' and p.get('LRS_POL')=='FALSE','reset_enabled':p.get('LRS_EN')=='TRUE','CE_disabled_or_one':p.get('LCE_EN')=='FALSE' or any(a.endswith('/@$constant_1') for a in aliases.get(pn.get(c+'/CE'),[]))})
            else:
                if 'CE' in r['ports']:
                    row['checks']['CE_always_enabled']=any(a.endswith('/@$constant_1') for a in aliases.get(pn.get(c+'/CE'),[]))
                    row['CE_binding']='Connected CE must be constant one'
                else:
                    row['checks']['CE_always_enabled']=r['type']=='GTP_DFF_C' and set(r['ports'])=={'Q','D','CLK','C'}
                    row['CE_binding']='Exact GTP_DFF_C has no CE; official primitive samples each positive clock edge'
        rows.append(row)
    independent=len({r.get('actual_cell') for r in rows if r.get('actual_cell')})==2
    adjacency=all(r.get('actual_cell') for r in rows) and rows[0]['Q_net']==rows[1]['D_net']
    first_input=bool(rows[0].get('D_net')) and roots(rows[0]['D_net'])=={'d'}
    return {'stage':stage,'rows':rows,'distinct_cells':independent,'Q0_to_D1':bool(adjacency),'D0_original_input':first_input,'passed':independent and bool(adjacency) and first_input and all(all(r['checks'].values()) for r in rows)}
def main():
    final=json.loads((M/'evidence/final_result.json').read_bytes());ind=json.loads((M/'evidence/independent_audit_result.json').read_bytes())
    assert final['status']=='FAIL' and ind['status']=='FAIL'
    assert (M/'evidence/comparison_conclusion.json').exists(),'Map02 completion chain not finished'
    assert all(all(v.values()) for v in final['artifact_hash_checks'].values()),'Map02 failed for missing artifact evidence'
    check_prepared();check_protected();assert not (H/'execution').exists(),'Refuse duplicate execution'
    idle()
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p];kernel.CreateMutexW.restype=ctypes.c_void_p
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=kernel.CreateMutexW(None,True,'Global\\ov56401_PDS_single_instance')
    assert handle and ctypes.get_last_error()!=183,'Existing cooperating PDS controller owns mutex'
    try:
        assert not [p for p in processes() if p['Name'].lower() in {'pds.exe','pds_shell.exe','ta.exe'}],'PDS/GUI became busy'
        work=H/'execution';work.mkdir()
        parser_source=M/'analysis_tools/parse_objects.py'
        parser_raw=parser_source.read_bytes()
        assert parser_raw.count(b"'v7_sdt_top'")==2,'Unexpected source parser top bindings'
        parser_probe=parser_raw.replace(b"'v7_sdt_top'",b"'map03_twoff_probe'")
        (work/'parse_objects.py').write_bytes(parser_probe)
        save('parser_top_binding.json',{'source':str(parser_source),'source_sha256':sha(parser_source),
             'probe_sha256':sha(work/'parse_objects.py'),'exact_literal_replacements':2,
             'original_top':'v7_sdt_top','probe_top':'map03_twoff_probe',
             'graph_algorithm_changed':False,'production_parser_modified':False})
        save('execution_frozen_inputs.json',{'prepared_manifest_sha256':sha(E/'prepared_hashes.json'),'map02_final_sha256':sha(M/'evidence/final_result.json'),'map02_audit_sha256':sha(M/'evidence/independent_audit_result.json'),'runner_sha256':sha(Path(__file__)),'parser_sha256':sha(work/'parse_objects.py')})
        results={}
        for name in ['baseline','site']:
            arm=work/name;shutil.copytree(H/name,arm);(arm/'evidence').mkdir()
            rawc=tool(arm,'compile',[PDS,'-project',arm/'project.pds','-run','compile','-work_dir',arm])
            raws=tool(arm,'synthesis',[PDS,'-project',arm/'project.pds','-run','synthesize','-work_dir',arm])
            assert b'Process "Compile" done.' in rawc and b'Process "Synthesize" done.' in raws
            results[name]={}
            for stage,folder,suffix,native in [('compile','compile','comp','cmr.db'),('synthesis','synthesize','syn','snr.db')]:
                db=arm/folder/('map03_twoff_probe_'+suffix+'.adf');ndb=arm/folder/native
                graph=exported(arm,stage,db);audit=audit_graph(graph,stage)
                results[name][stage]=audit
                (arm/'evidence'/(stage+'_artifact.json')).write_text(json.dumps({'adf':str(db),'adf_sha256':sha(db),'native_db':str(ndb),'native_db_sha256':sha(ndb),'endpoint_audit':audit},indent=2),encoding='ascii')
                assert audit['passed'],(name,stage,audit)
            syn=arm/'synthesize/map03_twoff_probe_syn.adf';script=arm/'evidence/actual_map.tcl'
            script.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\nadd_constraint {'+(arm/'constraints/clock.fdc').as_posix()+'}\nadd_constraint {'+(arm/'constraints/site.lcf').as_posix()+'}\ndev_map -force_to_run -input_db_file {'+syn.as_posix()+'} -override_pcf true -devmap_remove_dups 0 -devmap_const_prop 0 -devmap_control_set_num 0\nexport_fdc -file {'+(arm/'device_map/actual_roundtrip.fdc').as_posix()+'}\n',encoding='ascii')
            raw=tool(arm,'mapping',[PDS,'-file',script,'-work_dir',arm,'-project_name','map03_twoff_probe'])
            assert b'Process "Device Map" done.' in raw
            db=arm/'device_map/map03_twoff_probe_map.adf';ndb=arm/'device_map/dmr.db'
            graph=exported(arm,'mapping',db);audit=audit_graph(graph,'mapping');results[name]['mapping']=audit
            (arm/'evidence/mapping_artifact.json').write_text(json.dumps({'adf':str(db),'adf_sha256':sha(db),'native_db':str(ndb),'native_db_sha256':sha(ndb),'endpoint_audit':audit},indent=2),encoding='ascii')
            if name=='site':
                pcf=arm/'device_map/map03_twoff_probe.pcf';fdc=arm/'device_map/actual_roundtrip.fdc';assert pcf.is_file() and fdc.is_file()
                pt=pcf.read_bytes().decode('ascii',errors='backslashreplace');ft=fdc.read_bytes().decode('ascii',errors='backslashreplace')
                bindings=[]
                for row,site in zip(audit['rows'],['CLMA_33_450','CLMA_45_462']):
                    cell=row.get('actual_cell','MISSING')
                    actual=[line for line in pt.splitlines() if re.search(r'\bdef_inst_site\s+\{?\\?'+re.escape(cell)+r'\}?\s+'+site+r'\s+impl_devCQ0(?:\s|$)',line)]
                    roundtrip=[line for line in ft.splitlines() if row['target'] in line and site in line and 'impl_devCQ0' in line and 'PAP_LOC' in line]
                    bindings.append({'logical_target':row['target'],'actual_cell':cell,'site':site,'impl':'impl_devCQ0','actual_PCF_lines':actual,'actual_export_fdc_lines':roundtrip,'passed':bool(actual and roundtrip)})
                results[name]['constraint_binding']={'rows':bindings,'pcf_sha256':sha(pcf),'export_fdc_sha256':sha(fdc),'passed':all(r['passed'] for r in bindings)}
        check_prepared()
        passed=results['site']['mapping']['passed'] and results['site']['constraint_binding']['passed']
        baseline_packed=not results['baseline']['mapping']['distinct_cells']
        save('actual_final_result.json',{'status':'PASS_METHOD_ONLY' if passed else 'FAIL','results':results,'scope':'twoFF constraint/endpoint method probe only; no 60-cell production gate acceptance','baseline_exhibits_packing':baseline_packed,'anti_packing_effect_demonstrated':passed and baseline_packed,'limitation':'If baseline already has two independent cells, successful site binding establishes constraint support only, not packing inhibition','production_gate':'BLOCKED','remote_or_device':False})
    finally:
        if handle:kernel.CloseHandle(handle)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',action='store_true');args=parser.parse_args()
    if not args.run:
        check_prepared();print('Only checked frozen prepared hashes; explicit --run and completed map02 FAIL required')
    else:
        try:main()
        except BaseException:
            save('actual_failure.json',{'status':'FAIL','traceback':traceback.format_exc(),'production_gate':'BLOCKED','scope':'twoFF probe'})
            save('actual_final_result.json',{'status':'FAIL','reason':'See actual_failure.json; no ignored errors accepted','production_gate':'BLOCKED'})
            raise
