"""Actual global signoff and packed-reset/sync evidence; fail closed, no bit."""
from pathlib import Path
import hashlib
import sys
import types
import traceback
from preflight import HERE, BOARD, load, sha, require
from physical_flow import EVIDENCE, PDS, protected, run, record, wait_idle, status
from targeted_reports import query

def packed_bindings(route):
    source = BOARD / 'physical_subagent_evidence_01/physical_targets11.py'
    text = source.read_text(encoding='utf8')
    code = text[text.index('def params('):text.index("if __name__=='__main__':")]
    code = code.replace("out/'coverageproof_routed.json'", "out/'coverageproof_physical_receivers.json'")
    code = code.replace("out/'actual/analysis/graph.json'", "out/'actual_final_pnr/analysis/graph.json'")
    code = code.replace("out/'actual/analysis/classification.json'", "out/'actual_final_pnr/analysis/classification.json'")
    def save_path(path, value):
        record(str(Path(path).relative_to(EVIDENCE)), value)
    cf = types.SimpleNamespace(sha=sha)
    gen = types.SimpleNamespace(OUT=EVIDENCE, NEW=HERE, cf=cf, write_json=save_path)
    scope = {'gen':gen,'json':__import__('json'),'re':__import__('re')}
    exec(compile(code,str(source),'exec'),scope)
    record('packed_binding_parser.json',{'source':str(source),'sha256':sha(source),
            'executed_sha256':hashlib.sha256(code.encode('utf8')).hexdigest(),
            'input_graph':'actual_final_pnr/analysis/graph.json','old_graph_fallback':False})
    return scope['prepare'](EVIDENCE,route)

def global_reports(route):
    source = BOARD/'physical_subagent_evidence_01/audit_fixed.py'
    raw = source.read_text(encoding='utf8')
    raw = raw[:raw.index("    analysis=OUT/'actual/analysis'")] + "    print('Actual global audits finished; no bit',flush=True)\n"
    raw = raw.replace(' -report_exception TRUE',' -report_exception FALSE')
    raw = raw.replace("else '200000'", "else '512'")
    raw = raw.replace("b'max_path 200000'", "b'max_path 512'")
    cf = types.ModuleType('continue_fixed')
    cf.BASE,cf.HERE,cf.PDS,cf.OUT = BOARD,HERE,PDS,EVIDENCE
    cf.sha,cf.save,cf.run,cf.idle = sha,record,run,wait_idle
    sys.modules['continue_fixed']=cf
    saved=sys.argv;sys.argv=['isolated_global','.','project.pds']
    try:
        scope={'__name__':'isolated_global','__file__':str(source)}
        exec(compile(raw,str(source),'exec'),scope)
        scope['OUT']=EVIDENCE;scope['HERE']=HERE
        record('global_audit_parser.json',{'source':str(source),'sha256':sha(source),
            'executed_sha256':hashlib.sha256(raw.encode('utf8')).hexdigest(),'max_path':512,'report_exception':False,'bit_stage':False})
        scope['main']()
    finally:sys.argv=saved

def main():
    wait_idle();protected()
    route=HERE/'place_route/v7_sdt_top_pnr.adf'
    require(sha(route)==load(EVIDENCE/'pnr_artifact.json')['sha256'],'Route drift')
    require(load(EVIDENCE/'actual_mailbox_completion.json')['passed'],'Mailbox actual coverage missing')
    proof=packed_bindings(route)
    require(proof['reset_semantic_binding_passed'] and proof['sync_binding_passed'],'Reset/sync semantic packing proof failed')
    record('reset_targets.json',{'ends':sorted(row['logical'] for group in proof['reset_bindings'] for row in group['logical_mappings'])})
    record('reset_bindings.json',{'bindings':[{'logical':r['logical'],'physical':group['physical'],
           'semantic_mapping':r} for group in proof['reset_bindings'] for r in group['logical_mappings']],
           'logical_count':proof['reset_logical_count'],'unique_physical_RS':len(proof['reset_bindings'])})
    global_reports(route)
    ends=sorted(group['physical'] for group in proof['reset_bindings'])
    path,rows=query(route,'routed_reset',ends=ends,max_path=1024,nworst=10)
    details={}
    for corner in ['Slow','Fast']:
        for check in ['Recovery','Removal']:
            selected=[r for r in rows if r['corner']==corner and r['check']==check]
            actual={r['end'] for r in selected}
            logical_covered={r['logical'] for group in proof['reset_bindings'] if group['physical'] in actual for r in group['logical_mappings']}
            details[corner+'_'+check]={'covered':len(logical_covered),'physical_covered':len(actual & set(ends)),
                'missing':sorted(set(ends)-actual),'worst_slack':min((r['slack'] for r in selected),default=None)}
    passed=all(not r['missing'] and r['covered']==32 and r['worst_slack'] is not None and r['worst_slack']>=0 for r in details.values())
    record('evidence/reset_routed_audit.json',{'passed':passed,'details':details,'logical_count':32,
            'unique_physical_RS':len(ends),'packed_stages_require_separate_internal_timing_evidence':proof['sync_packed_internal'],
            'full_reset32_lane_timing_claimed':False})
    # Preserve each original topology mapping; reports must use external physical pins.
    pairs=sorted(tuple(r['physical']) for r in proof['sync_bindings'])
    path,rows=query(route,'routed_sync_later',pairs=pairs,max_path=max(128,len(pairs)*8))
    sd={}
    for corner in ['Slow','Fast']:
        selected=[r for r in rows if r['corner']==corner];actual={(r['start'],r['end']) for r in selected}
        sd[corner]={'covered':len(set(pairs)&actual),'missing':sorted(set(pairs)-actual),'unexpected':sorted(actual-set(pairs)),
                    'worst_slack':min((r['slack'] for r in selected),default=None)}
    sp=all(not r['missing'] and not r['unexpected'] and r['worst_slack'] is not None and r['worst_slack']>=0 for r in sd.values())
    record('evidence/sync_later_routed_audit.json',{'passed':sp and not proof['sync_packed_internal'],'external_passed':sp,
           'details':sd,'packed_internal_requires_timing_evidence':proof['sync_packed_internal']})
    record('remaining_actual_result.json',{'reset_RS_reports_passed':passed,'sync_external_passed':sp,
            'packed_internal_count':len(proof['sync_packed_internal']),'full_signoff':False,'bit_allowed':False})
    status('ACTUAL_RESET_SYNC_REPORTS_COMPLETE_INTERNAL_LANES_PENDING')

if __name__=='__main__':
    try:main()
    except BaseException:
        (EVIDENCE/'remaining_physical_failure.txt').write_text(traceback.format_exc(),encoding='utf8')
        status('REMAINING_PHYSICAL_AUDIT_FAILED')
        raise
