"""Actual routed all-corner, IO, mailbox, synchronizer and reset gates before bit."""
import continue_fixed as cf
import sys
from continue_fixed import BASE,HERE,PDS,sha,save,run,idle
OUT=cf.OUT/(sys.argv[1] if len(sys.argv)>1 else 'physical_fixed_native_08')
PROJECT=sys.argv[2] if len(sys.argv)>2 else 'standard_flow_fixed_native.pds'
cf.OUT=OUT
from pathlib import Path
import json,re,shutil,importlib.util,sys,types
def tcl_list(items): return '{'+' '.join('{'+x+'}' for x in sorted(set(items)))+'}'
def main():
    idle()
    route=HERE/'place_route/v7_sdt_top_pnr.adf'
    receipt=json.loads((OUT/'pnr_artifact.json').read_bytes())
    assert sha(route)==receipt['sha256']
    h=sha(route)
    guard=json.loads((BASE/'source_diagnostics_route_01/build01_guard.json').read_bytes())
    before=json.loads((OUT/'input_hashes.json').read_bytes())
    def guards(): return {p:sha(Path(p)) for p in guard}
    def inputs(): return {p:sha(HERE/p) for p in before}
    assert guards()==guard and inputs()==before
    physical=None
    if PROJECT=='standard_flow_exact11.pds':
        (OUT/'evidence').mkdir(exist_ok=True)
        import audit_physical_targets11
        physical=audit_physical_targets11.main(OUT,route)
    export=OUT/'final_export'; export.mkdir(exist_ok=True)
    script=export/'export.tcl'
    script.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n'
        '.switch_db -input {'+route.as_posix()+'} -output {'+(export/'routed_dump.txt').as_posix()+'}\n'
        'report_timing -input_db_file {'+route.as_posix()+'} -force_to_run -delay_type min_max -nworst 1 -max_path '+('512' if PROJECT=='standard_flow_exact11.pds' else '200000')+' -slack_less_than 0 -input_pins TRUE -report_exception TRUE\n',encoding='ascii')
    if not (OUT/'final_export_result.json').exists():
        run('final_export',[str(PDS),'-file',str(script),'-work_dir',str(export),'-project_name','fixed06_routed'],export)
    else:
        previous=json.loads((OUT/'final_export_result.json').read_bytes())
        assert previous['route_sha256_after']==h and previous['exit_code']==0
    save('final_export_result.json',{'exit_code':0,'route_db_unchanged':sha(route)==h,'protected_unchanged':guards()==guard,'route_sha256_after':sha(route)})
    save('protected_before.json',guard);save('inputs_before.json',before)
    origin=BASE.parent/'whole_candidate_v2_route_01'
    spec=importlib.util.spec_from_file_location('summarize_route',origin/'summarize_route.py')
    summary=importlib.util.module_from_spec(spec);sys.modules['summarize_route']=summary;spec.loader.exec_module(summary)
    summary.HERE=OUT;summary.EVIDENCE=OUT/'evidence';summary.EVIDENCE.mkdir(exist_ok=True)
    runner=types.ModuleType('run_route');runner.guards=guards;runner.inputs=inputs;sys.modules['run_route']=runner
    source=(origin/'audit_final.py').read_bytes()
    changes=[(b'fpga_v8_cooperative_top_v2.rtr',b'v7_sdt_top.rtr'),
        (b"HERE.parents[1] / 'motion_100h/run_20261003_212303/phy_audit.json'",b'Path('+repr(str(BASE.parents[1]/'motion_100h/run_20261003_212303/phy_audit.json')).encode('ascii')+b')'),
        (b'max_path 15000',b'max_path 200000')]
    for a,b in changes: assert source.count(a)==1;source=source.replace(a,b)
    save('raw_gate_reuse.json',{'source':str(origin/'audit_final.py'),'source_sha256':sha(origin/'audit_final.py'),'executed_sha256':__import__('hashlib').sha256(source).hexdigest()})
    scope={'__name__':'fixed_raw_audit','__file__':str(origin/'audit_final.py')}
    exec(compile(source,str(origin/'audit_final.py'),'exec'),scope);scope['main']()
    stages={s:summary.extract(HERE/s/db,s) for s,db in [('synthesize','snr.db'),('place_route','prr.db')]}
    save('evidence/stage_tables.json',stages)
    baseline=json.loads((BASE.parent/'whole_candidate_v7_route_01/evidence/stage_tables.json').read_bytes())
    pins=stages['place_route']['pnr_io_report']['rows']; old=baseline['place_route']['pnr_io_report']['rows']
    assert len(pins)==112 and pins==old,'PCB IO changed'
    save('evidence/io_audit.json',{'passed':True,'pins':112,'matches_frozen_v7':True})
    analysis=OUT/'actual/analysis'
    if not analysis.exists():
        analysis.mkdir(parents=True)
        for n in ['graph.json','manifest.json','objects.json','exact_complement.json']:
            shutil.copy2(OUT.parent/'native_probe_07/synthesize_actual/analysis'/n,analysis/n)
    shutil.copy2(BASE/'source_diagnostics_route_01/actual/classify_paths.py',analysis/'classify_paths.py')
    run('classify_paths',['python',str(analysis/'classify_paths.py')],analysis)
    c=json.loads((analysis/'classification.json').read_bytes());g=json.loads((analysis/'graph.json').read_bytes());m=json.loads((analysis/'manifest.json').read_bytes())
    pairs=sorted(set((r['mapping']['launch_CLK'],r['mapping']['capture_D']) for r in m['resolved'] if r['mapping']['kind']=='register'))
    resets=sorted(set(q.rsplit('/',1)[0]+'/'+p for x in c['reset'] for q in x['actual_Q'] for p in g['primitives'][q.rsplit('/',1)[0]]['ports'] if p in ('P','C','R','S')))
    expected_pair_count=1320 if (OUT/'canonical_equivalence_after_remap.json').exists() else 1280
    assert len(pairs)==expected_pair_count and resets
    syncpairs=[(r['launch_CLK'],r['capture_D']) for r in c['ordinary_pairs']]
    queries=[] if PROJECT=='standard_flow_exact11.pds' else [('mailbox',pairs,[],2,10000),('reset',[],resets,10,200000),('sync_later',syncpairs,[],2,200000)]
    target_module=BASE/'source_diagnostics_route_01/audit_targets.py'
    # Only the report parser is reused; its legacy main is not called.
    text=target_module.read_text(); parser=text[text.index('def records'):text.index('def main')]
    ps={'re':re};exec(parser,ps); records=ps['records']
    gates={}
    if PROJECT=='standard_flow_exact11.pds':
        gates.update({key:physical[key] for key in ['mailbox','reset','sync_later']})
        gates['target_filter_zero_ignored']=physical['physical_target_filter'] and physical['singlepair_zero_ignored']
    for name,pp,ends,nworst,maximum in queries:
        out=OUT/('routed_'+name);out.mkdir(); starts=[a for a,b in pp];ends=ends or [b for a,b in pp]
        command='report_timing -input_db_file {'+route.as_posix()+'} -force_to_run -delay_type min_max -nworst '+str(nworst)+' -max_path '+str(maximum)+' -input_pins TRUE -report_exception TRUE'
        if starts: command+=' -from '+tcl_list(starts)
        command+=' -to '+tcl_list(ends)
        script=out/'export.tcl';script.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n'+command+'\n',encoding='ascii')
        run('target_'+name,[str(PDS),'-file',str(script),'-work_dir',str(out),'-project_name','fixed06_'+name],out)
        assert sha(route)==h
        rows=records(out/'report_timing/v7_sdt_top.rtr');detail={}
        for corner in ['Slow','Fast']:
            subset=[x for x in rows if x['corner']==corner]
            if name=='mailbox':subset=[x for x in subset if x['exception'] and 'MaxDelay Path' in x['exception']]
            if pp:
                expected=set(pp);covered={(x['start'],x['end']) for x in subset};slacks=[x['slack'] for x in subset if x['slack'] is not None]
                detail[corner]={'covered':len(expected&covered),'missing':sorted(expected-covered),'unexpected':sorted(covered-expected),'worst_slack':min(slacks,default=None)}
            else:
                for kind in ['Recovery','Removal']:
                    selected=[x for x in subset if x['kind'] and kind.lower() in x['kind'].lower()]
                    covered={x['end'] for x in selected}; slacks=[x['slack'] for x in selected if x['slack'] is not None]
                    detail[corner+'_'+kind]={'missing':sorted(set(ends)-covered),'worst_slack':min(slacks,default=None),'covered':len(set(ends)&covered)}
        gates[name]=all(not v['missing'] and not v.get('unexpected',[]) and v['worst_slack'] is not None and v['worst_slack']>=0 for v in detail.values())
        save('evidence/'+name+'_routed_audit.json',{'passed':gates[name],'details':detail,'records':rows})
    sta=json.loads((OUT/'evidence/final_sta_summary.json').read_bytes())
    ten=sta['all_corner_summaries']
    gates['ten_groups']=len(ten)==10 and all(s['rows'] and s['sum_failing_endpoints']==0 and all(r['worst_slack_ns']>=0 for r in s['rows']) for s in ten)
    hsst=json.loads((OUT/'evidence/hsst_actual_phy_audit.json').read_bytes())
    gates['hsst']=hsst['sites_identical_to_baseline'] and hsst['dedicated_connections_identical_to_baseline']
    gates['io']=True;gates['protected']=guards()==guard and inputs()==before
    save('acceptance_gates.json',gates)
    assert all(gates.values()),'Routed acceptance gates open; do not generate bit'
    if PROJECT == 'standard_flow_exact11.pds':
        coverage = OUT/'coverageproof_routed.json'
        assert coverage.exists(), 'Routed object coverage proof required before bit generation'
        proof = json.loads(coverage.read_bytes())
        assert proof.get('passed') is True, 'Routed object coverage proof has not passed'
        assert proof.get('reset_semantic_binding_passed') is True and proof.get('sync_binding_passed') is True
        import prove_cdb11
        proofs=prove_cdb11.main()
        assert len(proofs)==2 and all(p['passed'] for p in proofs),'实际364 clockpair/CDB继承未通过'
    run('gen_bit_stream',[str(PDS),'-project',str(HERE/PROJECT),'-run','gen_bit_stream','-work_dir',str(HERE)],HERE)
    bits=[p for p in HERE.rglob('*.bit') if p.stat().st_size]
    assert bits,'No actual bit produced'
    save('bit_artifacts.json',{str(p):sha(p) for p in bits})
    print('LOCAL BIT COMPLETE, no remote/program actions',flush=True)
if __name__=='__main__':main()
