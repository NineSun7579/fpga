"""Reuse reviewed report parsers, but bind this build and never generate bit."""
import json
import re
import sys
import types
from pathlib import Path
from preflight import HERE, BOARD, load, sha, require
from physical_flow import EVIDENCE, PDS, record, run, export_graph, protected, snapshot, status

def routed_binding(route):
    graph, analysis = export_graph('routed', route, False)
    proof = load(EVIDENCE / 'coverageproof_synthesis.json')
    from physical_flow import TOOLS
    sys.path.insert(0,str(TOOLS))
    from routed_identity import truth_proof, bind_clock_leaf
    from graph_adapter import Resolver
    synthesis=EVIDENCE/'actual_post_constraints/analysis'
    sg=load(synthesis/'graph.json');manifest=load(synthesis/'manifest.json')
    result=truth_proof(graph,sg,manifest,Path(__file__).resolve().parent/'libraries/routed_truth_reference.py.txt')
    result.update(bindings=[],route_sha256=sha(route),graph_sha256=sha(analysis/'graph.json'),
                  synthesis_graph_sha256=sha(synthesis/'graph.json'),manifest_sha256=sha(synthesis/'manifest.json'))
    r=Resolver(graph);clock_coverage=[]
    for camera in proof['cameras']:
        # Preserve copies as endpoint sets, and missing leaves only with actual tool cleanup.
        for logical in camera['synthesis']['leaves']:
            try:result['bindings'].append(bind_clock_leaf(graph,logical,[EVIDENCE/'dev_map.log',EVIDENCE/'pnr.log']))
            except (RuntimeError,OSError) as exc:result['errors'].append({'logical':logical,'error':str(exc)})
        try:
            leaves=r.clock_leaves(camera['camera'])
            bound={p for b in result['bindings'] for p in b['physical'] if b['logical'] in camera['synthesis']['leaves']}
            require(bound==set(leaves['leaves']),'Actual surviving routed camera clock coverage differs from bound clone/cleanup evidence')
            clock_coverage.append(leaves)
        except RuntimeError as exc:result['errors'].append({'camera':camera['camera'],'error':str(exc)})
    result['clock_coverage']=clock_coverage
    result['data_function_passed']=result['passed']
    result['passed']=result['passed'] and not result['errors']
    record('coverageproof_routed.json', result)
    require(result['passed'], 'Routed physical graph coverage failed')
    # Derive reset pin names (P/C versus physical RS) from THIS routed graph.
    from physical_flow import endpoint_audit, TOOLS
    sys.path.insert(0,str(TOOLS))
    from graph_adapter import classify
    endpoint_audit('routed',graph,load(EVIDENCE/'actual_post_constraints/analysis/graph.json'))
    classified=classify(graph)
    resetrows=[r for r in classified['rows'] if r['chain'] in {'cr','hr','reset_pipe'}]
    logical_resets=sorted(r['logical'] for r in resetrows)
    reset_bindings=[{'logical':r['logical'],'physical':r['reset'],'clock_physical':r['CLK']} for r in resetrows]
    require(len(reset_bindings)==len({r['physical'] for r in reset_bindings})==32,'32 actual routed reset pins required')
    sync_bindings=[{'logical':[r['launch_CLK'],r['capture_D']],'physical':[r['launch_CLK'],r['capture_D']]} for r in classified['ordinary_pairs']]
    require(len(sync_bindings)==16,'16 actual same-domain later-stage pairs required')
    require(not result['errors'] and all(r['physical'] for r in reset_bindings), 'Physical reset/sync binding incomplete')
    result['independent_storage_gate_passed']=True
    result['independent_registers']=60
    record('coverageproof_routed.json',result)
    from cdb_proof import prove
    prove('routed',EVIDENCE/'routed/synthesis_export/synthesis_dump.txt',graph,result)
    from targeted_reports import prove_single_pair
    prove_single_pair(route,result)
    record('reset_targets.json', {'ends': logical_resets})
    record('reset_bindings.json', {'bindings': reset_bindings})
    record('sync_bindings.json', {'bindings': sync_bindings})
    return result, reset_bindings, sync_bindings

def audit_all(route):
    # Always preserve fresh global negative-slack results before targeted gates
    # can fail. No failed global/target gate is waived to obtain a local bit.
    from global_audit import audit
    audit(route)
    sta=load(EVIDENCE/'evidence/final_sta_summary.json')
    groups=sta['all_corner_summaries']
    kinds={'Setup','Hold','Recovery','Removal','Minimum Pulse Width'}
    gates={'ten_groups':len(groups)==10 and {(g['section'],g['corner']) for g in groups}=={(k,c) for k in kinds for c in ['Slow','Fast']}
           and all(g['rows'] and g['sum_failing_endpoints']==0 and all(r['worst_slack_ns']>=0 and r['total_negative_slack_ns']==0 and r['total_endpoints']>0 for r in g['rows']) for g in groups)}
    hsst=load(EVIDENCE/'evidence/hsst_actual_phy_audit.json')
    gates.update(hsst=hsst['sites_identical_to_baseline'] and hsst['dedicated_connections_identical_to_baseline'],
                 io=load(EVIDENCE/'evidence/io_audit.json')['passed'],
                 motion32=load(EVIDENCE/'evidence/motion_routed_resource_proof.json')['routed_history_DRM36K_total']==32)
    record('acceptance_gates.json',gates)
    try:
        coverage,reset_bindings,sync_bindings=routed_binding(route)
        from targeted_reports import audit_targets
        gates.update(audit_targets(route,coverage,reset_bindings,sync_bindings))
        protected();gates['protected']=True
        require(load(EVIDENCE/'runtime_clockpair_proof.json')['passed'],'Actual runtime U-B inheritance missing')
        gates['runtime_U_B']=True
    except BaseException as exc:
        gates['targeted_and_routed_proof_complete']=False
        record('acceptance_gates.json',gates)
        record('routed_signoff_blocked.json',{'reason':str(exc),'global_STA_preserved':True,'bit_generated':False})
        raise
    record('acceptance_gates.json',gates)
    require(all(gates.values()),'Actual full routed acceptance gates failed; leave timing evidence, no bit')
    record('signoff.json',{'passed':True,'gates':gates,'motion32':True,'reset32':True,
           'routed_graph_coverage':True,'route_sha256':sha(route),'remote_or_program':False,'bit_generated':False})
    status('ALL_MEASURED_BUILD03_GATES_PASS_NO_BIT_YET')

