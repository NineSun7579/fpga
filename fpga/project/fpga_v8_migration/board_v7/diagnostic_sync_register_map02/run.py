"""Serial isolated experiment, queued after all existing controllers and finishers."""
from pathlib import Path
import collections, hashlib, json, os, re, subprocess, sys, time, traceback
HERE=Path(__file__).resolve().parent
E=HERE/'evidence'
PDS=Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')
PRIOR={'recover_compile_attempt.py','run_pds.py','physical_flow.py','run_exact11.py','resume_exact11.py','run_map_audit14.py','run_stage_map13.py','summarize_exact11.py','audit_fixed.py','finalize_exact11.py','run_export_fdc17.py','run_mapped_timing15.py','resolve_mapped14.py','verify_routed11.py'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,v): (E/name).write_bytes((json.dumps(v,indent=2,ensure_ascii=True)+'\n').encode('ascii'))
def processes():
    cmd='ConvertTo-Json -InputObject @(Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,CommandLine) -Compress'
    return json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',cmd]))
def wait_queue():
    last=None
    while True:
        busy=[];observers=[]
        for p in processes():
            if p['ProcessId']==os.getpid():continue
            name=p['Name'].lower(); command=p.get('CommandLine') or ''
            wait=re.search(r'(?i)Wait-Process\b[^;\r\n]*',command)
            if wait and str(os.getpid()) in re.findall(r'\d+',wait[0]):
                observers.append(p);continue
            scripts=set(re.findall(r'([A-Za-z_0-9]+\.py)\b',command))
            normalized=command.replace('\\','/').lower()
            own=HERE.name.lower() in normalized
            gate_waiter='source_diagnostics_timing_build_02' in normalized and 'controller02.py' in scripts
            full_controller='board_v7/' in normalized and bool(scripts) and not own and not gate_waiter
            if name in {'pds.exe','pds_shell.exe','ta.exe'} or (name in {'python.exe','pythonw.exe','powershell.exe','pwsh.exe','cmd.exe'} and (scripts & PRIOR or full_controller) and not own and not gate_waiter): busy.append(p)
        key=sorted(p['ProcessId'] for p in busy)
        if key!=last:
            save('queue_latest.json',{'time':time.time(),'busy':busy,'self_dependent_observers':observers,'observed_processes':processes(),'policy':'Observe full board_v7 controller lifetimes plus global PDS/TA. Exclude own comparison, build02 gate waiter and observers explicitly waiting for this controller; prevent prerequisite deadlock.'})
            print('WAIT_EXISTING_CONTROLLERS' if busy else 'QUEUE_CLEAR',key,flush=True);last=key
        if not busy:return
        time.sleep(5)
def verify():
    guard=json.loads((E/'protected_baseline.json').read_bytes())
    bad=[p for p,h in guard.items() if not Path(p).is_file() or sha(Path(p))!=h]
    save('protected_latest.json',{'count':len(guard),'mismatches':bad});assert not bad
    for filename in ['map01_guard.json','build02_guard.json','active_run_input_guard.json']:
        baseline=json.loads((E/filename).read_bytes())
        drift=[p for p,h in baseline.items() if not Path(p).is_file() or sha(Path(p))!=h]
        save(filename.replace('_guard.json','_guard_latest.json'),{'count':len(baseline),'mismatches':drift})
        assert not drift,(filename,drift)
    frozen=json.loads((E/'input_hashes.json').read_bytes())
    assert all(sha(HERE/p)==h for p,h in frozen.items() if p!='project.pds'),'Offline input drift'
def run(label,command,cwd=HERE):
    wait_queue();verify()
    assert not (E/(label+'.log')).exists(),label
    save(label+'_launch.json',{'time':time.time(),'command':list(map(str,command)),'cwd':str(cwd)})
    print('RUNNING',label,flush=True)
    with (E/(label+'.log')).open('xb') as log:r=subprocess.run(list(map(str,command)),cwd=cwd,stdout=log,stderr=subprocess.STDOUT)
    raw=(E/(label+'.log')).read_bytes()
    errors=[l.decode('ascii','backslashreplace') for l in raw.splitlines() if l.startswith(b'E:') or re.match(rb'\s*(?:\*\*\s*)?(?:ERROR|FATAL)\b',l) or re.search(rb'(?:unknown|unsupported|unrecognized|ignor\w*).*(?:option|attribute)|(?:option|attribute).*not supported',l,re.I)]
    save(label+'_result.json',{'exit_code':r.returncode,'errors':errors,'log_sha256':sha(E/(label+'.log'))})
    verify();assert r.returncode==0 and not errors,(label,errors)
    return raw
def export(label,db):
    dest=E/label;analysis=dest/'analysis';dump=dest/'synthesis_export/synthesis_dump.txt'
    analysis.mkdir(parents=True);dump.parent.mkdir()
    script=dest/'export.tcl'
    script.write_bytes(('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n.switch_db -input {'+db.as_posix()+'} -output {'+dump.as_posix()+'}\n').encode('ascii'))
    before=sha(db)
    run(label+'_export',[PDS,'-file',script,'-work_dir',dest,'-project_name','syncmap01_'+label],dest)
    assert sha(db)==before
    parser=analysis/'parse_objects.py';parser.write_bytes((HERE/'analysis_tools/parse_objects.py').read_bytes())
    r=subprocess.run([sys.executable,str(parser)],cwd=analysis,capture_output=True)
    (analysis/'parser.log').write_bytes(r.stdout+r.stderr);assert r.returncode==0,r.stderr
    save(label+'_export_hashes.json',{'adf_sha256':before,'dump_sha256':sha(dump),'graph_sha256':sha(analysis/'graph.json'),'verilog_sha256':sha(dump.with_suffix('.v')) if dump.with_suffix('.v').exists() else None})
    return json.loads((analysis/'graph.json').read_bytes())
def audit(label,g,reference=None):
    # Resolve kept logical Q net names through actual graph aliases, then physical drivers.
    rows=[];pins=g['pin_net'];prims=g['primitives'];aliases=g['net_aliases'];netpins=g['netpins']
    def transparent(n):
        seen=set()
        while n not in seen:
            seen.add(n)
            drivers=[p for p in netpins.get(n,[]) if prims[p.rsplit('/',1)[0]]['ports'][p.rsplit('/',1)[1]]['direction']=='OUTPUT']
            if len(drivers)!=1:return n,drivers
            cell=drivers[0].rsplit('/',1)[0];rec=prims[cell]
            if 'KEEPBUF' not in rec['type'].upper() and rec['type'].lower() not in {'syn_keepbuf','keepbuf'}:return n,drivers
            inputs=[cell+'/'+p for p,v in rec['ports'].items() if v['direction']=='INPUT']
            output_port=drivers[0].rsplit('/',1)[1]
            index=re.search(r'\[\d+\]$',output_port)
            if index:inputs=[p for p in inputs if p.endswith(index[0])]
            if len(inputs)!=1:return n,drivers
            n=pins.get(inputs[0],n)
        return n,[]
    for cam in range(4):
        prefix=f'source_diagnostics/cameras[{cam}].'
        for chain,count in [('ack_sync',2),('req_sync',3),('overrun_sync',2),('cr',2),('hr',2),('reset_pipe',4)]:
            parent=prefix+('source/' if chain!='reset_pipe' else '')
            for bit in range(count):
                logical=parent+f'{chain}[{bit}]';instance=parent+f'{chain}_ff{bit}'
                netalias=(parent.rstrip('/')+'/@'+f'{chain}[{bit}]') if chain!='reset_pipe' else f'source_diagnostics/@cameras[{cam}].reset_pipe[{bit}]'
                matches=[n for n,a in aliases.items() if netalias in a]
                for direct in [instance+'/Q',logical+'/Q']:
                    if direct in pins:matches.append(pins[direct])
                matches=sorted(set(matches))
                drivers=[]
                for n in matches:drivers.extend(transparent(n)[1])
                drivers=sorted(set(drivers));cells=sorted({p.rsplit('/',1)[0] for p in drivers})
                binding_method='actual_Q_alias_or_primitive_Q_pin'
                if not cells:
                    candidates=[c for c,r in prims.items() if (c.startswith(instance+'/') or c.startswith(logical+'/')) and ('RS' in r['ports'] or 'CLK' in r['ports'])]
                    if len(candidates)==1:
                        cells=candidates;binding_method='actual_physical_cell_under_logical_instance'
                        c=cells[0]
                        drivers=[c+'/'+p for p,v in prims[c]['ports'].items() if v['direction']=='OUTPUT' and p in {'Q','Q0'} and c+'/'+p in pins]
                        matches=sorted({pins[p] for p in drivers})
                packed_from=None
                if not cells and bit and reference and rows:
                    prev=rows[-1]
                    if prev['camera']==cam and prev['chain']==chain and len(prev['cells'])==1 and 'SRL2' in prims[prev['cells'][0]]['type'].upper():
                        rp=reference['pin_net']
                        for before,after in [(parent+f'{chain}_ff{bit-1}',instance),(parent+f'{chain}[{bit-1}]',logical)]:
                            if before+'/Q' in rp and after+'/D' in rp and rp[before+'/Q']==rp[after+'/D'] and rp.get(before+'/CLK')==rp.get(after+'/CLK'):
                                cells=prev['cells'];c=cells[0];packed_from=prev['logical'];binding_method='verified_synthesis_adjacent_Q_to_D_inside_SRL2'
                                drivers=[c+'/Q0'] if c+'/Q0' in pins else []
                                matches=[pins[p] for p in drivers];break
                rec={'camera':cam,'chain':chain,'bit':bit,'logical':logical,'expected_instance':instance,'q_alias':netalias,'matching_nets':matches,'drivers':drivers,'cells':cells,'records':{c:prims[c] for c in cells},'pins':{c:{p:pins.get(c+'/'+p) for p in prims[c]['ports']} for c in cells}}
                rec['binding_method']=binding_method
                rec['packed_from']=packed_from
                # Compiler primitive cell names, synthesis GTP and physical DFF all require real D/clock/reset ports.
                independent=len(cells)==1 and len(drivers)==1
                if independent:
                    c=cells[0];r=prims[c];portset=set(r['ports']);clock=[p for p,v in r['ports'].items() if v['clock']]
                    if not clock and 'CLK' in portset and r['type'].startswith(('GTP_DFF','gopQ','gopSRL')):clock=['CLK']
                    reset=[p for p in portset if p in {'C','P','RS','CLR','PRE'}]
                    independent='D' in portset and bool(clock) and bool(reset) and not any(t in r['type'].upper() for t in ['SRL','DRM','RAM','LUT6QQ'])
                    rec.update({'D':c+'/D' if 'D' in portset else None,'clock_endpoints':[c+'/'+p for p in clock],'reset_endpoints':[c+'/'+p for p in reset]})
                rec['independent_endpoint_passed']=independent;rows.append(rec)
    allcells=[r['cells'][0] for r in rows if r['independent_endpoint_passed']]
    result={'stage':label,'status':'PASS' if len(allcells)==60 and len(set(allcells))==60 else 'FAIL','expected':60,'independent_registers':len(set(allcells)),'independent_sync':sum(r['independent_endpoint_passed'] for r in rows if r['chain'] in {'ack_sync','req_sync','overrun_sync'}),'independent_reset':sum(r['independent_endpoint_passed'] for r in rows if r['chain'] in {'cr','hr','reset_pipe'}),'physical_types':dict(collections.Counter(v['type'] for v in prims.values())),'rows':rows,'boundary':'Independent real storage cells and endpoints only. Functional regression remains original candidate evidence; this is not routed STA signoff.'}
    save(label+'_topology.json',result);return result
def main():
    assert not (E/'final_result.json').exists()
    verify();wait_queue()
    results={}
    for label,stage,folder,suffix,native,mark in [('compile','compile','compile','comp','cmr.db','Compile'),('synthesis','synthesize','synthesize','syn','snr.db','Synthesize'),('mapping','dev_map','device_map','map','dmr.db','Device Map')]:
        db=HERE/folder/('v7_sdt_top_'+suffix+'.adf')
        assert not db.exists()
        if stage=='dev_map':
            script=E/'map.tcl'
            script.write_bytes(('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\nadd_constraint {'+(HERE/'constraints/clock.fdc').as_posix()+'}\ndev_map -force_to_run -input_db_file {'+(HERE/'synthesize/v7_sdt_top_syn.adf').as_posix()+'} -devmap_remove_dups 0 -devmap_const_prop 0 -devmap_control_set_num 0\n').encode('ascii'))
            raw=run(label,[PDS,'-file',script,'-work_dir',HERE])
        else:raw=run(label,[PDS,'-project',HERE/'project.pds','-run',stage,'-work_dir',HERE])
        assert db.exists() and db.stat().st_size
        ndb=HERE/folder/native;assert ndb.exists()
        receipt={'adf':str(db),'adf_sha256':sha(db),'native_db':str(ndb),'native_db_sha256':sha(ndb),'official_done_lines':[l.decode('ascii','backslashreplace') for l in raw.splitlines() if b'Process "' in l and b'done.' in l]}
        assert any('Process "'+mark+'" done.' in l for l in receipt['official_done_lines']),receipt
        save(label+'_artifact.json',receipt)
        g=export(label,db);results[label]=audit(label,g)
    verify()
    save('final_result.json',{'status':results['mapping']['status'],'stages':{k:{n:v[n] for n in ['status','independent_registers','independent_sync','independent_reset']} for k,v in results.items()},'options':{'devmap_remove_dups':0,'devmap_const_prop':0,'devmap_control_set_num':0},'no_timing_relaxation':True,'routed':False,'remote_or_program':False,'protected_count':len(json.loads((E/'protected_baseline.json').read_bytes()))})
    print('COMPLETED',results['mapping']['status'],flush=True)
if __name__=='__main__':
    try:main()
    except BaseException:
        save('failure.json',{'traceback':traceback.format_exc(),'remote_or_program':False});raise
