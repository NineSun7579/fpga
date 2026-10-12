"""Stream the production STA bytes, retaining every actual violation."""
from collections import Counter
import re
from prepare import save, sha, FROZEN
from audit import constraints

def diagnose(run, output=None):
    output = output or run
    report = run / 'final_sta/report_timing/top.rtr'
    section = None
    rows, paths, current, detail = [], [], {}, []
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
            if line.startswith('Startpoint'):
                current, detail = {}, []
            if current or line.startswith('Startpoint'):
                detail.append(raw)
            for token in ('Startpoint', 'Endpoint', 'Path Group', 'Path Type', 'Clock Skew'):
                if line.startswith(token) and ':' in line:
                    current[token] = line.split(':', 1)[1].strip()
            if line.startswith('Slack (VIOLATED)'):
                paths.append(dict(current, slack=float(line.split()[-1]),
                                  detail=b''.join(detail).decode('ascii', errors='replace')))
    bad = [r for r in rows if r['slack'] < 0 or r['total'] != 0 or r['failing']]
    result = dict(status='FAIL' if bad else 'PASS', report_sha256=sha(report),
                  summary_rows=rows, failing_rows=bad, violated_paths=paths,
                  violation_distribution=dict(Counter(p.get('Path Group', '?') + ' / ' + p.get('Path Type', '?') for p in paths)))
    save(output / 'final_sta_analysis.json', result)
    save(output / 'clock_audit.json', constraints(report, FROZEN / 'final_sta/report_timing/top.rtr'))
    assert len(rows) == 126, len(rows)
    print('FULL_STA_DIAGNOSIS', result['status'], 'rows', len(rows),
          'violated_paths', len(paths), result['violation_distribution'], flush=True)
    return result
