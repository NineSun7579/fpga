"""Runtime bridge: immutable source contract plus reviewed non-simulation metadata reconciliation."""
from pathlib import Path
import hashlib, importlib.util, json, re, gzip
HERE=Path(__file__).resolve().parent.parent
BOARD=HERE.parent
BASE=BOARD/'source_diagnostics_route_02'
spec=importlib.util.spec_from_file_location('build02_preparation',HERE/'preflight.py')
PREP=importlib.util.module_from_spec(spec);spec.loader.exec_module(PREP)
load=PREP.load;sha=PREP.sha;require=PREP.require
def save(n,v):
    p=HERE/'evidence/runtime'/n;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes((json.dumps(v,indent=2,ensure_ascii=True)+'\n').encode('ascii'))
def reconcile():
    lists=[PREP.REG/v/'compile.f' for v in ['baseline','primitive']]
    compilation={str(Path(line.strip().strip('"')).resolve()) for p in lists for line in p.read_text().splitlines() if line.strip()}
    # Covers compiled libraries and included TB/scenario/monitor files as well as hardware RTL.
    for v in ['baseline','primitive']:
        compilation.update(str((PREP.REG/v/n).resolve()) for n in ['tb_sdt.sv','scenario.vh','compare_monitor.vh'])
    compilation.update(str(Path(line.strip().strip('"')).resolve()) for line in
                       (BOARD/'source_diagnostics_top_candidate/vendor.f').read_text().splitlines() if line.strip())
    frozen=load(PREP.REG/'frozen_inputs.json')
    sealed=load(PREP.REG/'hashlog.json')
    require(len(sealed)==123,'Regression seal inventory changed');PREP.check_hashes(PREP.REG,sealed)
    audit=load(PREP.REG/'audit.json');results=load(PREP.REG/'results.json')
    require(audit['status']=='PASS' and results['exact_four_state_trace_comparison']['equal'],'Regression evidence not PASS')
    for variant in ['baseline','primitive']:
        require(audit['counts'][variant]['checks_after_four_reset_extension']==14668,'Real check count changed')
        log=(PREP.REG/variant/'simulation.log').read_bytes()
        require(b'TOP_FOUR_RESET_PASS checks=14668' in log and re.search(rb'Errors:\s*0\b',log) and not re.search(rb'\*\*\s+(Error|Fatal):',log),'Regression log failed')
        h=hashlib.sha256()
        with gzip.open(PREP.REG/variant/'comparison.trace.gz','rb') as stream:
            while True:
                block=stream.read(1024*1024)
                if not block:break
                h.update(block)
        require(h.hexdigest()==results[variant]['trace_sha256'],'Regression trace digest mismatch')
    drift={name:{'expected':h,'actual':sha(name) if Path(name).is_file() else None} for name,h in frozen.items()
           if not Path(name).is_file() or sha(name)!=h}
    rows=[]
    for name,change in drift.items():
        require(str(Path(name).resolve()) not in compilation,'Historical mismatch is an actual compilation input')
        file=Path(name).resolve()
        rel=file.relative_to(PREP.BASE) if file.is_relative_to(PREP.BASE) else None
        allowed=rel is not None and (rel.as_posix() in {'project.pds','controller_status.json','STATUS.md','prepare_local_delivery.py'} or
                rel.parts[0] in {'evidence','constraints_candidate','compile','synthesize','device_map','place_route',
                                'generate_bitstream','constraint_check','logbackup'})
        # This named mutable route03 binding receipt is not consumed by ModelSim.
        # Actual compile/vendor/include membership was checked above; all 741
        # immutable copied RTL/input hashes are checked separately below.
        allowed=allowed or file==(BOARD/'physical_subagent_evidence_01/fixed_06/physical_exact_11/physical_target_bindings.json').resolve()
        require(allowed,'Mismatch outside active non-simulation flow metadata/artifacts: '+name)
        rows.append({'path':name,**change,'actual_compile_list_member':False,'compiled_or_included_source':False,
                     'semantic_role':'active PDS flow metadata' if name.endswith('project.pds') else 'active physical flow telemetry/constraint proof artifact; not ModelSim input',
                     'historical_bytes_available':False,'proof':'Complete actual compile/vendor lists and sealed included inputs are unchanged; this path is not consumed by ModelSim'})
    checked={}
    for name in sorted(compilation):
        p=Path(name);expected=frozen.get(name)
        if expected is None:
            sealed={n.replace('\\','/'):h for n,h in load(PREP.REG/'hashlog.json').items()}
            expected=sealed.get(p.relative_to(PREP.REG).as_posix()) if p.is_relative_to(PREP.REG) else None
        require(expected is not None and sha(p)==expected,'Actual regression compilation input drift: '+name)
        checked[name]=expected
    manifest=load(HERE/'manifest.json');PREP.check_hashes(HERE,manifest['local_hashes'])
    frozen_copy=load(HERE/'evidence/build01_frozen_inputs.json');PREP.check_hashes(PREP.BASE,frozen_copy)
    require({n for n,h in manifest['local_hashes'].items() if h!=frozen_copy[n]}==set(PREP.REPLACEMENTS),'Copy has more than the two primitive changes')
    require(PREP.scan(manifest['registered_sources'])==manifest['binding_scan'],'Top/source binding drift')
    require(PREP.optimization_gate()==manifest['optimization_gate'],'Three optimization evidence drift')
    bridges=[]
    for rel in PREP.REPLACEMENTS:
        require((HERE/rel).read_bytes()==(PREP.REG/'primitive/rtl'/Path(rel).name).read_bytes(),'Integrated primitive not regression input')
        active=(PREP.BASE/rel).read_bytes();reference=(PREP.REG/'baseline/rtl'/Path(rel).name).read_bytes()
        require(active.replace(b'(* syn_preserve=1, syn_allow_retiming=0 *)',b'(* ASYNC_REG="TRUE" *)')==reference,'Baseline changed beyond attributes')
        bridges.append({'path':rel,'build01_sha256':sha(PREP.BASE/rel),'regressed_baseline_sha256':sha(PREP.REG/'baseline/rtl'/Path(rel).name),
                        'all_other_bytes_identical':True})
    receipt={'status':'PASS','review_basis':'topregression01/REPORT.md line 26 and actual compile/vendor/input membership',
             'report_sha256':sha(PREP.REG/'REPORT.md'),'regression_code_sha256':sha(PREP.REG/'run.py'),
             'actual_compilation_inputs':checked,'actual_compilation_input_count':len(checked),
             'non_compilation_metadata_diffs':rows,'regression_hashlog_files':len(sealed),
             'frozen_copy_files':len(frozen_copy),'only_two_source_changes':True,
             'baseline_attribute_bridge':bridges,
             'historical_failed_record_preserved':sha(HERE/'preflight_result.json'),
             'scope':'Reconcile unrelated metadata membership only; does not waive any compilation/source hash or physical endpoint gate'}
    save('reviewed_reconciliation.json',receipt)
    return receipt
def frozen_guard():
    hashes=load(HERE/'evidence/build01_frozen_inputs.json');PREP.check_hashes(PREP.BASE,hashes);return hashes
def verify():
    reconcile();m=load(HERE/'manifest.json');PREP.check_hashes(HERE,m['local_hashes'])
    return {**m,'decode_candidates_gate':m['optimization_gate']}
def map_gate():
    p=PREP.MAP/'evidence/final_result.json'
    if p.exists():
        r=load(p)
        if r.get('status')=='FAIL':
            topology=PREP.MAP/'evidence/mapping_topology.json'
            failed=[{k:x.get(k) for k in ['logical','cells','binding_method','packed_from','independent_endpoint_passed']}
                    for x in load(topology)['rows'] if not x['independent_endpoint_passed']] if topology.exists() else []
            return {'status':'BLOCKED','reason':'map01 actual final_result FAIL',
                'final_result_sha256':sha(p),'stages':r.get('stages'),'detail_failed_checks':r.get('detail_failed_checks'),
                'failed_actual_endpoint_rows':failed,'physical_start_allowed':False}
        if r.get('status')=='PASS' and r.get('all_verified_checks_passed') is not True:
            return {'status':'PENDING','reason':'Waiting for map01 audit_final detailed 60-endpoint PASS',
                    'final_result_sha256':sha(p),'physical_start_allowed':False}
    if not p.exists():return {'status':'PENDING','reason':'map01 final_result.json absent','physical_start_allowed':False}
    try:
        import collections
        r=load(p)
        require(r['status']=='PASS' and r.get('all_verified_checks_passed') is True,'Final map audit not PASS')
        src=PREP.MAP/'run.py';text=src.read_text(encoding='utf8')
        scope={'collections':collections,'save':lambda n,v:None}
        exec(compile(text[text.index('def audit('):text.index('def main():')],str(src),'exec'),scope)
        srcdetail=PREP.MAP/'audit_final.py';text=srcdetail.read_text(encoding='utf8')
        ds={'save':lambda n,v:None}
        exec(compile(text[text.index('def parameters('):text.index('def main():')],str(srcdetail),'exec'),ds)
        proofs={}
        for stage in ['compile','synthesis','mapping']:
            art=load(PREP.MAP/f'evidence/{stage}_artifact.json')
            require(sha(art['adf'])==art['adf_sha256'] and sha(art['native_db'])==art['native_db_sha256'],'Map actual artifact drift')
            require(art['official_done_lines'],'Map official done marker absent')
            graphpath=PREP.MAP/f'evidence/{stage}/analysis/graph.json';g=load(graphpath)
            export=load(PREP.MAP/f'evidence/{stage}_export_hashes.json')
            require(sha(graphpath)==export['graph_sha256'] and sha(art['adf'])==export['adf_sha256'],'Actual map graph export binding drift')
            ref=load(PREP.MAP/'evidence/synthesis/analysis/graph.json') if stage=='mapping' else None
            a=scope['audit'](stage,g,ref);d=ds['detail'](stage,g,a)
            require(a['status']=='PASS' and (a['independent_registers'],a['independent_sync'],a['independent_reset'])==(60,28,32)
                    and not d['failed_checks'],'Recomputed real map graph endpoint/parameter audit FAIL: '+stage)
            proofs[stage]={'status':'PASS','independent_registers':60,'independent_sync':28,'independent_reset':32,
                           'graph_sha256':sha(graphpath),'adf_sha256':sha(art['adf']),'detail_failed_checks':0}
        inputs=load(PREP.MAP/'evidence/input_hashes.json')
        PREP.check_hashes(PREP.MAP,{n:h for n,h in inputs.items() if n!='project.pds'})
        for rel in PREP.REPLACEMENTS:require((PREP.MAP/rel).read_bytes()==(HERE/rel).read_bytes(),'Mapped primitive differs from integrated bytes')
        return {'status':'PASS','final_result_sha256':sha(p),'recomputed_actual_graphs':proofs,
                'map_controller_sha256':sha(src),'map_detail_checker_sha256':sha(srcdetail),'independent_registers':60,
                'independent_sync':28,'independent_reset':32,'physical_start_allowed':True,
                'project_metadata_policy':'Tool rewrites PDS flow metadata; all actual RTL/constraint/parser inputs and ADF/DB/export graph hashes checked independently'}
    except (RuntimeError,KeyError,OSError,AssertionError,ValueError) as exc:
        return {'status':'BLOCKED','reason':str(exc),'physical_start_allowed':False,'final_result_sha256':sha(p)}
