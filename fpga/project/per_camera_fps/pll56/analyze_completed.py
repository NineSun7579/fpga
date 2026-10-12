"""Read-only post-build audit; persist diagnosis only within owned candidate."""
import json
import re
from prepare import HERE, FROZEN, check, save, sha
from audit import constraints

run = HERE / 'build_po3co5wg'
report = run / 'final_sta/report_timing/top.rtr'
proof = check()
section = None
rows, paths, current = [], [], {}
with report.open('rb') as stream:
    for raw in stream:
        line = raw.strip().decode('ascii', errors='replace')
        match = re.search(r'(Setup|Hold|Recovery|Removal|Minimum Pulse Width) Summary\((Slow|Fast) Corner\)', line)
        if match:
            section = match.groups()
        match = re.fullmatch(r'(\w+)\s+(?:(\w+)\s+)?(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+)\s+(\d+)', line)
        if match and section:
            a, b, slack, total, failing, endpoints = match.groups()
            rows.append(dict(section=section, launch=a, capture=b or a, slack=float(slack),
                             total=float(total), failing=int(failing), endpoints=int(endpoints)))
        for token in ('Startpoint', 'Endpoint', 'Path Group', 'Path Type'):
            if line.startswith(token) and ':' in line:
                if token == 'Startpoint':
                    current = {}
                current[token] = line.split(':', 1)[1].strip()
        if line.startswith('Slack (VIOLATED)'):
            paths.append(dict(current, slack=float(line.split()[-1])))
assert len(rows) == 126, len(rows)
bad = [r for r in rows if r['slack'] < 0 or r['total'] != 0 or r['failing']]
assert bad and paths, 'Expected actual timing failure evidence'
save(run / 'final_sta_analysis.json', dict(status='FAIL', report_sha256=sha(report),
     summary_rows=rows, failing_rows=bad, violated_paths=paths,
     frozen_hash_verification=proof, bitgen_run=False))
save(run / 'clock_audit.json', constraints(report, FROZEN / 'final_sta/report_timing/top.rtr'))
receipt = json.loads((run / 'receipt.json').read_text())
receipt.update(final_sta_analysis_sha256=sha(run / 'final_sta_analysis.json'),
               clock_audit_sha256=sha(run / 'clock_audit.json'),
               pin_equivalence='PASS', phy_equivalence='PASS', timing_rows=126,
               timing_failing_rows=bad, bitgen_run=False)
assert not (run / 'top.sbit').exists() and not (run / 'bitgen').exists()
save(run / 'receipt.json', receipt)
save(HERE / 'current_run.json', receipt)
print(json.dumps(dict(failing_rows=bad, violated_paths=paths, finished=receipt['finished']), indent=2))
