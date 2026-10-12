"""Exact physical filters, bounded batches, streaming record/slack validation."""
import re
from pathlib import Path
from preflight import require, sha, load
from physical_flow import EVIDENCE, PDS, run, record

BAD = re.compile(rb'Timing-4006|STA-3016|unknown\s+(?:arguments?|options?)', re.I)

def records(path):
    row = None
    with Path(path).open(encoding='gb18030', errors='replace') as stream:
        for line in stream:
            field = re.match(r'^\s*(Startpoint|Endpoint|Path Type|Path Class|Timing Exception)\s*:\s*(.*?)\s*$', line)
            if field:
                key, value = field.groups()
                if key == 'Startpoint':
                    require(row is None, 'Incomplete record without Slack before next Startpoint')
                    row = {'start': value.split(' (', 1)[0], 'end': None, 'kind': None,
                           'path_class': None, 'corner': None, 'exception': None, 'check': None, 'slack': None}
                elif row is not None:
                    name = {'Endpoint': 'end', 'Path Type': 'kind', 'Path Class': 'path_class', 'Timing Exception': 'exception'}[key]
                    row[name] = value.split(' (', 1)[0] if key == 'Endpoint' else value
                    if key == 'Path Type':
                        corner = re.search(r'\b(slow|fast)\s+corner\b', value, re.I)
                        row['corner'] = corner[1].capitalize() if corner else None
                    elif key == 'Path Class' and value.lower() in {'minimum pulse width', 'pulse width path', 'minimum pulse width path'}:
                        row['check'] = 'Minimum Pulse Width'
            if row is None:
                continue
            check = re.match(r'^\s*(Recovery|Removal)\s+time\b', line, re.I)
            if check:
                row['check'] = check[1].capitalize()
            elif re.match(r'^\s*(?:(?:Minimum|Min|High|Low)\s+)?Pulse\s+width\b', line, re.I):
                row['check'] = 'Minimum Pulse Width'
            slack = re.search(r'\bSlack\s*\((?:MET|VIOLATED)\)\s+(-?\d+(?:\.\d+)?)', line)
            if slack:
                row['slack'] = float(slack[1])
                require(row['start'] and row['end'] and row['corner'], 'Incomplete scored record fields')
                yield row
                row = None  # summaries following Slack cannot contaminate this record
    require(row is None, 'Report ends with an incomplete unscored record')

def list_tcl(items):
    return '{' + ' '.join('{' + p + '}' for p in sorted(set(items))) + '}'

def query(route, label, pairs=(), ends=(), max_path=8, nworst=2):
    dest = EVIDENCE / label; dest.mkdir()
    command = ('report_timing -input_db_file {' + route.as_posix() + '} -force_to_run -delay_type min_max'
               ' -report_exception TRUE -input_pins TRUE -nworst ' + str(nworst) + ' -max_path ' + str(max_path))
    if pairs:
        command += ' -from ' + list_tcl(a for a, b in pairs)
        ends = [b for a, b in pairs]
    require(ends, 'Empty physical target filter')
    command += ' -to ' + list_tcl(ends)
    script = dest / 'export.tcl'
    script.write_bytes(('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n' + command + '\n').encode('ascii'))
    before = sha(route)
    run(label, [str(PDS), '-file', str(script), '-work_dir', str(dest), '-project_name', 'timing01_' + label], dest)
    require(sha(route) == before, 'Target report mutated routed DB')
    logs = [EVIDENCE / (label + '.log'), dest / 'report_timing/run.log']
    hits = []
    for path in logs:
        require(path.is_file(), 'Missing actual targeted tool log')
        with path.open('rb') as stream:
            for number, line in enumerate(stream, 1):
                if BAD.search(line):
                    hits.append({'path': str(path), 'line': number, 'text': line.decode('ascii', 'backslashreplace')})
    record(label + '_filter_guard.json', {'passed': not hits, 'hits': hits, 'route_sha256': before})
    require(not hits, 'Actual target filter ignored/unsupported: ' + label)
    report = dest / 'report_timing/v7_sdt_top.rtr'
    rows = list(records(report))
    require(rows, 'Empty targeted actual report')
    allowed_ends = set(ends)
    allowed_starts = {a for a, b in pairs}
    require(all(r['end'] in allowed_ends and (not pairs or r['start'] in allowed_starts) for r in rows),
            'Target filter returned unrelated physical endpoints')
    return report, rows

def prove_single_pair(route, coverage):
    allpairs = sorted(tuple(r['physical']) for r in coverage['pairs'])
    require(len(set(allpairs)) == 1320, 'Physical pair binding must contain 1320 unique pairs')
    receipt = EVIDENCE / 'single_pair_filter_proof.json'
    if receipt.exists():
        prior = load(receipt)
        report = EVIDENCE / 'target_single_pair/report_timing/v7_sdt_top.rtr'
        require(prior['passed'] is True and prior['pair'] == list(allpairs[0])
                and prior['route_sha256'] == sha(route) and prior['report_sha256'] == sha(report), 'Stale single-pair proof')
        return
    report, rows = query(route, 'target_single_pair', pairs=[allpairs[0]], max_path=8)
    require(all((r['start'], r['end']) == allpairs[0] and r['exception']
                and 'MaxDelay Path 15.238' in r['exception'] for r in rows), 'Single-pair filter/budget not proven')
    require({r['corner'] for r in rows} == {'Slow', 'Fast'}, 'Single physical pair needs both actual corners')
    record('single_pair_filter_proof.json', {'passed': True, 'pair': allpairs[0], 'records': rows,
           'report_sha256': sha(report), 'route_sha256': sha(route)})

def audit_targets(route, coverage, reset_bindings, sync_bindings):
    allpairs = sorted(tuple(r['physical']) for r in coverage['pairs'])
    prove_single_pair(route, coverage)
    aggregate = EVIDENCE / 'routed_mailbox/report_timing/v7_sdt_top.rtr'
    aggregate.parent.mkdir(parents=True)
    detail = {c: {'pairs': set(), 'worst': None} for c in ['Slow', 'Fast']}
    reports = []
    with aggregate.open('xb') as output:
        for index in range(0, len(allpairs), 64):
            batch = allpairs[index:index+64]
            path, rows = query(route, 'mailbox_batch_' + str(index // 64).zfill(3), pairs=batch,
                               max_path=len(batch)*4, nworst=2)
            actual = {(r['start'], r['end']) for r in rows}
            require(actual <= set(batch), 'Cross-pair/unrelated report records')
            for row in rows:
                require(row['exception'] and 'MaxDelay Path 15.238' in row['exception'], 'Mailbox budget exception absent')
                item = detail[row['corner']]; item['pairs'].add((row['start'], row['end']))
                item['worst'] = row['slack'] if item['worst'] is None else min(item['worst'], row['slack'])
            with path.open('rb') as source:
                while True:
                    block = source.read(1024*1024)
                    if not block: break
                    output.write(block)
            output.write(b'\n')
            reports.append({'path': str(path), 'sha256': sha(path), 'pairs': batch})
    results = {c: {'covered': len(x['pairs'] & set(allpairs)), 'missing': sorted(set(allpairs)-x['pairs']),
                  'unexpected': sorted(x['pairs']-set(allpairs)), 'worst_slack': x['worst']} for c, x in detail.items()}
    passed = all(not r['missing'] and not r['unexpected'] and r['worst_slack'] is not None and r['worst_slack'] >= 0 for r in results.values())
    record('evidence/mailbox_routed_audit.json', {'passed': passed, 'details': results, 'batch_reports': reports})
    require(passed, 'Full actual physical mailbox Slow/Fast coverage/slack failed')
    resets = sorted({r['physical'] for r in reset_bindings})
    require(len(resets) == 32, '32 independent actual physical reset targets required')
    path, rows = query(route, 'routed_reset', ends=resets, max_path=1024, nworst=10)
    reset_detail = {}
    for corner in ['Slow', 'Fast']:
        for kind in ['Recovery', 'Removal']:
            selected = [r for r in rows if r['corner'] == corner and r['check'] == kind]
            covered = {r['end'] for r in selected}
            reset_detail[corner+'_'+kind] = {'covered': len(covered & set(resets)), 'missing': sorted(set(resets)-covered),
                                          'worst_slack': min((r['slack'] for r in selected), default=None)}
    reset_pass = all(not r['missing'] and r['worst_slack'] is not None and r['worst_slack'] >= 0 for r in reset_detail.values())
    record('evidence/reset_routed_audit.json', {'passed': reset_pass, 'details': reset_detail})
    clock_targets = sorted({r['physical'].rsplit('/', 1)[0] + '/CLK' for r in reset_bindings})
    path, rows = query(route, 'routed_reset_mpw', ends=clock_targets, max_path=1024, nworst=10)
    mpw_details = {}
    for corner in ['Slow', 'Fast']:
        selected = [r for r in rows if r['corner'] == corner and r['check'] == 'Minimum Pulse Width']
        covered = {r['end'] for r in selected}
        mpw_details[corner] = {'covered': len(covered & set(clock_targets)), 'missing': sorted(set(clock_targets)-covered),
                               'worst_slack': min((r['slack'] for r in selected), default=None)}
    mpw_pass = all(not r['missing'] and r['worst_slack'] is not None and r['worst_slack'] >= 0 for r in mpw_details.values())
    record('evidence/reset_mpw_routed_audit.json', {'passed': mpw_pass, 'details': mpw_details, 'clock_targets': clock_targets})
    syncpairs = sorted(tuple(r['physical']) for r in sync_bindings)
    path, rows = query(route, 'routed_sync_later', pairs=syncpairs, max_path=len(syncpairs)*8)
    sync_detail = {}
    for corner in ['Slow', 'Fast']:
        subset = [r for r in rows if r['corner'] == corner]
        actual = {(r['start'], r['end']) for r in subset}
        sync_detail[corner] = {'covered': len(actual & set(syncpairs)), 'missing': sorted(set(syncpairs)-actual),
                               'unexpected': sorted(actual-set(syncpairs)), 'worst_slack': min((r['slack'] for r in subset), default=None)}
    sync_pass = all(not r['missing'] and not r['unexpected'] and r['worst_slack'] is not None and r['worst_slack'] >= 0 for r in sync_detail.values())
    record('evidence/sync_later_routed_audit.json', {'passed': sync_pass, 'details': sync_detail})
    require(reset_pass and mpw_pass and sync_pass, 'Reset Recovery/Removal/MPW or sync later physical gate failed')
    return {'mailbox': passed, 'reset': reset_pass, 'reset_mpw': mpw_pass, 'sync_later': sync_pass, 'single_pair_filter': True}
