"""Local byte-copy/evidence audit only. Never launches an FPGA or simulation tool."""
from pathlib import Path
import argparse, collections, difflib, gzip, hashlib, json, re

HERE = Path(__file__).resolve().parent
BOARD = HERE.parent
BASE = BOARD / 'source_diagnostics_timing_build_01'
CAND = BOARD / 'diagnostic_sync_register_timing_candidate/rtl_primitive'
REG = BOARD / 'diagnostic_sync_top_regression01'
MAP = BOARD / 'diagnostic_sync_register_map_01'
REPLACEMENTS = ['rtl/v7_sfd_candidate.v', 'rtl/v7_sdt_bus.v']

def require(ok, message):
    if not ok: raise RuntimeError(message)

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_bytes())
def save(p, value):
    p = HERE / p
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes((json.dumps(value, indent=2, ensure_ascii=True)+'\n').encode('ascii'))
def clean(raw): return re.sub(rb'//[^\r\n]*|/\*.*?\*/', b'', raw, flags=re.S)
def inventory(root):
    return {p.relative_to(root).as_posix(): sha(p) for folder in ['rtl', 'inputs']
            for p in (root/folder).rglob('*') if p.is_file()}
def check_hashes(root, hashes):
    for n,h in hashes.items(): require(sha(root/n)==h, 'Hash drift: '+str(root/n))

def regression():
    hashes=load(REG/'hashlog.json')
    require(len(hashes)==123, 'Unexpected final regression hash inventory')
    check_hashes(REG, hashes)
    frozen=load(REG/'frozen_inputs.json')
    drift={n:{'expected':h,'actual':sha(n) if Path(n).is_file() else None}
           for n,h in frozen.items() if not Path(n).is_file() or sha(n)!=h}
    # Active PDS can be rewritten by the running tool. Record, never waive the inputproof gate.
    active_records={str(BASE/n) for n in ['project.pds','controller_status.json','evidence/queue_snapshot.json']}
    require(set(drift)<=active_records,'Regression frozen RTL/evidence drift: '+repr(drift))
    a=load(REG/'audit.json'); r=load(REG/'results.json')
    require(a['status']=='PASS' and a['registered_primitive_instance_count']==60,
            'Real regression audit not PASS')
    require(r['exact_four_state_trace_comparison']['equal'] is True, 'Trace comparison failed')
    for variant in ['baseline','primitive']:
        require(a['counts'][variant]['checks_after_four_reset_extension']==14668, 'Checks missing')
        log=(REG/variant/'simulation.log').read_bytes()
        require(b'TOP_FOUR_RESET_PASS checks=14668' in log and b'SDT_ALL_PASS checks=14540' in log,
                'Actual regression markers absent')
        require(re.search(rb'Errors:\s*0\b',log) and not re.search(rb'\*\*\s+(Error|Fatal):',log),
                'Actual regression log failed')
        h=hashlib.sha256()
        with gzip.open(REG/variant/'comparison.trace.gz','rb') as stream:
            while True:
                block=stream.read(1024*1024)
                if not block: break
                h.update(block)
        require(h.hexdigest()==r[variant]['trace_sha256'], 'Trace hash mismatch')
    binding=load(REG/'actual_parent_bindings.json')
    require(binding['CE_count']==28 and binding['PE_count']==32 and
            len(set(binding['primitive_instances']))==60, 'Actual top primitive count mismatch')
    bridges=[]
    for rel in REPLACEMENTS:
        require((CAND/Path(rel).name).read_bytes()==(REG/'primitive/rtl'/Path(rel).name).read_bytes(),
                'Candidate not regression input')
        active=(BASE/rel).read_bytes(); reference=(REG/'baseline/rtl'/Path(rel).name).read_bytes()
        normalized=active.replace(b'(* syn_preserve=1, syn_allow_retiming=0 *)',b'(* ASYNC_REG="TRUE" *)')
        require(normalized==reference,'Build01 differs beyond verified attribute-only baseline bridge')
        bridges.append({'path':rel,'build01_sha256':sha(BASE/rel),
                        'regressed_baseline_sha256':sha(REG/'baseline/rtl'/Path(rel).name),
                        'attribute_only_replacements':active.count(b'(* syn_preserve=1, syn_allow_retiming=0 *)'),
                        'all_other_bytes_identical':True})
    # Re-read real compile lists: only these two files were redirected.
    origin=BOARD/'source_diagnostics_top_candidate'
    old=[Path(x.strip().strip('"')) for x in (origin/'compile.f').read_text().splitlines() if x.strip()]
    new=[Path(x.strip().strip('"')) for x in (REG/'primitive/compile.f').read_text().splitlines() if x.strip()]
    require(len(old)==len(new), 'Regression input list cardinality changed')
    for x,y in zip(old,new):
        require(y==(REG/'primitive/rtl'/x.name if x.name in {Path(n).name for n in REPLACEMENTS} else x),
                'Regression input redirect changed')
    return {'status':'PASS' if not drift else 'INPUTPROOF_DRIFT','hashlog_status':'PASS',
            'frozen_input_mismatches':drift,'frozen_inputs_unchanged':len(frozen)-len(drift),
            'hashlog_files':len(hashes),'frozen_inputs':len(frozen),
            'extended_checks':14668,'trace_equal':True,'actual_CE':28,'actual_PE':32,
            'hashlog_sha256':sha(REG/'hashlog.json'),'inputproof_sha256':sha(REG/'frozen_inputs.json'),
            'compile_list_sha256':sha(REG/'primitive/compile.f'), 'repeated_simulation':False,
            'baseline_attribute_bridge':bridges}

def optimization_gate():
    m=load(BASE/'manifest.json')
    require(m['decode_candidates_gate']['status']=='PASS' and m['lease_gate']['status']=='PASS',
            'Three optimizations not integrated/audited')
    for receipt in [m['decode_candidates_gate'],m['lease_gate']]:
        check_hashes(Path('.'),receipt['hashes'])
    paths=['inputs/source/ov5640/ov5640_reg.v','rtl/fpga_v8_capture_control_axil_arm_v2.v',
           'rtl/fpga_v8_capture_lease_prefix.v','rtl/v7_sdt_top.v']
    for p in paths: require(sha(BASE/p)==m['local_hashes'][p], 'Optimized source drift: '+p)
    return {'status':'PASS','hashes':{p:sha(BASE/p) for p in paths},
            'manifest_sha256':sha(BASE/'manifest.json'), 'receipt':'build01 existing evidence rehashed; no simulation repeated'}

def scan(registered):
    modules=collections.defaultdict(list)
    for p in registered:
        if Path(p).suffix.lower() not in {'.v','.vp','.sv'}: continue
        for mod in re.findall(rb'\bmodule\s+(\w+)',clean((HERE/p).read_bytes())):
            modules[mod.decode('ascii')].append(p)
    duplicate={k:v for k,v in modules.items() if len(v)>1}
    require(not duplicate,'Duplicate registered module: '+repr(duplicate))
    require(modules['v7_sdt_top']==['rtl/v7_sdt_top.v'] and
            modules['v7_sdt_bus']==['rtl/v7_sdt_bus.v'] and
            modules['v7_sfd_candidate']==['rtl/v7_sfd_candidate.v'],'Actual module registration ambiguous')
    top=clean((HERE/'rtl/v7_sdt_top.v').read_bytes())
    bus=clean((HERE/'rtl/v7_sdt_bus.v').read_bytes())
    src=clean((HERE/'rtl/v7_sfd_candidate.v').read_bytes())
    require(len(re.findall(rb'\bv7_sdt_bus\s+source_diagnostics\s*\(',top))==1,'Actual top bus binding ambiguous')
    require(re.search(rb'for\s*\(g=0;g<4;g=g\+1\)\s*begin:\s*cameras',bus), 'Four-camera generate changed')
    require(len(re.findall(rb'\bv7_sfd_candidate\s+source\s*\(',bus))==1,'Source binding ambiguous')
    counts={}
    names=[]
    for kind in ['CE','PE']:
        pattern=rb'\bGTP_DFF_'+kind.encode()+rb'\s*#\s*\(.*?\)\s+(\w+)\s*\('
        sn=re.findall(pattern,src,flags=re.S); bn=re.findall(pattern,bus,flags=re.S)
        require(len(set(sn+bn))==len(sn+bn),'Primitive instances duplicate')
        counts[kind]=4*(len(sn)+len(bn))
        names += [f'source_diagnostics/cameras[{i}].'+('source/' if n in sn else '')+n.decode()
                  for i in range(4) for n in sn+bn]
    require(counts=={'CE':28,'PE':32} and len(set(names))==60,'Primitive binding count failed')
    return {'top':'v7_sdt_top','bus_instance':'source_diagnostics','camera_count':4,
            'unique_registered_modules':len(modules),'duplicates':duplicate,'primitive_counts':counts,
            'primitive_instances':sorted(names),'basis':'registered RTL syntax/byte scan, not new elaboration or mapped endpoint proof'}

def map_gate():
    result=MAP/'evidence/final_result.json'
    if not result.exists(): return {'status':'PENDING','reason':'map01 final_result.json absent','physical_start_allowed':False}
    try:
        r=load(result)
        require(r['status']=='PASS' and r.get('all_verified_checks_passed') is True,'Final detailed map audit not PASS')
        for stage in ['compile','synthesis','mapping']:
            s=r['stages'][stage]
            require(s['status']=='PASS' and (s['independent_registers'],s['independent_sync'],s['independent_reset'])==(60,28,32),
                    'Actual 60 independent endpoints missing: '+stage)
            art=load(MAP/f'evidence/{stage}_artifact.json')
            require(sha(art['adf'])==art['adf_sha256'] and sha(art['native_db'])==art['native_db_sha256'], 'Map artifact drift')
            require(art['official_done_lines'], 'Official stage completion missing')
            topology=load(MAP/f'evidence/{stage}_topology.json')
            rows=topology['rows']
            graph=load(MAP/f'evidence/{stage}/analysis/graph.json')
            require(len(rows)==60 and all(x['independent_endpoint_passed'] for x in rows) and
                    len({x['cells'][0] for x in rows})==60,'Topology independence missing')
            for row in rows:
                cell=row['cells'][0]
                require(cell in graph['primitives'] and
                        not any(x in graph['primitives'][cell]['type'].upper() for x in ['SRL','RAM','DRM']),
                        'Independent row not actual storage cell')
                require(all(p in graph['pin_net'] for p in [row['D']]+row['clock_endpoints']+row['reset_endpoints']),
                        'Actual graph D/clock/reset endpoints missing')
            detail=load(MAP/f'evidence/{stage}_endpoint_details.json')
            require(not detail['failed_checks'] and len(detail['rows'])==60 and
                    all(x['all_proven_checks_passed'] for x in detail['rows']),'Endpoint parameter/connection audit missing')
        check_hashes(MAP,load(MAP/'evidence/input_hashes.json'))
        for rel in REPLACEMENTS:
            require((MAP/rel).read_bytes()==(HERE/rel).read_bytes(),'Map tested a different primitive')
        return {'status':'PASS','final_result_sha256':sha(result),'independent_registers':60,
                'independent_sync':28,'independent_reset':32,'physical_start_allowed':False,
                'reason':'Evidence gate PASS; physical launch still requires main-session separate authorization'}
    except (RuntimeError,KeyError,OSError) as exc:
        return {'status':'BLOCKED','reason':str(exc),'physical_start_allowed':False}

def prepare():
    require(not (HERE/'manifest.json').exists(),'Already prepared; use --verify')
    reg=regression(); optim=optimization_gate()
    frozen=inventory(BASE)
    project=(BASE/'project.pds').read_bytes()
    registered=[x.decode('ascii') for x in re.findall(rb'\(_file "([^"]+)"',project)]
    require(len(registered)==len(set(registered)), 'Duplicate file registration')
    sources=[p for p in registered if p.startswith(('rtl/','inputs/'))]
    require(all(p in frozen for p in sources),'Registered source outside frozen inventory')
    save('evidence/build01_frozen_inputs.json',frozen)
    for n,h in frozen.items():
        out=HERE/n; require(not out.exists(),'Refuse overwrite '+n)
        out.parent.mkdir(parents=True,exist_ok=True); out.write_bytes((BASE/n).read_bytes())
        require(sha(out)==h,'Copy mismatch '+n)
    changes=[]
    for rel in REPLACEMENTS:
        old=(HERE/rel).read_bytes(); new=(CAND/Path(rel).name).read_bytes()
        (HERE/rel).write_bytes(new)
        diff=''.join(difflib.unified_diff(old.decode('latin1').splitlines(True),new.decode('latin1').splitlines(True),
                     fromfile='build01/'+rel,tofile='build02/'+rel))
        (HERE/(Path(rel).name+'.diff')).write_bytes(diff.encode('latin1'))
        changes.append({'path':rel,'before':hashlib.sha256(old).hexdigest(),'after':sha(HERE/rel),'candidate':str(CAND/Path(rel).name)})
    # Do not copy any old generated clock constraints or executable project/controller.
    require(b'constraints_candidate/' in project,'Unknown constraint registration prefix')
    template=project.replace(b'constraints_candidate/',b'constraints_pending/')
    template=re.sub(rb'\(_gci_state \(_integer \d+\)\)',b'(_gci_state (_integer 0))',template)
    (HERE/'project_template.pds').write_bytes(template)
    tools=HERE/'analysis_tools';tools.mkdir(exist_ok=True)
    template_sources={}
    for p in list((BASE/'analysis_tools').glob('*'))+[BASE/n for n in ['physical_flow.py','targeted_reports.py','routed_acceptance.py']]:
        if not p.is_file(): continue
        target=HERE/'review_templates'/p.relative_to(BASE)
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.read_bytes())
        template_sources[p.relative_to(BASE).as_posix()]=sha(p)
    check_hashes(BASE,frozen)
    require(inventory(BASE)==frozen,'Build01 input inventory changed while freezing')
    m={'schema':1,'status':'PREPARED_NOT_MAPPED','mode':'LOCAL_COPY_PYCOMPILE_PREFLIGHT_ONLY',
       'baseline':str(BASE),'frozen_inputs_sha256':sha(HERE/'evidence/build01_frozen_inputs.json'),
       'build01_project_sha256':hashlib.sha256(project).hexdigest(),'registered_sources':sources,
       'constraint_registrations_pending':[p.replace('constraints_candidate/','constraints_pending/') for p in registered if p not in sources],
       'local_hashes':inventory(HERE),'changes':changes,'optimization_gate':optim,'regression_gate':reg,
       'binding_scan':scan(sources),'review_template_hashes':template_sources,'template_sha256':sha(HERE/'project_template.pds'),
       'pds_started':False,'mapped':False,'bit_generated':False,'device_operations':False,
       'physical_start_authorized':False,'constraints_qualified':False}
    save('manifest.json',m)
    save('source_binding_diff.json',{'registration_changes':[], 'actual_top_byte_identical':sha(HERE/'rtl/v7_sdt_top.v')==frozen['rtl/v7_sdt_top.v'],
         'changed_sources':changes,'all_other_rtl_inputs_byte_identical':True,'primitive_binding':m['binding_scan']})
    verify()

def verify():
    m=load(HERE/'manifest.json');frozen=load(HERE/'evidence/build01_frozen_inputs.json')
    check_hashes(BASE,frozen); check_hashes(HERE,m['local_hashes'])
    require(sha(HERE/'project_template.pds')==m['template_sha256'],'Template drift')
    require(sha(HERE/'evidence/build01_frozen_inputs.json')==m['frozen_inputs_sha256'],'Frozen inventory drift')
    require({n for n,h in m['local_hashes'].items() if h!=frozen[n]}==set(REPLACEMENTS),'Unexpected source change')
    require(scan(m['registered_sources'])==m['binding_scan'],'Source binding drift')
    reg=regression()
    # Evidence hashes remain strict; active project drift is re-reported on every read.
    require({k:v for k,v in reg.items() if k not in {'status','frozen_input_mismatches','frozen_inputs_unchanged'}}==
            {k:v for k,v in m['regression_gate'].items() if k not in {'status','frozen_input_mismatches','frozen_inputs_unchanged'}},'Regression evidence receipt drift')
    require(optimization_gate()==m['optimization_gate'],'Optimization receipt drift')
    for n,h in m['review_template_hashes'].items(): require(sha(HERE/'review_templates'/n)==h,'Review template drift')
    gate=map_gate()
    receipt={'preparation_pass':True,'status':'PREPARED_NOT_MAPPED','baseline_files_checked':len(frozen),
             'registered_sources':len(m['registered_sources']),'binding':m['binding_scan']['primitive_counts'],
             'regression_gate':reg,'map_gate':gate,'physical_start_allowed':False,
             'constraints_qualified':False,'pds_started':False,'bit_generated':False,'device_operations':False}
    receipt['physical_evidence_gate_pass']=reg['status']=='PASS' and gate['status']=='PASS'
    receipt['remaining_gates']=['historical inputproof drift reconciliation' if reg['status']!='PASS' else 'inputproof PASS',
                              'map01 final detailed actual PASS60' if gate['status']!='PASS' else 'map01 PASS',
                              'main-session separate physical authorization','fresh graph constraint qualification',
                              'new actual mapping/routed U-B and all ten STA groups']
    save('preflight_result.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k!='regression_gate'},indent=2))
    return receipt

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--prepare',action='store_true');ap.add_argument('--verify',action='store_true')
    args=ap.parse_args();prepare() if args.prepare else verify()
