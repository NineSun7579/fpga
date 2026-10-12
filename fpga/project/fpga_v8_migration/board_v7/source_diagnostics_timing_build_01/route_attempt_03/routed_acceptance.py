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
    prim, pn = graph['primitives'], graph['pin_net']
    errors, bindings, pairs = [], [], []
    def bind(logical):
        cell, port = logical.rsplit('/', 1)
        candidates = [k + '/' + port for k, r in prim.items() if k.startswith(cell + '/') and port in r['ports']]
        if len(candidates) != 1 or candidates[0] not in pn:
            errors.append({'logical': logical, 'candidates': candidates})
            return None
        return candidates[0]
    for camera in proof['cameras']:
        for logical in camera['synthesis']['leaves']:
            physical = bind(logical)
            if physical:
                bindings.append({'logical': logical, 'physical': physical})
        for a, b in camera['physical_pairs']:
            launch, capture = bind(a), bind(b)
            if not launch or not capture:
                continue
            q = launch.rsplit('/', 1)[0] + '/Q'
            if q not in pn or pn[q] != pn[capture]:
                errors.append({'pair': [a, b], 'physical': [launch, capture]})
            else:
                pairs.append({'logical': [a, b], 'physical': [launch, capture], 'direct_Q_to_D': True})
    result = {'passed': not errors and len(pairs) == 1320, 'physical_pair_count': len(pairs),
              'bindings': bindings, 'pairs': pairs, 'errors': errors, 'route_sha256': sha(route)}
    record('coverageproof_routed.json', result)
    require(result['passed'], 'Routed physical graph coverage failed')
    from targeted_reports import prove_single_pair
    prove_single_pair(route, result)
    source = EVIDENCE / 'actual_post_constraints/analysis'
    sg = load(source / 'graph.json'); classified = load(source / 'classification.json')
    logical_resets = sorted({q.rsplit('/', 1)[0] + '/' + p for x in classified['reset'] for q in x['actual_Q']
                             for p in sg['primitives'][q.rsplit('/', 1)[0]]['ports'] if p in ('P', 'C', 'R', 'S')})
    require(len(logical_resets) == 32, 'Expected 32 logical reset ends')
    reset_bindings = [{'logical': p, 'physical': bind(p)} for p in logical_resets]
    sync_bindings = []
    for row in classified['ordinary_pairs']:
        a, b = row['launch_CLK'], row['capture_D']
        x, y = bind(a), bind(b)
        require(x and y and pn[x.rsplit('/', 1)[0] + '/Q'] == pn[y], 'Routed synchronizer later stage topology failed')
        sync_bindings.append({'logical': [a, b], 'physical': [x, y]})
    require(not errors and all(r['physical'] for r in reset_bindings), 'Physical reset/sync binding incomplete')
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
                'stream_parser_sha256': sha(HERE / 'targeted_reports.py'),
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
