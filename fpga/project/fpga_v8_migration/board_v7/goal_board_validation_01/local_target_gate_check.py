"""Real parser counts and negative semantic checks, never actual delivery PASS."""
from collections import Counter
import json
from pathlib import Path
import tempfile
from new_program_candidate import (HERE, records, raw_target_details, target_log_check,
                                   actual_endpoint_gate, require, sha)
from new_prepare_delivery import ARTIFACTS, AUDIT_ROLES
from endpoint_recompute import ROLES, recompute


def rejects(call):
    try:
        call()
    except (ValueError, RuntimeError, KeyError, TypeError):
        return
    raise AssertionError('Semantic negative unexpectedly accepted')


def main():
    build = HERE.parent / 'source_diagnostics_timing_build_01/evidence'
    counts = {}
    for name in ('routed_reset', 'routed_sync_later'):
        path = build / name / 'report_timing/v7_sdt_top.rtr'
        rows = list(records(path))
        counts[name] = {'records': len(rows), 'checks': dict(Counter(str(r['corner']) + '_' + str(r['check']) for r in rows)),
                        'pairs': len({(r['start'], r['end']) for r in rows}),
                        'ends': len({r['end'] for r in rows}), 'sha256': sha(path)}
    root = HERE.parent / 'source_diagnostics_timing_build_03/runtime'
    sources = {k: (root / p).resolve() for k, p in ROLES.items()}
    graph = json.loads((build / 'routed/analysis/graph.json').read_bytes())
    rejects(lambda: recompute(graph, sources, root, require, sha))
    rejects(lambda: actual_endpoint_gate({'status': 'PASS', 'independent_registers': 60, 'rows': []}, graph))
    negative = 2
    with tempfile.TemporaryDirectory(dir=HERE) as folder:
        report = Path(folder) / 'semantic.rtr'
        def row(start='cell/CLK', end='cell/CLK', corner='slow', check='Minimum Pulse Width', slack='1.0'):
            return f'Startpoint : {start}\nEndpoint : {end}\nPath Type : max ({corner} corner)\nPath Class : {check}\n{check} time 0.1\nSlack (MET) {slack}\n'
        base = row() + row(corner='fast')
        for text in ('', row(), base.replace('1.0', '-1.0'), base.replace('cell/CLK', 'foreign/CLK'),
                     base.replace('Startpoint : cell/CLK', 'Startpoint : foreign/CLK'),
                     base + 'Startpoint : incomplete/CLK\n'):
            report.write_text(text)
            rejects(lambda: raw_target_details(report, {'cell/CLK'}, ('Minimum Pulse Width',)))
            negative += 1
        sync = ''.join(row('launch/CLK', 'capture/D', c, k) for c in ('slow', 'fast') for k in ('Setup', 'Hold'))
        for text in (sync.replace(row('launch/CLK', 'capture/D', 'fast', 'Hold'), ''),
                     sync.replace('capture/D', 'other/D'), sync.replace('1.0', '-1.0')):
            report.write_text(text)
            rejects(lambda: raw_target_details(report, {('launch/CLK', 'capture/D')}, ('Setup', 'Hold'), True))
            negative += 1
        for text in ('Timing-4006', 'timing4006', 'STA-3016', 'sta3016', 'unknown option', 'Unknown arguments'):
            report.write_text(text)
            rejects(lambda: target_log_check(report))
            negative += 1
    assert {'reset_mpw_raw', 'sync_later_raw', 'sync_pairs', 'routed_endpoint_audit'} <= set(ARTIFACTS)
    assert {'routed_connection', 'endpoint_recompute', *ROLES} <= AUDIT_ROLES
    result = {'actual_build01_parser_counts': counts, 'negative_semantic_checks': negative,
              'build01_independent60_rejected': True, 'actual_build03_report_count': 0,
              'actual_delivery_pass': False, 'PDS_remote_DMA_program': False}
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    main()
