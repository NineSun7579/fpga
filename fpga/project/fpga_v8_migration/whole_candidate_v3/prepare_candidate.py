"""Replay reviewed production binding into a fresh v3. No external writes/PDS."""
from pathlib import Path
import sys, re, json, hashlib, importlib.util, difflib
from collections import defaultdict, deque
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
M = HERE.parent
BASE = M/'whole_candidate_v2'
GUARD = M/'reset_fault_guard'

def load_module(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    obj=importlib.util.module_from_spec(spec); spec.loader.exec_module(obj); return obj

helpers=load_module('v2_helpers',BASE/'build_candidate.py')
sys.modules['build_candidate']=helpers
audit=load_module('v2_audit',BASE/'audit_candidate.py')
binding=load_module('rfg_binding',GUARD/'build_binding.py')
sha=lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
digest=lambda b: hashlib.sha256(b).hexdigest()

def put(rel, data):
    p=HERE/rel; assert p.resolve().is_relative_to(HERE)
    p.parent.mkdir(parents=True,exist_ok=True)
    if isinstance(data,bytes): p.write_bytes(data)
    else: p.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8')

def guarded_paths():
    files=[]
    for root in [BASE,M/'whole_candidate',M/'whole_candidate_v2_route_01']:
        for sub in ['inputs','rtl']:
            files += [p for p in (root/sub).rglob('*') if p.is_file()]
    files += [BASE/'project.pds',M/'whole_candidate/project.pds']
    for root in [GUARD,M/'whole_reset_contract_01',M/'capture_arm_contract',M/'pcie_h2f_transport_contract']:
        files += [p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    for sub in ['source','ipcore']:
        files += [p for p in (M.parent/sub).rglob('*') if p.is_file()]
    return sorted(set(files))

def snapshot(paths): return {str(p):sha(p) for p in paths}

def numeric(text, params):
    text=text.strip()
    if '?' in text:
        condition, choices=text.split('?',1); yes,no=choices.split(':',1)
        return numeric(yes if numeric(condition,params) else no,params)
    text=re.sub(r"(\d+)'([hbd])([0-9a-fA-F_]+)",lambda m:str(int(m[3].replace('_',''),{'h':16,'b':2,'d':10}[m[2]])),text)
    for k,v in params.items(): text=re.sub(r'\b'+k+r'\b',str(v),text)
    while '$clog2' in text:
        text=re.sub(r'\$clog2\(([^()]*)\)',lambda m:str((numeric(m[1],{} )-1).bit_length()),text)
    assert re.fullmatch(r'[\d\s+*/%()<>|&~^-]+',text),text
    return int(eval(text,{'__builtins__':{}},{}))

def parameters(data, supplied=None, outer=None):
    clean=helpers.uncomment(data)
    result={}
    mh=re.search(rb'\bmodule\s+\w+\s*#\s*\(',clean)
    if mh:
        start=mh.end()-1; stop=helpers.balanced(clean,start)
        for part in clean[start+1:stop-1].split(b','):
            part=re.sub(rb'^\s*parameter\s+',b'',part)
            part=re.sub(rb'^\s*(?:integer|signed)\s+',b'',part)
            part=re.sub(rb'^\s*\[[^]]+\]\s*',b'',part)
            m=re.match(rb'\s*(\w+)\s*=\s*(.*?)\s*$',part,re.S)
            assert m,part
            name=m[1].decode(); val=m[2].decode()
            if val.startswith('"'):
                result[name]=val; continue
            try: result[name]=numeric(val,result)
            except (AssertionError,ValueError,SyntaxError): pass
    for k,v in (supplied or {}).items():
        if v.startswith('"'): continue
        result[k]=numeric(v,outer or {})
    return result

def port_schema(data, params):
    data=re.sub(rb'(output\s+reg\s+\w+)\s*=\s*0',rb'\1',data)
    data=re.sub(rb'\$clog2\(([^()]*)\)',lambda m:str((numeric(m[1].decode(),params)-1).bit_length()).encode(),data)
    return helpers.ports(data,params)

def actual_instances(data):
    clean=helpers.uncomment(data)
    pattern=rb'(?<![\w.$])\b(\w+)(?:\s*#\s*(?=\()|\s+(?=\w+\s*\())'
    for m in re.finditer(pattern,clean):
        pos=m.end(); params={}
        if clean[pos:pos+1]==b'(':
            stop=helpers.balanced(clean,pos)
            params=dict((k.decode(),v.decode().strip()) for k,v in re.findall(rb'\.(\w+)\s*\(([^()]*)\)',clean[pos:stop]))
            pos=stop
        tail=re.match(rb'\s*(\w+)\s*\(',clean[pos:])
        if not tail: continue
        start=pos+tail.end()-1; stop=helpers.balanced(clean,start)
        text=clean[start+1:stop-1]; pairs=[]
        for p in re.finditer(rb'\.(\w+)\s*\(',text):
            a=p.end()-1; z=helpers.balanced(text,a)
            pairs.append((p[1].decode(),text[a+1:z-1].decode().strip()))
        if pairs:
            assert len(pairs)==len(dict(pairs)),tail[1]
            yield {'module':m[1].decode(),'instance':tail[1].decode(),'parameters':params,'ports':dict(pairs)}

def main():
    assert not (HERE/'inputs').exists(), 'Fresh preparation only; never overwrite a candidate'
    protected=guarded_paths(); before=snapshot(protected)
    put('artifacts/protected_before.json',before)
    for p in (BASE/'inputs').rglob('*'):
        if p.is_file(): put('inputs/'+p.relative_to(BASE/'inputs').as_posix(),p.read_bytes())
    assert sum(p.is_file() for p in (HERE/'inputs').rglob('*'))==694
    receipt=json.loads((GUARD/'artifacts/results.json').read_bytes())
    assert receipt['enforced_scenarios']==19 and receipt['transport_precheck_pass']
    for name,h in receipt['source_hashes'].items():
        assert sha(BASE/'rtl'/name)==h,('v2 receipt source mismatch',name)
        assert sha(BASE/'rtl'/name)==sha(binding.SOURCE/name),('route/v2 source mismatch',name)
    original_manifest=json.loads((GUARD/'artifacts/binding_manifest.json').read_bytes())
    binding.OUT=HERE/'artifacts/binding_replay'
    # The generator retains its audited route input lookup; its output alone is redirected.
    candidates=binding.build()
    assert json.loads((binding.OUT/'binding_manifest.json').read_bytes())==original_manifest
    replay_manifest={}
    for p in (BASE/'rtl').glob('*.v'):
        n=p.stem
        if n in candidates:
            candidate=candidates[n]; name=binding.RENAMES[n]+'.v'
        else: candidate=p.read_bytes(); name=p.name
        put('rtl/'+name,candidate)
        replay_manifest[p.name]={'original_sha256':sha(p),'candidate_file':'rtl/'+name,'candidate_sha256':digest(candidate),'exact_binding_replay':n in candidates,'byte_identical':p.read_bytes()==candidate}
    put('rtl/fpga_v8_reset_fault_guard.v',(GUARD/'fpga_v8_reset_fault_guard.v').read_bytes())
    put('host/session_fault_transport.hpp',(GUARD/'session_fault_transport.hpp').read_bytes())
    put('cooperative_host/coop_host_protocol.hpp',(M/'cooperative_host/coop_host_protocol.hpp').read_bytes())
    # Compatibility products from the generator are retained only as review artifacts.
    pds=(BASE/'project.pds').read_bytes()
    for old,new in binding.RENAMES.items(): pds=re.sub(rb'\b'+old.encode()+rb'\b',new.encode(),pds)
    anchor=b'                (_file "rtl/'+binding.RENAMES[binding.NAMES[0]].encode()+b'.v"'
    assert pds.count(anchor)==1
    pds=pds.replace(anchor,b'                (_file "rtl/fpga_v8_reset_fault_guard.v"\n                    (_format verilog)\n                    (_timespec "2026-10-03T00:00:00")\n                )\n'+anchor)
    put('project.pds',pds)
    assert not (HERE/'compile_01').exists()
    (HERE/'compile_01').mkdir() # deliberately empty; parent prepares a run after v2 finishes
    put('artifacts/source_changes.json',replay_manifest)
    put('artifacts/guard_results.json',receipt)
    structural_audit(pds,candidates,replay_manifest)
    after=snapshot(protected); assert before==after,'Protected static source mutation'
    put('artifacts/protected_after.json',after)
    put('artifacts/candidate_source_sha256.json',{p.relative_to(HERE).as_posix():sha(p) for root in [HERE/'inputs',HERE/'rtl',HERE/'host',HERE/'cooperative_host'] for p in sorted(root.rglob('*')) if p.is_file()} | {'project.pds':sha(HERE/'project.pds')})
    put('artifacts/preparation.json',{'protected_static_files':len(before),'protected_before_after_identical':True,'frozen_inputs':694,'v2_rtl_files':18,'original_components':12,'v2_additions':5,'v3_guard_added':1,'v3_rtl_files':19,'compile_01_empty':not any((HERE/'compile_01').iterdir()),'pds_invoked':False,'process_inspection':False,'parent_runs_after_v2_finishes':True})
    print('Prepared v3; static protected files unchanged:',len(before))

def structural_audit(pds,candidates,replay_manifest):
    topname=binding.RENAMES[binding.NAMES[0]]
    top=(HERE/'rtl'/f'{topname}.v').read_bytes(); old=(BASE/'rtl'/f'{binding.NAMES[0]}.v').read_bytes()
    assert top==candidates[binding.NAMES[0]]
    defaults={'MEM_ROW_WIDTH':15,'MEM_BANK_WIDTH':3,'MEM_COLUMN_WIDTH':10,'MEM_DQ_WIDTH':16,'MEM_DQS_WIDTH':2}
    oldpins=helpers.ports(audit.pin_header(old),defaults); pins=helpers.ports(audit.pin_header(top),defaults)
    assert oldpins==pins
    expanded={}
    for n,(d,w) in pins.items():
        if not w: expanded[n]=d
        else:
            a,z=map(int,w[1:-1].split(':'))
            for i in range(min(a,z),max(a,z)+1): expanded[f'{n}[{i}]']=d
    prr=BASE/'baseline/top_prr.prt'; rows=[l.split(b'|') for l in prr.read_bytes().splitlines() if len(l.split(b'|'))>=7 and l.split(b'|')[4]]
    assert len(rows)==112 and len(expanded)==126
    assert all(expanded[r[4].decode()]==r[5].decode() for r in rows)
    put('baseline/top_prr.prt',prr.read_bytes())
    paths=[HERE/p.decode() for p in re.findall(rb'\(_(?:file|ip|ip_source_item)\s+"([^"]+)"',pds)]
    assert all(p.resolve().is_relative_to(HERE) and p.is_file() for p in paths)
    assert all(b'_timespec' in m for m in re.findall(rb'\(_file\s+"rtl/[^\n]+.*?\n\s*\)',pds,re.S))
    assert not any('compat_' in str(p) or 'shell' in str(p) or '/host/' in p.as_posix() for p in paths)
    sourcepaths=sorted(set(p for p in paths if p.suffix.lower() in ['.v','.sv']))
    bodies={}; modules=defaultdict(list)
    for p in sourcepaths:
        for m in re.finditer(rb'\bmodule\s+(\w+)\b(.*?)\bendmodule\b',helpers.uncomment(p.read_bytes()),re.S):
            name=m[1].decode(); modules[name].append(p.relative_to(HERE).as_posix()); bodies[name]=m[0]
    duplicates={k:v for k,v in modules.items() if len(v)>1}
    assert all(all(p.startswith('inputs/ipcore/') for p in ps) for ps in duplicates.values())
    graph=defaultdict(set)
    for name,b in bodies.items():
        for kind,inst in audit.instances(b):
            if kind in modules and kind!=name: graph[name].add(kind)
    reached=set(); todo=deque([topname])
    while todo:
        n=todo.popleft()
        if n not in reached: reached.add(n); todo.extend(graph[n]-reached)
    assert set(binding.RENAMES.values())|{'fpga_v8_reset_fault_guard'} <= reached
    assert not set(binding.NAMES)&reached
    assert 'fpga_v8_capture_control_axil_arm_v2' in reached and 'fpga_v8_capture_control_axil' not in reached
    clean=helpers.uncomment(top); top_params=parameters(top)
    widths={n:audit.width_value(w,{}) for n,(d,w) in pins.items()}
    for m in re.finditer(rb'\b(?:wire|reg)\s+(\[[^]]+\]\s*)?([^;]*);',clean):
        for part in m[2].split(b','):
            nm=re.match(rb'\s*(\w+)',part)
            if nm: widths[nm[1].decode()]=audit.width_value((m[1] or b'').strip(),top_params)
    # These two pre-existing implicit scalar nets are real DDR IP outputs in v2.
    # Record them; do not normalize production RTL as the ModelSim compatibility path does.
    inherited_implicit={}
    ddrschema=port_schema(bodies['ddr3'],parameters(bodies['ddr3']))
    for n in ['core_clk','ddr_init_done']:
        if n not in widths:
            assert ddrschema[n]==('output',''),ddrschema[n]
            assert re.search(rb'\.'+n.encode()+rb'\s*\(\s*'+n.encode()+rb'\s*\)',old)
            widths[n]=1; inherited_implicit[n]='Inherited scalar DDR IP output; unchanged v2 net'
    def exprwidth(expr):
        expr=expr.strip()
        if expr.startswith('{') and expr.endswith('}'): return sum(exprwidth(x) for x in audit.split_concat(expr[1:-1]))
        if re.fullmatch(r"\d+'[hbd][0-9a-fA-F_xz]+",expr): return int(expr.split("'")[0])
        if re.search(r'==|!=|&&|\|\||^!',expr):
            for token in re.findall(r'\b(?:v8_|rfg_)\w+',expr): assert token in widths,token
            return 1
        if expr.startswith('~'): return exprwidth(expr[1:])
        if '|' in expr or '&' in expr:
            terms=re.split(r'[|&]',expr); return max(exprwidth(x) for x in terms)
        if expr in widths: return widths[expr]
        m=re.fullmatch(r'(\w+)\[(\d+)(?::(\d+))?\]',expr)
        if m: assert m[1] in widths; return abs(int(m[2])-int(m[3]))+1 if m[3] else 1
        raise AssertionError(('undeclared expression',expr))
    connections=list(actual_instances(top)); checks=[]; omitted={}; drivers=defaultdict(list); consumers=defaultdict(list)
    newkinds={p.stem for p in (HERE/'rtl').glob('*.v')}-{topname}
    all_top_api=[]
    for obj in connections:
        kind=obj['module']
        if kind not in bodies: continue
        params=parameters(bodies[kind],obj['parameters'],top_params)
        try: schema=port_schema(bodies[kind],params)
        except AssertionError:
            assert kind not in newkinds,('new API unparsed',kind)
            continue
        assert set(obj['ports'])<=set(schema),('unknown named ports',kind,set(obj['ports'])-set(schema))
        all_top_api.append({'instance':obj['instance'],'module':kind,'named_ports':len(obj['ports']),'unconnected':sorted(set(schema)-set(obj['ports']))})
        if kind not in newkinds: continue
        omitted[obj['instance']]=sorted(set(schema)-set(obj['ports']))
        assert not omitted[obj['instance']],('new API omitted',obj['instance'],omitted[obj['instance']])
        for port,expr in obj['ports'].items():
            d,w=schema[port]
            if not expr: continue
            bits=exprwidth(expr); expected=audit.width_value(w,{})
            assert bits==expected,(kind,port,expr,bits,expected)
            checks.append({'instance':obj['instance'],'module':kind,'port':port,'expression':expr,'bits':bits})
            nets=re.findall(r'\b(?:v8_|rfg_)\w+',expr)
            if d=='output':
                assert re.fullmatch(r'[\w\s{},:\[\]]+',expr),('output expression',port,expr)
                for net in nets: drivers[net].append(obj['instance']+'.'+port)
            else:
                for n in nets: consumers[n].append(obj['instance']+'.'+port)
    # All continuous assignments, including wire initialization, participate in driver evidence.
    assign_deps={}
    for m in re.finditer(rb'\bassign\s+(\w+)\s*=\s*([^;]+);',clean):
        n=m[1].decode(); expr=m[2].decode(); assign_deps[n]=re.findall(r'\b(?:v8_|rfg_)\w+',expr)
        if n.startswith(('v8_','rfg_')): drivers[n].append('assign')
        for dep in assign_deps[n]: consumers[dep].append('assign '+n)
    for obj in connections:
        if obj['instance']=='pcie_fifo':
            for p in ['smlh_link_up','rdlh_link_up']: assert obj['ports'][p] in drivers
    multiple={n:d for n,d in drivers.items() if len(d)>1}; missing={n:d for n,d in consumers.items() if not drivers[n]}
    assert not multiple,multiple
    assert not missing,missing
    assert len(checks)>489,len(checks)
    # Internal wrapper chain named APIs and parameter override names, actual production bytes.
    chain=[]
    old_bodies={p.stem:helpers.uncomment(p.read_bytes()) for p in (BASE/'rtl').glob('*.v')}
    reverse={new:old for old,new in binding.RENAMES.items()}
    for owner in binding.RENAMES.values():
        for obj in actual_instances(bodies[owner]):
            kind=obj['module']
            if kind not in bodies: continue
            names=set(parameters(bodies[kind]))
            assert set(obj['parameters'])<=names,(owner,kind,'unknown parameter',set(obj['parameters'])-names)
            if kind in binding.RENAMES.values():
                schema=port_schema(bodies[kind],parameters(bodies[kind]))
                assert set(obj['ports'])<=set(schema),(owner,kind,'unknown port')
                omitted_ports=sorted(set(schema)-set(obj['ports']))
                prior=next(x for x in actual_instances(old_bodies[reverse[owner]]) if x['instance']==obj['instance'])
                old_schema=port_schema(old_bodies[reverse[kind]],parameters(old_bodies[reverse[kind]]))
                old_omitted=set(old_schema)-set(prior['ports'])
                connected_now=old_omitted-set(omitted_ports)
                assert not set(omitted_ports)-old_omitted
                assert not connected_now or (owner==topname and connected_now=={'smlh_link_up','rdlh_link_up'})
                chain.append({'owner':owner,**obj,'omitted':omitted_ports,'v2_omitted':sorted(old_omitted),'newly_connected_actual_link_outputs':sorted(connected_now)})
    # Concrete feedback audit: READY independent of request; engine_idle ignores lease_block.
    lease=helpers.uncomment((HERE/'rtl/fpga_v8_capture_lease.v').read_bytes())
    ready=re.search(rb'assign config_ready\s*=\s*([^;]+);',lease)[1]
    assert b'config_valid' not in ready and b'lease_block' not in ready
    wrapper=helpers.uncomment((HERE/'rtl/fpga_v8_capture_ov5640_ddr.v').read_bytes())
    idle=re.search(rb'assign engine_idle\s*=\s*([^;]+);',wrapper)[1]
    assert b'lease_block' not in idle
    assert b'assign admit_axi=axpermit[1] && !close_admission;' in bodies['fpga_v8_reset_fault_guard']
    assert b'if (healthy && aks[1] && pks[1]' in bodies['fpga_v8_reset_fault_guard']
    feedback={'config_ready':ready.decode(),'engine_idle':idle.decode(),'guard_startup_ack_and_runtime_active_registered':True,'permit_closure_depends_on_health_registered_authority_not_ready':True,'ready_independent_of_config_valid':True,'full_mapped_combinational_loop_audit_pending':True}
    # Source preservation beyond the intentional admission bindings.
    preserved={}
    for n in ['ov5640_top','cam2_ov5640_top','cam3_ov5640_top','cam4_ov5640_top','cam6_ov5640_ddr','cam5_axi_dma_write','cam6_axi_dma_write','ov5640_axi_dma_write','cam2_axi_dma_write','cam3_axi_dma_write','cam4_axi_dma_write']:
        a=audit.camera_instance(old,n); z=audit.camera_instance(top,n); assert a==z,n; preserved[n]=digest(z)
    fdc={p.relative_to(HERE).as_posix():sha(p) for p in paths if p.suffix=='.fdc'}
    assert all(sha(BASE/rel)==h for rel,h in fdc.items())
    idfs=[]
    for p in paths:
        if p.suffix!='.idf': continue
        for rel in re.findall(rb'<file\s+pathname="([^"]+)"',p.read_bytes()):
            target=(p.parent/rel.decode()).resolve(); assert target.is_relative_to(HERE)
            idfs.append({'idf':p.relative_to(HERE).as_posix(),'file':rel.decode(),'exists':target.is_file(),'resolved':target.relative_to(HERE).as_posix()})
    put('artifacts/interface_width_audit.json',checks)
    put('artifacts/top_named_api_audit.json',all_top_api)
    put('artifacts/internal_binding_api_audit.json',chain)
    put('artifacts/feedback_audit.json',feedback)
    put('artifacts/ip_relative_path_audit.json',idfs)
    put('artifacts/registered_sources.json',{p.relative_to(HERE).as_posix():sha(p) for p in paths})
    put('artifacts/structural_audit.json',{'top_module':topname,'registered_source_files':len(sourcepaths),'reachable_modules':sorted(reached),'inherited_ip_duplicates':duplicates,'inherited_top_implicit_nets':inherited_implicit,'new_duplicates':{},'named_port_width_checks':len(checks),'new_top_api_omissions':omitted,'new_multiple_drivers':multiple,'new_missing_drivers':missing,'top_pins':pins,'top_bits':126,'pcb_gpio_ddr_pads':112,'hsst_bits':14,'hsst_pins':sorted(set(expanded)-{r[4].decode() for r in rows}),'pcb_ports_identical':True,'camera_instances_preserved':preserved,'constraints_identical_to_v2':fdc,'core_clock_mhz':131.25,'root_clock':'free_clk, 25 MHz, V4/LVCMOS15','missing_clock_root_port_differences':[],'port_differences':[],'guard_parameters':parameters(bodies['fpga_v8_reset_fault_guard']),'production_binding_byte_replay':True,'legacy_controller_reachable':False,'test_shell_registered':False,'full_top_elaborated':False,'synthesis_verified':False,'board_ready':False})
    print('Actual top width checks:',len(checks),'PCB 112+14; binding APIs and driver checks pass')

def reaudit():
    before=json.loads((HERE/'artifacts/protected_before.json').read_bytes())
    assert snapshot([Path(p) for p in before])==before
    put('cooperative_host/coop_host_protocol.hpp',(M/'cooperative_host/coop_host_protocol.hpp').read_bytes())
    candidates={n:(HERE/'rtl'/(binding.RENAMES[n]+'.v')).read_bytes() for n in binding.NAMES}
    structural_audit((HERE/'project.pds').read_bytes(),candidates,json.loads((HERE/'artifacts/source_changes.json').read_bytes()))
    assert snapshot([Path(p) for p in before])==before
    put('artifacts/protected_after.json',before)
    put('artifacts/candidate_source_sha256.json',{p.relative_to(HERE).as_posix():sha(p) for root in [HERE/'inputs',HERE/'rtl',HERE/'host',HERE/'cooperative_host'] for p in sorted(root.rglob('*')) if p.is_file()} | {'project.pds':sha(HERE/'project.pds')})
    put('artifacts/preparation.json',{'protected_static_files':len(before),'protected_before_after_identical':True,'frozen_inputs':694,'v2_rtl_files':18,'original_components':12,'v2_additions':5,'v3_guard_added':1,'v3_rtl_files':19,'compile_01_empty':not any((HERE/'compile_01').iterdir()),'pds_invoked':False,'process_inspection':False,'parent_runs_after_v2_finishes':True})
    print('Prepared v3; static protected files unchanged:',len(before))

if __name__=='__main__':
    if sys.argv[1:]==['--audit']: reaudit()
    else: main()
