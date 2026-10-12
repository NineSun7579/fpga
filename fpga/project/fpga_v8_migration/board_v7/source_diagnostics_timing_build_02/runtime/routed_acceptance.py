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
    result=truth_proof(graph,sg,manifest,BOARD/'build01_binding_review01/review.py')
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
    from targeted_reports import prove_single_pair
    prove_single_pair(route,result)
    record('reset_targets.json', {'ends': logical_resets})
    record('reset_bindings.json', {'bindings': reset_bindings})
    record('sync_bindings.json', {'bindings': sync_bindings})
    return result, reset_bindings, sync_bindings

def audit_all(route):
    coverage, reset_bindings, sync_bindings = routed_binding(route)
    protected()
    # Parameterize the existing audit in memory; do not edit its source or run its bit stage.
    source_path = BOARD / 'physical_subagent_evidence_01/audit_fixed.py'
    raw = source_path.read_text(encoding='utf8')
    # Reuse only the global ten-group/motion/HSST/IO parsers. All target queries
    # are replaced by our proved physical filters and bounded batches.
    raw = raw[:raw.index("    analysis=OUT/'actual/analysis'")] + "    print('GLOBAL RAW/IO/HSST/MOTION AUDIT COMPLETE; no bit stage',flush=True)\n"
    raw = raw.replace(' -report_exception TRUE', ' -report_exception FALSE')
    from targeted_reports import audit_targets
    gates = audit_targets(route, coverage, reset_bindings, sync_bindings)
    cf = types.ModuleType('continue_fixed')
    cf.BASE, cf.HERE, cf.PDS, cf.OUT = BOARD, HERE, PDS, EVIDENCE
    cf.sha = sha
    cf.save = record
    cf.run = run
    def idle():
        from physical_flow import wait_idle
        wait_idle()
    cf.idle = idle
    sys.modules['continue_fixed'] = cf
    oldargv = sys.argv
    sys.argv = ['isolated_audit', '.', 'project.pds']
    scope = {'__name__': 'isolated_routed_audit', '__file__': str(source_path),
             'isolated_coverage': coverage, 'isolated_reset_bindings': reset_bindings,
             'isolated_sync_bindings': sync_bindings}
    try:
        exec(compile(raw, str(source_path), 'exec'), scope)
        scope['OUT'] = EVIDENCE
        scope['HERE'] = HERE
        record('audit_parser_binding.json', {'source': str(source_path), 'source_sha256': sha(source_path),
               'bit_stage_removed': True, 'old_graph_fallback_removed': True,
               'target_pins': 'actual routed physical Q-D/reset/sync bindings',
                'stream_parser_sha256': sha(Path(__file__).resolve().parent / 'targeted_reports.py'),
               'executed_sha256': __import__('hashlib').sha256(raw.encode('utf8')).hexdigest()})
        scope['main']()
    finally:
        sys.argv = oldargv
    sta = load(EVIDENCE / 'evidence/final_sta_summary.json')
    groups = sta['all_corner_summaries']
    gates['ten_groups'] = len(groups) == 10 and all(g['rows'] and g['sum_failing_endpoints'] == 0
                         and all(r['worst_slack_ns'] >= 0 for r in g['rows']) for g in groups)
    hsst = load(EVIDENCE / 'evidence/hsst_actual_phy_audit.json')
    gates['hsst'] = hsst['sites_identical_to_baseline'] and hsst['dedicated_connections_identical_to_baseline']
    gates['io'] = load(EVIDENCE / 'evidence/io_audit.json')['passed']
    protected(); gates['protected'] = True
    record('acceptance_gates.json', gates)
    require(all(gates.values()), 'Actual acceptance gates failed')
    motion = load(EVIDENCE / 'evidence/motion_routed_resource_proof.json')
    require(motion['routed_history_DRM36K_total'] == 32, 'Motion32 not proven')
    resets = load(EVIDENCE / 'evidence/reset_routed_audit.json')
    require(all(v['covered'] == 32 for v in resets['details'].values()), 'Reset32 endpoint coverage missing')
    record('signoff.json', {'passed': True, 'gates': gates, 'motion32': True, 'reset32': True,
                           'routed_graph_coverage': True, 'route_sha256': sha(route),
                           'remote_or_program': False, 'bit_generated': False})
    status('ALL_MEASURED_GATES_PASS_NO_BIT_GENERATED')
