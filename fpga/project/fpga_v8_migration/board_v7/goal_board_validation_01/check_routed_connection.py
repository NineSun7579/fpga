"""Check actual saved routed mailbox paths and rejection of corrupt evidence."""
import copy
import hashlib
import json
from pathlib import Path
from routed_connection import identity_connection

HERE = Path(__file__).resolve().parent
graph_path = HERE.parent / 'source_diagnostics_timing_build_01/evidence/routed/analysis/graph.json'
review_path = HERE.parent / 'build01_binding_review01/review.json'
graph = json.loads(graph_path.read_bytes())
review = json.loads(review_path.read_bytes())
pairs = {(r['launch_Q'], r['capture_D']) for r in review['resolved'] if r['kind'] == 'register'}
assert len(pairs) == 1320
counts = {'direct': 0, 'buffered': 0}
for q, d in pairs:
    result = identity_connection(graph, q, d)
    counts['direct' if result['direct'] else 'buffered'] += 1
assert counts == {'direct': 1319, 'buffered': 1}

def reject(g, q, d):
    try:
        identity_connection(g, q, d)
    except (ValueError, KeyError):
        return
    raise AssertionError('Corrupted connectivity was accepted')

row = review['buffered_pairs'][0]
q, d = row['launch_Q'], row['capture_D']
cell = row['driver_trace'][0]['driver'].rsplit('/', 1)[0]
bad = copy.deepcopy(graph)
bad['primitives'][cell]['type'] = 'unproven_buffer'
reject(bad, q, d)
bad = copy.deepcopy(graph)
bad['pin_net'][cell + '/M'] = bad['pin_net'][d]
reject(bad, q, d)
bad = copy.deepcopy(graph)
bad['netpins'][bad['pin_net'][d]].append(q)
reject(bad, q, d)
bad = copy.deepcopy(graph)
bad['primitives'][cell]['parameters'].append(
    ['PARAMETER', 'INITA', ['B', '64', '"' + '1' * 64 + '"']])
reject(bad, q, d)

def binding(p):
    return {'path': str(p), 'bytes': p.stat().st_size,
            'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
result = {'status': 'PASS', 'actual_mailbox_pairs': len(pairs), 'counts': counts,
          'negative_checks': 4, 'graph': binding(graph_path), 'review': binding(review_path),
          'checker': binding(Path(__file__)), 'implementation': binding(HERE / 'routed_connection.py'),
          'scope': 'Saved build01 physical data connectivity only; no timing or bitstream acceptance'}
(HERE / 'routed_connection_check.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
