"""只读复核工具实际继承的时钟/例外及双角预算；运行失败也完整归档。"""
from pathlib import Path
import json,xml.etree.ElementTree as ET
import generate_exact11 as gen
OUT=gen.OUT
def flatten(rows):
    for row in rows:
        yield row
        yield from flatten(row.get('children',[]))
def extract(path):
    result={}
    if not path.exists():return result
    for event,elem in ET.iterparse(path,events=['end']):
        if elem.tag=='table':
            ident=elem.attrib.get('id','')
            if any(k in ident for k in ['clock_summary','clock_interaction','exception_report_set_max_delay','exception_report_set_false_path']):
                def row(e):return {'data':[d.text or '' for d in e.findall('data')],'children':[row(x) for x in e.findall('row')]}
                result[ident]={'headers':[x.text or '' for x in elem.findall('column_headers/data')],'rows':[row(x) for x in elem.findall('row')]}
            elem.clear()
    return result
def main():
    offline=json.loads((OUT/'coverageproof_offline.json').read_bytes())
    baseline_path=gen.cf.BASE.parent/'whole_candidate_v7_route_01/evidence/stage_tables.json'
    baseline=json.loads(baseline_path.read_bytes())['synthesize']
    clock_table=baseline['synthesize_report_timing_clock_summary']
    frozen_clocks={r['data'][0] for r in flatten(clock_table['rows'])}
    assert frozen_clocks==set(offline['clocks']),'冻结 V7 实际时钟集合与 FDC 不一致'
    old_interactions=baseline['synthesize_report_clock_interaction']['rows']
    old_async={tuple(r['data'][:2]) for r in old_interactions if r['data'][3]=='Asynchronous Groups'}
    carved={tuple(p) for p in offline['carved_camera_to_ddr']}
    required=old_async-carved
    assert required<=set(tuple(p) for p in offline['retained_clock_pairs'])
    actual=extract(gen.NEW/'synthesize/snr.db')
    gen.write_json(OUT/'actual_imported_exception_tables.json',actual)
    interactions={tuple(r['data'][:2]):r['data'] for t,v in actual.items() if 'clock_interaction' in t for r in v['rows']}
    tool_clocks={r['data'][0] for t,v in actual.items() if 'clock_summary' in t for r in flatten(v['rows'])}
    missing=sorted(required-set(interactions))
    lost=[{'pair':pair,'row':interactions[pair]} for pair in sorted(required&set(interactions)) if 'False Path' not in interactions[pair][3]]
    same_domain=[v for (a,b),v in interactions.items() if a==b and 'False Path' in v[3]]
    evidence={'frozen_actual_clock_table':str(baseline_path),'frozen_clocks':sorted(frozen_clocks),
              'actual_clocks':sorted(tool_clocks),'actual_clock_set_complete':tool_clocks==frozen_clocks,
              'old_connected_async_pairs':sorted(old_async),'retained_connected_pairs':sorted(required),
              'missing':missing,'lost_false_exceptions':lost,'same_domain_false_exceptions':same_domain,
              'clockpair_inheritance_passed':bool(interactions) and not missing and not lost and not same_domain and tool_clocks==frozen_clocks,
              'all_368_declared_pairs_accounted_offline':offline['all_old_pairs_accounted']}
    target=OUT/'evidence/mailbox_routed_audit.json'
    if target.exists():
        budget=json.loads(target.read_bytes());evidence['mailbox_double_corner']=budget
        evidence['mailbox_1320_both_corners_passed']=budget.get('passed') is True and budget.get('physical_targets') is True and all(v['covered']==1320 and not v['missing'] and not v['unexpected'] and not v.get('bad_budget',[]) and v['worst_slack'] is not None and v['worst_slack']>=0 for v in budget['details'].values()) and len(budget['details'])==2
    else:evidence['mailbox_1320_both_corners_passed']=False
    gates=OUT/'acceptance_gates.json'
    evidence['acceptance_gates']=json.loads(gates.read_bytes()) if gates.exists() else None
    import verify_routed11
    evidence['routed_physical_binding_passed']=verify_routed11.main()
    import physical_targets11
    physical_targets11.prepare()
    protection=json.loads((gen.cf.BASE/'source_diagnostics_route_01/build01_guard.json').read_bytes())
    evidence['protected_count']=len(protection)
    evidence['protected_mismatches']=[p for p,h in protection.items() if gen.cf.sha(Path(p))!=h]
    evidence['compile_syn_routed_coverage']=all((OUT/('coverageproof_'+stage+'.json')).exists() and json.loads((OUT/('coverageproof_'+stage+'.json')).read_bytes())['passed'] for stage in ['compile','synthesis','routed'])
    evidence['remote_or_program']=False
    import prove_cdb11
    cdb_proofs=prove_cdb11.main()
    evidence['actual_cdb_stage_proofs']=[{'stage':r['stage'],'passed':r['passed'],'clockpair_count':r['clockpair_count'],'errors':r['errors']} for r in cdb_proofs]
    evidence['all_364_clockpairs_actual_cdb_passed']=len(cdb_proofs)==2 and all(r['passed'] for r in cdb_proofs)
    gen.write_json(OUT/'runtime_clockpair_and_budget_proof.json',evidence)
    gen.write_json(OUT/'review_result.json',{'pnr_done':(OUT/'pnr_artifact.json').exists(),
        'clockpair_inheritance_passed':evidence['clockpair_inheritance_passed'],
        'mailbox_1320_both_corners_passed':evidence['mailbox_1320_both_corners_passed'],
        'compile_syn_routed_coverage':evidence['compile_syn_routed_coverage'],
        'acceptance_gates':evidence['acceptance_gates'],'protected_count':len(protection),
        'protected_mismatches':evidence['protected_mismatches'],'remote_or_program':False})
    print('实际例外继承核验：',evidence['clockpair_inheritance_passed'],'；1320 双角预算：',evidence['mailbox_1320_both_corners_passed'],flush=True)
if __name__=='__main__':main()
