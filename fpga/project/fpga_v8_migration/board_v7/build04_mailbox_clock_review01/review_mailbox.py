"""Reproducible mailbox/clock-sink diagnostic; all writes are external."""
from pathlib import Path
import collections,copy,difflib,hashlib,json,re,subprocess,sys
sys.dont_write_bytecode=True
from setup_review import HERE,BOARD,B04,PREP,sha,save
sys.path.insert(0,str(HERE/'analysis'))
from graph_adapter import Resolver,require,strict_keepbuf,classify,canon
from derive_new_constraints import coll,derive
NET_EVIDENCE={}
STAGE='synthesis'
def run(cmd,name,cwd):
    original=name;i=1
    while (HERE/name).exists():
        i+=1;name=Path(original).stem+'_attempt'+str(i).zfill(2)+Path(original).suffix
    p=subprocess.run(cmd,cwd=cwd,capture_output=True)
    (HERE/name).write_bytes(p.stdout+p.stderr)
    return {'command':cmd,'exit_code':p.returncode,'log':name}
def detail(g,cell):
    r=g['primitives'][cell]
    pins={}
    for p in r['ports']:
        n=g['pin_net'].get(cell+'/'+p)
        if n is not None:NET_EVIDENCE.setdefault(STAGE,{})[n]={'netpins':g['netpins'][n],'aliases':g['net_aliases'][n]}
        pins[p]={'net':n,'complete_net_evidence_file':'complete_connected_nets_'+STAGE+'.json'}
    return {'cell':cell,'record':r,'pins':pins}
def raw_nodes(raw,terms):
    # Independent byte-level balanced node extraction. Preserve exact bytes/offsets.
    stack=[];nodes=[]
    for m in re.finditer(rb'"(?:[^"\\]|\\.)*"|\\[^\s]+|[()]|[^\s()]+',raw):
        token=m.group()
        if token==b'(':stack.append([m.start(),None,False])
        elif token==b')':
            start,kind,hit=stack.pop()
            if hit and kind in {b'INSTANCE',b'CONNECT',b'NET',b'CELL'}:
                if kind!=b'CELL':nodes.append({'offset':start,'end':m.end(),'kind':kind.decode(),'raw':raw[start:m.end()].decode('ascii','replace')})
            if stack and hit:stack[-1][2]=True
        elif stack:
            if stack[-1][1] is None:stack[-1][1]=token
            if any(t in token for t in terms):stack[-1][2]=True
    return nodes
def main():
    global STAGE
    a=HERE/'analysis'
    steps=[run([sys.executable,'-B',str(a/'resolve_manifest.py')],'fresh_resolve.log',a)]
    require(steps[-1]['exit_code']==0,'Fresh resolve failed')
    m=json.loads((a/'manifest.json').read_bytes());g=json.loads((a/'graph.json').read_bytes())
    require(not m['errors'] and len(m['resolved'])==2048,'2048 resolution failed')
    binding=json.loads((HERE/'input_binding.json').read_bytes())
    require(m['source_dump_sha256']==sha(B04/'evidence/runtime/actual/synthesis_export/synthesis_dump.txt'),'ADIF binding mismatch')
    groups=collections.defaultdict(list);logical=[];details={};constant=[]
    for row in m['resolved']:
        mp=row['mapping'];key=None
        if mp['kind']=='register':
            q,d=mp['launch_Q'],mp['capture_D'];key=(q,d)
            require(g['pin_net'][q]==g['pin_net'][d],'Q-D different nets')
            require(set(g['netpins'][g['pin_net'][q]])=={q,d},'Not exclusive mailbox pair')
            require(all(p.startswith(f"source_diagnostics/cameras[{row['camera']}].source/") for p in key),'Cross-camera pair')
            require(mp['capture_q']==mp['capture_cell']+'/Q','Receiver Q mismatch')
            require(g['primitives'][mp['launch_cell']]['type']=='GTP_DFF_CE' and g['primitives'][mp['capture_cell']]['type']=='GTP_DFF_CE','Unknown mailbox primitive')
            groups[key].append({'camera':row['camera'],'logical_bit':row['logical_bit'],'word':row['word'],'bit':row['bit']})
            for cell in [mp['launch_cell'],mp['capture_cell']]:
                if cell not in details:details[cell]=detail(g,cell)
        else:
            require(mp=={'kind':'constant_zero','value':0},'Unknown mapping kind')
            constant.append({'camera':row['camera'],'logical_bit':row['logical_bit'],'word':row['word'],'bit':row['bit']})
        logical.append({**row,'physical_pair':list(key) if key else None})
    require(len(groups)==1280 and len(constant)==728,'Actual inventory changed')
    duplicates=[{'launch_Q':q,'capture_D':d,'logical_aliases':rows,'extra_aliases':len(rows)-1} for (q,d),rows in groups.items() if len(rows)>1]
    require(sum(x['extra_aliases'] for x in duplicates)==40 and len(duplicates)==4,'Duplicate contract changed')
    expected=[480+i for i in range(32) if (0x53464401>>i)&1]
    for x in duplicates:require([r['logical_bit'] for r in x['logical_aliases']]==[240]+expected,'Unexpected duplicate bits')
    save('logical_to_physical_2048.json',{'status':'OFFLINE_DIAGNOSTIC_CONTRACT','acceptance_expected_count_updated':False,'logical_bits':logical,'physical_pairs':[{'launch_Q':q,'capture_D':d,'logical_aliases':rs} for (q,d),rs in sorted(groups.items())],'constant_zero_bits':constant,'duplicates':duplicates,'source_dump_sha256':m['source_dump_sha256'],'graph_sha256':sha(a/'graph.json'),'manifest_sha256':sha(a/'manifest.json')})
    save('complete_mailbox_primitives_netpins.json',details)
    save('complete_connected_nets_synthesis.json',NET_EVIDENCE.pop('synthesis'))
    print('2048 logical, 1320 register rows, 1280 unique pairs, 728 zero; no cross-camera pair',flush=True)
    # Verify original failure separately. Its 330/1320 acceptance gate is unchanged.
    cmd=[sys.executable,'-B',str(a/'derive_new_constraints.py'),'--compile-graph',str(B04/'evidence/runtime/compile/analysis/graph.json'),'--synthesis-graph',str(a/'graph.json'),'--mapping-manifest',str(a/'manifest.json'),'--frozen-clock',str(B04/'inputs/source/constraints/clock.fdc'),'--output',str(HERE/'frozen_gate_derive')]
    steps.append(run(cmd,'fresh_derive_frozen_gate.log',a))
    require(steps[-1]['exit_code']!=0 and b'legacy 320/camera' in (HERE/steps[-1]['log']).read_bytes(),'Frozen gate failed for unexpected reason')
    cg=json.loads((B04/'evidence/runtime/compile/analysis/graph.json').read_bytes())
    # Deliberate schema/mode counterexamples, including unknown type, must reject.
    sample=next(copy.deepcopy(r) for r in cg['primitives'].values() if r['type']=='bmsKEEPBUF_Cell_1')
    tests=[]
    for name,mut in [('width2',lambda r:r.update(default_parameters=[['PARAMETER','WIDTH',['DATATYPE','INTEGER'],['INTEGER','2']]])),('extra_control',lambda r:r['ports'].update(E={'direction':'INPUT','clock':False})),('inverted_port',lambda r:r['ports'].update({'Z[0]':{'direction':'INPUT','clock':False}})),('clock_state',lambda r:r['ports']['I[0]'].update(clock=True)),('unknown_type',lambda r:r.update(type='bmsKEEPBUF_Cell_999')),('unknown_parameter',lambda r:r.update(parameters=[['PARAMETER','INVERT',['DATATYPE','INTEGER'],['INTEGER','1']]]))]:
        r=copy.deepcopy(sample);mut(r)
        try:strict_keepbuf(r)
        except RuntimeError as exc:tests.append({'case':name,'rejected':True,'reason':str(exc)})
        else:raise RuntimeError('Nonidentity accepted '+name)
    # Unknown graph sinks are not silently dropped.
    fake={'primitives':{'bad':{'type':'UNKNOWN_CLOCK_GATE','ports':{'I':{'direction':'INPUT','clock':False}}}},'pin_net':{'bad/I':'root'},'netpins':{'root':['bad/I']},'net_aliases':{'root':['cmos1_pclk']}}
    try:Resolver(fake).clock_leaves(0)
    except RuntimeError as exc:tests.append({'case':'unknown_graph_sink','rejected':True,'reason':str(exc)})
    else:raise RuntimeError('Unknown sink accepted')
    fake['primitives']['bad']=copy.deepcopy(sample);fake['primitives']['bad']['ports']['I[0]']['clock']=True;fake['pin_net']={'bad/I[0]':'root'};fake['netpins']={'root':['bad/I[0]']}
    try:Resolver(fake).clock_leaves(0)
    except RuntimeError as exc:tests.append({'case':'nonidentity_terminal_keepbuf','rejected':True,'reason':str(exc)})
    else:raise RuntimeError('Nonidentity terminal sink accepted')
    save('identity_counterexamples.json',tests)
    raw=(B04/'inputs/source/constraints/clock.fdc').read_bytes();clocks=set();asyncgroups=[]
    for line in raw.decode('ascii').splitlines():
        line=line.lstrip()
        if line.startswith(('create_clock ','create_generated_clock ')):clocks.add(re.search(r'-name\s+\{([^}]+)\}',line)[1])
        if line.startswith('set_clock_groups '):
            require('-asynchronous' in line,'Unexpected clock group');asyncgroups.extend(re.findall(r'-group\s+\[get_clocks\s+\{?(\w+)\}?\]',line))
    u={(x,y) for x in clocks for y in clocks if x!=y and (x in asyncgroups or y in asyncgroups)};carved={(f'cmos{i+1}_pclk','ddrphy_sysclk') for i in range(4)}
    require(len(u)==368 and carved<=u and len(u-carved)==364,'Clock relation universe changed')
    lines=['# EXTERNAL DIAGNOSTIC DRAFT ONLY; independent candidate expectations/reload/STA pending.']
    lines.extend(f'set_false_path -from [get_clocks {{{x}}}] -to [get_clocks {{{y}}}]' for x,y in sorted(u-carved))
    classified=classify(g);camera_proofs=[]
    for cam in range(4):
        cp=Resolver(cg).clock_leaves(cam);sp=Resolver(g).clock_leaves(cam);pre=f'source_diagnostics/cameras[{cam}].source/'
        mb={k+'/'+p for k,r in cg['primitives'].items() if k.startswith(pre+'mailbox[') for p,v in r['ports'].items() if v['clock']}
        host={k+'/'+p for k,r in cg['primitives'].items() if k.startswith(pre+'host_bank[') for p,v in r['ports'].items() if p.startswith('D[') and v['direction']=='INPUT'}
        pairs={(r['mapping']['launch_CLK'],r['mapping']['capture_D']) for r in m['resolved'] if r['camera']==cam and r['mapping']['kind']=='register'}
        launches={x for x,y in pairs};captures={y for x,y in pairs}
        require(len(mb)==17 and len(host)==512 and mb<=set(cp['leaves']) and len(pairs)==320 and launches<=set(sp['leaves']),'Fresh camera sets invalid')
        complement=(set(cp['leaves'])-mb)|(set(sp['leaves'])-launches)
        require(not complement&(mb|launches),'Complement overlaps budget launch')
        lines.extend(['set_false_path -from '+coll(complement)+' -to [get_clocks {ddrphy_sysclk}]','set_max_delay -datapath_only 15.238 -from '+coll(mb|launches)+' -to '+coll(host|captures),'set_false_path -hold -from '+coll(mb|launches)+' -to '+coll(host|captures)])
        ack=classified['ack_first'][cam];lines.append('set_false_path -from '+coll({ack['launch_CLK']})+' -to '+coll({ack['capture_D']}))
        camera_proofs.append({'camera':cam,'compile':cp,'synthesis':sp,'compile_mailbox':sorted(mb),'compile_host':sorted(host),'physical_pairs':sorted(pairs),'complement':sorted(complement),'ack_first':ack})
    result=b'\n'.join(l for l in raw.splitlines() if not l.lstrip().startswith(b'set_clock_groups '))+b'\n'+'\n'.join(lines).encode('ascii')+b'\n'
    draft=HERE/'diagnostic_constraint_DRAFT';draft.mkdir(exist_ok=True)
    if (draft/'clock.fdc').exists():require((draft/'clock.fdc').read_bytes()==result,'Refuse changed draft')
    else:(draft/'clock.fdc').write_bytes(result)
    save('diagnostic_constraint_DRAFT/coverageproof.json',{'status':'DIAGNOSTIC_DRAFT_GATE_CLOSED','runtime_proven':False,'constraints_qualified':False,'independent_expected_count_update_required':True,'frozen_gate_1320_unchanged':True,'physical_pairs':len(groups),'register_resolution_rows':1320,'logical_bits':2048,'constant_zero':728,'U':sorted(u),'retained_clock_pairs':sorted(u-carved),'carved_camera_to_ddr':sorted(carved),'same_domain_exemptions':[],'mailbox_budget_ns':15.238,'DDR_MHz':131.25,'cameras':camera_proofs,'compile_graph_sha256':sha(B04/'evidence/runtime/compile/analysis/graph.json'),'synthesis_graph_sha256':sha(a/'graph.json'),'mapping_manifest_sha256':sha(a/'manifest.json'),'constraint_sha256':hashlib.sha256(result).hexdigest(),'logical_contract_sha256':sha(HERE/'logical_to_physical_2048.json')})
    print('fresh camera leaves/complements derived; frozen acceptance gate remains FAIL',flush=True)
    keep={}
    STAGE='compile'
    for x in camera_proofs:
        for edge in x['compile']['transparent']:
            if edge['type']=='bmsKEEPBUF_Cell_1':keep[edge['cell']]=detail(cg,edge['cell'])
    save('keepbuf_clock_details.json',keep)
    save('complete_connected_nets_compile.json',NET_EVIDENCE.pop('compile'))
    # Compare exact build01 mapping and RTL; distinguish semantic identity from optimization choice.
    STAGE='build01'
    oldroot=BOARD/'source_diagnostics_timing_build_01';oldm=json.loads((oldroot/'evidence/actual/analysis/manifest.json').read_bytes());oldg=json.loads((oldroot/'evidence/actual/analysis/graph.json').read_bytes())
    oldpairs={(r['mapping']['launch_Q'],r['mapping']['capture_D']) for r in oldm['resolved'] if r['mapping']['kind']=='register'}
    changes=[];old_details={}
    for old,new in zip(oldm['resolved'],m['resolved']):
        require((old['camera'],old['logical_bit'])==(new['camera'],new['logical_bit']),'Old manifest order mismatch')
        if old['mapping']!=new['mapping']:changes.append({'camera':new['camera'],'logical_bit':new['logical_bit'],'old':old['mapping'],'new':new['mapping']})
    for cam in range(4):
        for bit in [240]+expected:
            for bank in ['mailbox','host_bank']:
                cell=f'source_diagnostics/cameras[{cam}].source/{bank}[{bit}]';old_details[cell]=detail(oldg,cell)
    save('build01_duplicate_original_primitives.json',old_details)
    save('complete_connected_nets_build01.json',NET_EVIDENCE.pop('build01'))
    save('build01_mapping_diff.json',{'old_unique_pairs':len(oldpairs),'new_unique_pairs':len(groups),'removed_pairs':sorted(oldpairs-set(groups)),'added_pairs':sorted(set(groups)-oldpairs),'mapping_changes':changes,'optimization_cause':'Equal reset-to-zero/write-one trajectories in identical per-camera enable/clock/reset domains; build04 shares word15 one bits with word7 bit16. RTL mailbox assignments unchanged. Exact optimizer heuristic cause not inferable from exported graph.'})
    oldsrc=(oldroot/'rtl/v7_sfd_candidate.v').read_bytes().decode('ascii','replace');newsrc=(B04/'rtl/v7_sfd_candidate.v').read_bytes().decode('ascii','replace')
    (HERE/'build01_to_source03_boolean.diff').write_text(''.join(difflib.unified_diff(oldsrc.splitlines(True),newsrc.splitlines(True),fromfile='build01/v7_sfd_candidate.v',tofile='build04/source03_boolean/v7_sfd_candidate.v')),encoding='ascii')
    del oldg,cg
    # Mapped graph proof is connectivity only; endpoint storage semantics handled elsewhere.
    STAGE='mapped'
    mg=json.loads((B04/'evidence/runtime/mapping60_01/mapping/analysis/graph.json').read_bytes());mr=Resolver(mg);mapped=[]
    mapped_aliases=collections.defaultdict(set)
    for net,aa in mg['net_aliases'].items():
        for alias in aa:mapped_aliases[canon(alias)].add(net)
    for (q,d),rs in sorted(groups.items()):
        launch=q.rsplit('/',1)[0];capture=d.rsplit('/',1)[0]
        nets=mapped_aliases[canon(launch)];require(len(nets)==1,'Mapped mailbox alias net ambiguous: '+launch)
        net=next(iter(nets));drivers=mr.drivers(net);require(len(drivers)==1,'Mapped source driver ambiguous')
        actual_q=drivers[0]
        captures=[cell+'/D' for cell,r in mg['primitives'].items() if (cell==capture or cell.startswith(capture+'/')) and 'D' in r['ports'] and r['ports']['D']['direction']=='INPUT' and cell+'/D' in mg['pin_net']]
        require(len(captures)==1,'Mapped capture D not unique: '+capture);actual_d=captures[0]
        require(mg['pin_net'][actual_q]==mg['pin_net'][actual_d] and set(mg['netpins'][net])=={actual_q,actual_d},'Mapped Q-D connectivity not exclusive')
        require(actual_q.startswith(f"source_diagnostics/cameras[{rs[0]['camera']}].source/"),'Mapped cross-camera source')
        mapped.append({'synthesis_launch_Q':q,'synthesis_capture_D':d,'launch_Q':actual_q,'capture_D':actual_d,'logical_aliases':rs,'launch':detail(mg,actual_q.rsplit('/',1)[0]),'capture':detail(mg,actual_d.rsplit('/',1)[0])})
    save('mapped_1280_connectivity.json',{'semantic_signoff':False,'graph_sha256':sha(B04/'evidence/runtime/mapping60_01/mapping/analysis/graph.json'),'rows':mapped})
    save('complete_connected_nets_mapped.json',NET_EVIDENCE.pop('mapped'))
    print('mapped 1280 exact Q-D connectivity verified',flush=True)
    del mg
    # Preserve independent raw bytes evidence; absent duplicated cells cannot be fabricated by parser.
    terms=[b'mailbox[240]',b'host_bank[240]']+[f'{bank}[{bit}]'.encode() for bank in ['mailbox','host_bank'] for bit in expected]+[b'bmsKEEPBUF_Cell_1',b'ND12',b'ND18']
    rawproof=[]
    for stage in ['compile','actual','mapping60_01/mapping']:
        f=B04/'evidence/runtime'/stage/'synthesis_export/synthesis_dump.txt';raw=f.read_bytes();nodes=raw_nodes(raw,terms)
        save('raw_'+stage.replace('/','_')+'_nodes.json',{'source':str(f),'sha256':sha(f),'nodes':nodes,'duplicated_cell_token_counts':{t.decode():raw.count(b'(INSTANCE \\'+t+b' ') for t in terms if b'[' in t}})
        rawproof.append({'stage':stage,'nodes':len(nodes)})
        print('raw byte extraction',stage,len(nodes),flush=True)
    model=Path('C:/pango/PDS_2022.2-SP6.4/arch/lib/bms/verilog/bmsPrim.v');raw=model.read_bytes();start=raw.index(b'module bmsKEEPBUF ');end=raw.index(b'endmodule',start)+len(b'endmodule');snippet=raw[start:end]
    require(b'assign Z = I;' in snippet and b'parameter WIDTH = 2;' in snippet,'Official model changed')
    (HERE/'official_bmsKEEPBUF_model.v').write_bytes(snippet)
    drift=[p for p,h in binding.items() if sha(p)!=h];require(not drift,'Bound input drift')
    save('review_result.json',{'status':'OFFLINE_MAILBOX_CLOCK_DIAGNOSTIC_COMPLETE_GATE_CLOSED','steps':steps,'raw_byte_evidence':rawproof,'bound_input_drift':drift,'unique_pairs':1280,'register_resolution_rows':1320,'logical_bits':2048,'constant_zero':728,'duplicate_extra_aliases':40,'constraints_qualified':False,'runtime_STA_passed':False,'mapped_semantics_signoff':False,'pds_started':False,'remote_actions':False,'frozen_producer_consumer_changed':False,'required_next':'Independent new-candidate expectation review; actual routed 1280*2 scored MaxDelay15.238 records with exact physical-pair set and all2048 logical contract coverage; old1320 reports cannot be inherited.'})
    ledger={str(p.relative_to(HERE)):sha(p) for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    save('output_hashes.json',ledger)
    print('review complete, sealed external outputs; no PDS/STA',flush=True)
if __name__=='__main__':main()
