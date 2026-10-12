"""Independent review02: read old evidence, write only this new directory. No PDS."""
from pathlib import Path
import collections,copy,hashlib,importlib.util,itertools,json,re,shutil,subprocess,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
BOARD=HERE.parent
OLD=BOARD/'build04_mailbox_clock_review01'
B04=BOARD/'source_diagnostics_timing_build_04'
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def save(n,v):
    p=HERE/n;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def imported(name,p):
    s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
    seals=load(OLD/'final_bundle_hashes.json');assert len(seals)==58
    files={str(p.relative_to(OLD)) for p in OLD.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    assert files==set(seals)|{'final_bundle_hashes.json','output_hashes.json'}
    verified=[]
    for n,h in seals.items():
        got=sha(OLD/n);assert got==h,(n,h,got)
        verified.append({'path':n,'expected':h,'recomputed':got,'bytes':(OLD/n).stat().st_size})
    save('artifact58_rehash.json',verified)
    inputs=load(OLD/'input_binding.json')
    for p,h in inputs.items():assert sha(p)==h,('input drift',p)
    manifest=load(B04/'manifest.json');assert len(manifest['local_hashes'])==741
    local=[]
    for n,h in manifest['local_hashes'].items():
        assert sha(B04/n)==h,n;local.append({'path':n,'sha256':h})
    assert len(manifest['registered_sources'])==186 and len(set(manifest['registered_sources']))==186
    assert set(manifest['registered_sources'])<=set(manifest['registered_files'])
    for n in manifest['registered_sources']:assert (B04/n).is_file() and n in manifest['local_hashes']
    for n,h in manifest['full_source_copy_hashes'].items():assert sha(B04/n)==h,n
    for p,h in load(BOARD/'build04_route_prepare01/fresh_graph_input_binding.json').items():assert sha(p)==h,p
    save('source741_registered186_rehash.json',{'candidate_id':manifest['candidate_id'],'local':local,'registered_sources':manifest['registered_sources'],'full_source_copy_entries':len(manifest['full_source_copy_hashes']),'input_binding_verified':inputs,'manifest_sha256':sha(B04/'manifest.json'),'source04hash_sha256':sha(B04/'source04hash.json')})
    print('58 artifacts,741 local,186 registered and775 input bindings independently rehashed',flush=True)
    fresh=HERE/'fresh';fresh.mkdir(exist_ok=True)
    for n in ['resolve_manifest.py','graph_adapter.py','endpoint_logic.py','endpoint_detail.py','endpoints.py','preflight.py','derive_new_constraints.py','graph.json','objects.json']:
        shutil.copyfile(OLD/'analysis'/n,fresh/n)
    run=subprocess.run([sys.executable,'-B',str(fresh/'resolve_manifest.py')],cwd=fresh,capture_output=True)
    (HERE/'fresh_resolve.log').write_bytes(run.stdout+run.stderr);assert run.returncode==0
    m=load(fresh/'manifest.json');assert m==load(OLD/'analysis/manifest.json') and not m['errors']
    g=load(fresh/'graph.json');groups=collections.defaultdict(list);zero=set();rows={}
    for r in m['resolved']:
        k=(r['camera'],r['logical_bit']);assert k not in rows;rows[k]=r
        assert r['word']*32+r['bit']==r['logical_bit']
        mp=r['mapping']
        if mp['kind']=='constant_zero':assert mp=={'kind':'constant_zero','value':0};zero.add(k);continue
        assert mp['kind']=='register';q,d=mp['launch_Q'],mp['capture_D'];n=g['pin_net'][q]
        assert n==g['pin_net'][d] and set(g['netpins'][n])=={q,d}
        assert all(p.startswith(f"source_diagnostics/cameras[{r['camera']}].source/") for p in [q,d])
        for cell in [mp['launch_cell'],mp['capture_cell']]:assert g['primitives'][cell]['type']=='GTP_DFF_CE'
        assert mp['launch_CLK']==mp['launch_cell']+'/CLK'
        groups[(q,d)].append(k)
    assert set(rows)==set(itertools.product(range(4),range(512)))
    widths=[32,24,16,16,24,24,24,24,24,24,24,16,8,16,24]
    zeros={w*32+b for w,width in enumerate(widths) for b in range(width,32)}|{480+b for b in range(32) if not(0x53464401>>b)&1}
    aliases=[240]+[480+b for b in range(32) if (0x53464401>>b)&1]
    assert zero==set(itertools.product(range(4),zeros)) and len(zero)==728
    assert len(groups)==1280 and sum(map(len,groups.values()))==1320
    dup={q:ks for (q,d),ks in groups.items() if len(ks)>1};assert len(dup)==4
    assert sorted(dup.values())==[[(cam,b) for b in aliases] for cam in range(4)]
    for cam in range(4):assert sum(ks[0][0]==cam for ks in groups.values())==320
    oldcontract=load(OLD/'logical_to_physical_2048.json')
    assert oldcontract['logical_bits']==[{**r,'physical_pair':[r['mapping']['launch_Q'],r['mapping']['capture_D']] if r['mapping']['kind']=='register' else None} for r in m['resolved']]
    assert {(p['launch_Q'],p['capture_D']):[(x['camera'],x['logical_bit']) for x in p['logical_aliases']] for p in oldcontract['physical_pairs']}==dict(groups)
    save('fresh_exact_sets.json',{'logical2048':sorted(rows),'zero728':sorted(zero),'alias_bits_each_camera':aliases,'physical1280':[{'Q':q,'D':d,'logical_members':ks} for (q,d),ks in sorted(groups.items())],'per_camera_physical':[320]*4,'fresh_manifest_sha256':sha(fresh/'manifest.json')})
    print('fresh resolve exact2048/1320/1280/728; four11-bit groups; exclusive pair320/camera',flush=True)
    # Rerun the raw ADIF byte reader, without the graph parser. No old-tree write:
    sys.path.insert(0,str(OLD))
    reader=(OLD/'independent_adif_check.py').read_text(encoding='utf8')
    reader=reader.replace("g=json.loads(graph.read_bytes());assert set(leaf_ports)==set(g['primitives'])", "g=json.loads(graph.read_bytes());assert set(leaf_ports)==set(g['primitives'])\n    for cell,(typ,ports) in leaf_ports.items():\n        assert typ==g['primitives'][cell]['type'] and set(ports)==set(g['primitives'][cell]['ports']),cell")
    rawcopy=HERE/'raw_reader_review02.py';rawcopy.write_text(reader,encoding='utf8')
    rawmod=imported('raw_reader_review02',rawcopy)
    rawmod.save=save
    for stage in ['actual','compile','mapping60_01/mapping']:rawmod.check(stage)
    # Extend the raw reader independently to old build01, including all primitive ports/classes.
    oldroot=BOARD/'source_diagnostics_timing_build_01/evidence/actual';og=load(oldroot/'analysis/graph.json')
    cells=rawmod.read_cells((oldroot/'synthesis_export/synthesis_dump.txt').read_bytes());parent={};leaf={}
    def root(v):
        parent.setdefault(v,v)
        if parent[v]!=v:parent[v]=root(parent[v])
        return parent[v]
    def cat(*xs):return '/'.join(x for x in xs if x).lstrip('/')
    def flatten(key,path):
        ports,insts,nets=cells[key]
        for n,ends in nets:
            a=root(cat(path,'@'+n))
            for inst,p in ends:parent[root(cat(path,inst,p))]=root(a)
        for inst,typ,view in insts:
            sub=cat(path,inst)
            if cells[(typ,view)][1]:flatten((typ,view),sub)
            else:leaf[sub]=(typ,cells[(typ,view)][0])
    top=[k for k in cells if k[0]=='v7_sdt_top'];assert len(top)==1;flatten(top[0],'')
    classes=collections.defaultdict(set);pc={}
    for cell,(typ,ports) in leaf.items():
        for port in ports:
            p=cell+'/'+port
            if p in parent:pc[p]=root(p);classes[pc[p]].add(p)
    assert set(leaf)==set(og['primitives']) and set(pc)==set(og['pin_net'])
    for cell,(typ,ports) in leaf.items():assert typ==og['primitives'][cell]['type'] and set(ports)==set(og['primitives'][cell]['ports']),cell
    for p,cl in pc.items():assert classes[cl]==set(og['netpins'][og['pin_net'][p]])
    om=load(oldroot/'analysis/manifest.json');assert om['source_dump_sha256']==sha(oldroot/'synthesis_export/synthesis_dump.txt')
    op={(r['mapping']['launch_Q'],r['mapping']['capture_D']) for r in om['resolved'] if r['mapping']['kind']=='register'}
    assert len(op)==1320 and len(op-set(groups))==40 and not(set(groups)-op)
    structural=[]
    for cam in range(4):
        pre=f'source_diagnostics/cameras[{cam}].source/'
        for bank in ['mailbox','host_bank']:
            cs=[pre+f'{bank}[{b}]' for b in aliases]
            assert all(og['primitives'][c]['type']=='GTP_DFF_CE' for c in cs)
            for p in ['CLK','C','CE']:assert len({og['pin_net'][c+'/'+p] for c in cs})==1
            assert len({json.dumps(og['primitives'][c]['default_parameters'],sort_keys=True) for c in cs})==1
            for b,c in zip(aliases,cs):
                if bank=='mailbox':
                    dn=og['pin_net'][c+'/D'];assert any(a.endswith('$constant_1') for a in og['net_aliases'][dn])
                    q=c+'/Q';d=pre+f'host_bank[{b}]/D';assert classes[pc[q]]=={q,d}
            structural.append({'camera':cam,'bank':bank,'cells':cs,'common_controls':{p:og['pin_net'][cs[0]+'/'+p] for p in ['CLK','C','CE']},'default_parameters':og['primitives'][cs[0]]['default_parameters']})
    save('independent_build01_raw_and_trajectory.json',{'dump_sha256':sha(oldroot/'synthesis_export/synthesis_dump.txt'),'graph_sha256':sha(oldroot/'analysis/graph.json'),'all_connected_pins_checked':len(pc),'old_unique':1320,'removed_exact40':sorted(op-set(groups)),'added':[],'groups':structural})
    del cells,parent,leaf,pc,classes,og
    # Fresh clock-leaf resolution, strict KEEPBUF and counterexamples, full exact draft reconstruction.
    sys.path.insert(0,str(fresh));ga=imported('review02_graph_adapter',fresh/'graph_adapter.py')
    cg=load(B04/'evidence/runtime/compile/analysis/graph.json');proof=load(OLD/'diagnostic_constraint_DRAFT/coverageproof.json')
    sample=next(copy.deepcopy(r) for r in cg['primitives'].values() if r['type']=='bmsKEEPBUF_Cell_1')
    cases=[]
    muts=[('width2',lambda r:r.update(default_parameters=[['PARAMETER','WIDTH',['DATATYPE','INTEGER'],['INTEGER','2']]])),('extra_control',lambda r:r['ports'].update(E={'direction':'INPUT','clock':False})),('inverted_port',lambda r:r['ports'].update({'Z[0]':{'direction':'INPUT','clock':False}})),('clock_state',lambda r:r['ports']['I[0]'].update(clock=True)),('unknown_type',lambda r:r.update(type='bmsKEEPBUF_Cell_999')),('unknown_parameter',lambda r:r.update(parameters=[['PARAMETER','INVERT',['DATATYPE','INTEGER'],['INTEGER','1']]]))]
    for name,mut in muts:
        r=copy.deepcopy(sample);mut(r)
        try:ga.strict_keepbuf(r)
        except RuntimeError as e:cases.append({'case':name,'rejected':True,'reason':str(e)})
        else:raise AssertionError(name)
    fake={'primitives':{'bad':{'type':'UNKNOWN_CLOCK_GATE','ports':{'I':{'direction':'INPUT','clock':False}}}},'pin_net':{'bad/I':'root'},'netpins':{'root':['bad/I']},'net_aliases':{'root':['cmos1_pclk']}}
    for name in ['unknown_graph_sink','nonidentity_terminal_keepbuf']:
        if name.startswith('nonidentity'):
            fake['primitives']['bad']=copy.deepcopy(sample);fake['primitives']['bad']['ports']['I[0]']['clock']=True
            fake['pin_net']={'bad/I[0]':'root'};fake['netpins']={'root':['bad/I[0]']}
        try:ga.Resolver(fake).clock_leaves(0)
        except RuntimeError as e:cases.append({'case':name,'rejected':True,'reason':str(e)})
        else:raise AssertionError(name)
    assert cases==load(OLD/'identity_counterexamples.json');save('fresh_keepbuf_counterexamples8.json',cases)
    for r in cg['primitives'].values():
        if r['type'] in ga.KEEPBUF_WIDTHS:assert ga.strict_keepbuf(r)
    model=Path('C:/pango/PDS_2022.2-SP6.4/arch/lib/bms/verilog/bmsPrim.v');raw=model.read_bytes()
    start=raw.index(b'module bmsKEEPBUF ');end=raw.index(b'endmodule',start)+9;snippet=raw[start:end]
    assert snippet==(OLD/'official_bmsKEEPBUF_model.v').read_bytes()
    assert re.search(rb'parameter WIDTH = 2;',snippet) and b'assign Z = I;' in snippet
    assert not re.search(rb'\b(always|reg|initial|posedge|negedge)\b',snippet)
    (HERE/'official_KEEPBUF_exact.v').write_bytes(snippet)
    base=(B04/'inputs/source/constraints/clock.fdc').read_bytes();clocks=set();asyncs=set()
    for l in base.decode('ascii').splitlines():
        if l.lstrip().startswith(('create_clock ','create_generated_clock ')):clocks.add(re.search(r'-name\s+\{([^}]+)\}',l)[1])
        if l.lstrip().startswith('set_clock_groups '):
            assert '-asynchronous' in l;asyncs.update(re.findall(r'-group\s+\[get_clocks\s+\{?(\w+)\}?\]',l))
    universe={(a,b) for a,b in itertools.product(clocks,repeat=2) if a!=b and (a in asyncs or b in asyncs)}
    carve={(f'cmos{i+1}_pclk','ddrphy_sysclk') for i in range(4)}
    assert universe=={tuple(x) for x in proof['U']} and len(universe-carve)==364
    def coll(xs):return '[get_pins {'+' '.join('{'+x+'}' for x in sorted(xs))+'}]'
    # Match Tcl escaping from frozen collection renderer, with independent set inputs.
    dc=imported('review02_derive',fresh/'derive_new_constraints.py');coll=dc.coll
    commands=[f'set_false_path -from [get_clocks {{{a}}}] -to [get_clocks {{{b}}}]' for a,b in sorted(universe-carve)]
    counts=[];terminals=[];ackfresh=ga.classify(g)['ack_first']
    for cam in range(4):
        cp=ga.Resolver(cg).clock_leaves(cam);sp=ga.Resolver(g).clock_leaves(cam);stored=proof['cameras'][cam]
        assert cp==stored['compile'] and sp==stored['synthesis']
        prefix=f'source_diagnostics/cameras[{cam}].source/'
        mb={c+'/'+p for c,r in cg['primitives'].items() if c.startswith(prefix+'mailbox[') for p,v in r['ports'].items() if v['clock']}
        hd={c+'/'+p for c,r in cg['primitives'].items() if c.startswith(prefix+'host_bank[') for p,v in r['ports'].items() if p.startswith('D[') and v['direction']=='INPUT'}
        pp={(r['mapping']['launch_CLK'],r['mapping']['capture_D']) for r in m['resolved'] if r['camera']==cam and r['mapping']['kind']=='register'}
        launch={q for q,d in pp};capture={d for q,d in pp};comp=(set(cp['leaves'])-mb)|(set(sp['leaves'])-launch)
        assert sorted(mb)==stored['compile_mailbox'] and sorted(hd)==stored['compile_host'] and sorted(comp)==stored['complement']
        assert sorted(pp)==[tuple(x) for x in stored['physical_pairs']] and not comp&(mb|launch)
        assert len(pp)==320 and len(mb)==17 and len(hd)==512
        ack=ackfresh[cam];assert ack==stored['ack_first']
        commands.extend(['set_false_path -from '+coll(comp)+' -to [get_clocks {ddrphy_sysclk}]','set_max_delay -datapath_only 15.238 -from '+coll(mb|launch)+' -to '+coll(hd|capture),'set_false_path -hold -from '+coll(mb|launch)+' -to '+coll(hd|capture),'set_false_path -from '+coll({ack['launch_CLK']})+' -to '+coll({ack['capture_D']})])
        for edge in cp['transparent']:
            if edge.get('disposition')=='identity_terminal_no_output_net_no_storage':
                cell=edge['cell'];out=cell+'/Z[0]';assert out not in cg['pin_net'] and all(out not in ps for ps in cg['netpins'].values());terminals.append(edge)
        counts.append({'camera':cam,'compile_leaves':len(cp['leaves']),'synthesis_leaves':len(sp['leaves']),'complement':len(comp),'physical':len(pp)})
    prefix=b'\n'.join(l for l in base.splitlines() if not l.lstrip().startswith(b'set_clock_groups '))+b'\n'
    draft=(OLD/'diagnostic_constraint_DRAFT/clock.fdc').read_bytes();assert draft.startswith(prefix)
    actual=[l for l in draft[len(prefix):].decode('ascii').splitlines() if l and not l.startswith('#')]
    assert actual==commands and len(commands)==380 and not any(a==b for a,b in universe-carve)
    clean=[l.strip() for l in base.decode('ascii').splitlines()]
    free=next(l for l in clean if l.startswith('create_clock -name {free_clk}'))
    ddr=next(l for l in clean if l.startswith('create_generated_clock -name {ddrphy_sysclk}'))
    period=float(re.search(r'-period \{([^}]+)\}',free)[1]);mult=int(re.search(r'-multiply_by \{(\d+)\}',ddr)[1]);div=int(re.search(r'-divide_by \{(\d+)\}',ddr)[1]);assert 1000/period*mult/div==131.25
    preserved=[l for l in base.splitlines() if l.lstrip().startswith((b'create_clock ',b'create_generated_clock ',b'set_clock_uncertainty ',b'set_multicycle_path '))]
    assert all(l in draft.splitlines() for l in preserved)
    save('fresh_clock_exact_audit.json',{'U':368,'B':4,'retained':364,'exact_commands':380,'budget_ns':15.238,'DDR_MHz':131.25,'preserved_byte_lines':len(preserved),'cameras':counts,'KEEPBUF_no_storage_terminals':terminals,'new_same_domain_falsepaths':[],'model_sha256':sha(model),'model_snippet_sha256':sha(HERE/'official_KEEPBUF_exact.v'),'draft_sha256':sha(OLD/'diagnostic_constraint_DRAFT/clock.fdc')})
    assert (fresh/'derive_new_constraints.py').read_bytes()==(BOARD/'build04_route_prepare01/offline_fresh_synthesis/analysis/derive_new_constraints.py').read_bytes()
    cmd=[sys.executable,'-B',str(fresh/'derive_new_constraints.py'),'--compile-graph',str(B04/'evidence/runtime/compile/analysis/graph.json'),'--synthesis-graph',str(fresh/'graph.json'),'--mapping-manifest',str(fresh/'manifest.json'),'--frozen-clock',str(B04/'inputs/source/constraints/clock.fdc'),'--output',str(HERE/'frozen_gate_attempt')]
    gate=subprocess.run(cmd,cwd=fresh,capture_output=True);(HERE/'frozen1320_gate_reject.log').write_bytes(gate.stdout+gate.stderr)
    assert gate.returncode!=0 and b'legacy 320/camera' in gate.stdout+gate.stderr
    for n,h in seals.items():assert sha(OLD/n)==h,n
    save('recompute_result.json',{'status':'PASS_INDEPENDENT_OFFLINE_RECOMPUTATION','artifact58':True,'source741_registered186':True,'fresh2048_exact':True,'raw_all_stages_and_build01':True,'keepbuf8_rejections':True,'fresh_clock_exact':True,'old1320_gate_still_rejects':True,'runtime_STA_passed':False,'mapping60_official_behavior_review':'other agent; not signed here'})
    print('All independent recomputation passed; old1320 gate still rejects; no PDS/board',flush=True)
if __name__=='__main__':main()
