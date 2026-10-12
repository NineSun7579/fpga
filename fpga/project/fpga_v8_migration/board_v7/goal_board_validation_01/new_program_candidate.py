"""Candidate-only validatedDelivery v1 consumer; default is offline --check.

This contract is newly proposed, not an existing build producer's schema.
No legacy V7 verifier/main is imported. Flash is not exposed.
"""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys
import time
from types import SimpleNamespace
import uuid
from routed_connection import identity_connection
from endpoint_recompute import ROLES as ENDPOINT_ROLES, recompute

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent / 'source_diagnostics_timing_build_01'
ALLOWED_BUILDS = {name: (HERE.parent / name).resolve() for name in
                  ('source_diagnostics_timing_build_01', 'source_diagnostics_timing_build_02',
                   'source_diagnostics_timing_build_03')}
VENDOR = HERE.parents[2] / 'tools' / 'program_100h_motion.py'
KINDS = ('Setup', 'Hold', 'Recovery', 'Removal', 'Minimum Pulse Width')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def audit_metadata(path):
    # audit_fixed writes passed/details before enormous records[]. Read those
    # actual fields without allocating the multi-GB records/detail payload.
    decoder = json.JSONDecoder()
    result = {}
    buffer = ''
    with Path(path).open(encoding='utf-8-sig') as stream:
        def more():
            nonlocal buffer
            chunk = stream.read(65536)
            require(chunk and len(buffer) < 16 * 1024 * 1024, 'Audit metadata missing/oversized')
            buffer += chunk
        def strip():
            nonlocal buffer
            buffer = buffer.lstrip()
            while not buffer:
                more()
                buffer = buffer.lstrip()
        def value():
            nonlocal buffer
            while True:
                try:
                    obj, end = decoder.raw_decode(buffer)
                    buffer = buffer[end:]
                    return obj
                except json.JSONDecodeError:
                    more()
        strip()
        require(buffer.startswith('{'), 'Audit must be a JSON object')
        buffer = buffer[1:]
        while True:
            strip()
            key = value()
            strip()
            require(buffer.startswith(':'), 'Malformed audit JSON')
            buffer = buffer[1:]
            strip()
            require(key != 'records', 'Audit passed/details missing before records')
            require(key not in result, 'Duplicate audit metadata key')
            result[key] = value()
            if {'passed', 'details'} <= result.keys():
                return {k: result[k] for k in ('passed', 'details')}
            strip()
            require(buffer.startswith(','), 'Audit passed/details missing')
            buffer = buffer[1:]


def absolute(value):
    require(isinstance(value, str) and bool(value), 'Missing concrete absolute path')
    p = Path(value)
    require(p.is_absolute(), 'Relative path rejected')
    return p.resolve(strict=True)


def delivery_build(document):
    candidate = document.get('candidate_id')
    require(candidate in ALLOWED_BUILDS, 'Unknown diagnostic build candidate')
    build = absolute(document['build_root'])
    require(build == ALLOWED_BUILDS[candidate], 'Candidate/build root mismatch')
    return build


def bound(entry):
    p = absolute(entry['path'])
    require(p.is_file() and p.stat().st_size > 0, 'Missing/empty artifact')
    require(type(entry['bytes']) is int and p.stat().st_size == entry['bytes'], 'Artifact size mismatch')
    require(re.fullmatch('[0-9a-f]{64}', entry['sha256']) and sha(p) == entry['sha256'],
            'Artifact hash mismatch')
    return p


def nonnegative(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def raw_summaries(path):
    groups = []
    current = None
    production = multi = False
    design = []
    path_open = scored = False
    unscored = 0
    with path.open(encoding='gb18030', errors='replace') as stream:
        for line in stream:
            production |= 'Timing Models: Production' in line
            multi |= 'Timing analysis mode : multi corner' in line
            if line.startswith('Design Summary'):
                design.append(line.strip())
            if re.match(r'^\s*Startpoint\s*:', line):
                if path_open and not scored:
                    unscored += 1
                path_open, scored = True, False
            if path_open and re.search(r'Slack \((?:MET|VIOLATED)\)\s+(-?\d+(?:\.\d+)?)', line):
                scored = True
            require('Slack (VIOLATED)' not in line, 'Raw STA contains violated path')
            match = re.search(r'(Setup|Hold|Recovery|Removal|Minimum Pulse Width) Summary\((Slow|Fast) Corner\):', line)
            if match:
                current = {'section': match[1], 'corner': match[2], 'rows': []}
                groups.append(current)
                continue
            if line.startswith('===='):
                current = None
            if current:
                cols = line.split()
                index = 1 if current['section'] == 'Minimum Pulse Width' else 2
                if len(cols) == index + 4 and re.fullmatch(r'-?\d+\.\d+', cols[index]):
                    current['rows'].append({'worst_slack_ns': float(cols[index]),
                                            'total_negative_slack_ns': float(cols[index + 1]),
                                            'failing_endpoints': int(cols[index + 2]),
                                            'total_endpoints': int(cols[index + 3])})
    require(production and multi, 'Production multi-corner report missing')
    require(len(groups) == 10 and {(g['section'], g['corner']) for g in groups} ==
            {(k, c) for k in KINDS for c in ('Slow', 'Fast')}, 'Ten unique nonempty raw STA groups required')
    for g in groups:
        require(g['rows'] and all(nonnegative(r['worst_slack_ns']) and r['total_negative_slack_ns'] == 0 and
                r['failing_endpoints'] == 0 and r['total_endpoints'] > 0 for r in g['rows']),
                'Empty/failing raw STA group: ' + g['section'] + '/' + g['corner'])
    if path_open and not scored:
        unscored += 1
    return {'groups': groups, 'design_summary': design, 'unscored_io_paths': unscored}


def records(path):
    # Stream actual fields; routed pins have no " (" and corners are lowercase.
    row = None
    with path.open(encoding='gb18030', errors='replace') as stream:
        for line in stream:
            match = re.match(r'^\s*(Startpoint|Endpoint|Path Type|Path Class|Timing Exception)\s*:\s*(.*?)\s*$', line)
            if match:
                name, value = match.groups()
                if name == 'Startpoint':
                    require(row is None, 'Incomplete targeted timing record before next Startpoint')
                    row = dict(start=None, end=None, kind=None, path_class=None, corner=None, exception=None, slack=None, check=None)
                if row is None:
                    continue
                key = {'Startpoint': 'start', 'Endpoint': 'end', 'Path Type': 'kind',
                       'Path Class': 'path_class', 'Timing Exception': 'exception'}[name]
                row[key] = value.split(' (', 1)[0] if name in ('Startpoint', 'Endpoint') else value
                if name == 'Path Class' and value.lower() in {'minimum pulse width', 'pulse width path', 'minimum pulse width path'}:
                    row['check'] = 'Minimum Pulse Width'
                if name == 'Path Type':
                    corner = re.search(r'\b(slow|fast)\s+corner\b', value, re.I)
                    row['corner'] = corner[1].capitalize() if corner else None
            check = re.match(r'^\s*(Recovery|Removal|Setup|Hold)\s+time\b', line, re.I)
            if row is not None and check:
                row['check'] = check[1].capitalize()
            if row is not None and re.match(r'^\s*(?:(?:Minimum|Min|High|Low)\s+)?Pulse\s+width\b', line, re.I):
                row['check'] = 'Minimum Pulse Width'
            slack = re.search(r'Slack \((?:MET|VIOLATED)\)\s+(-?\d+(?:\.\d+)?)', line)
            if row is not None and slack:
                require(row['start'] and row['end'] and row['corner'], 'Incomplete scored targeted record')
                row['slack'] = float(slack[1])
                yield row
                row = None
        require(row is None, 'Incomplete targeted timing record at EOF')


def target_log_check(path):
    with path.open('rb') as stream:
        for line in stream:
            require(not (re.search(rb'Timing-?4006|STA-?3016', line, re.I) or
                         re.search(rb'unknown\s+(?:arguments?|options?)', line, re.I)),
                    'Timing target was ignored or invalid: ' + str(path))


def phase_pairs(mapping, coverage, graph):
    logical = {(r['mapping']['launch_CLK'], r['mapping']['capture_D']) for r in mapping['resolved']
               if r['mapping']['kind'] == 'register'}
    require(logical and all(a and b for a, b in logical), 'Empty synthesis logical mapping')
    require(coverage.get('passed') is True and not coverage['errors'] and coverage['bindings'], 'Routed coverage not passed')
    pinmap = {}
    reverse = {}
    def bind(a, b):
        require(a and b and (a not in pinmap or pinmap[a] == b) and
                (b not in reverse or reverse[b] == a), 'Ambiguous/non-injective phase binding')
        cell, port = b.rsplit('/', 1)
        require(cell in graph['primitives'] and port in graph['primitives'][cell]['ports'] and
                b in graph['pin_net'], 'Physical binding absent/unconnected in routed graph')
        pinmap[a] = b
        reverse[b] = a
    for row in coverage['bindings']:
        bind(row['logical'], row['physical'])
    translated = {}
    for row in coverage['pairs']:
        a, b = row['logical']
        x, y = row['physical']
        require((a, b) not in translated, 'Duplicate mailbox pair')
        bind(a, x)
        bind(b, y)
        q = x.rsplit('/', 1)[0] + '/Q'
        connection = identity_connection(graph, q, y)
        if 'direct_Q_to_D' in row:
            require(row['direct_Q_to_D'] is connection['direct'], 'Incorrect direct mailbox connection claim')
        translated[(a, b)] = (x, y)
    require(set(translated) == logical and len(set(translated.values())) == len(logical) and
            coverage['physical_pair_count'] == len(logical), 'Phase pair mapping must be complete and one-to-one')
    return set(translated.values())


def phase_resets(target_doc, binding_doc, graph):
    logical = set(target_doc['ends'])
    require(logical and all(logical), 'Reset targets empty')
    table = {}
    for row in binding_doc['bindings']:
        a, b = row['logical'], row['physical']
        require(a not in table and b not in table.values(), 'Ambiguous/duplicate reset binding')
        cell, port = b.rsplit('/', 1)
        require(cell in graph['primitives'] and port in graph['primitives'][cell]['ports'] and
                b in graph['pin_net'], 'Reset target absent/unconnected in actual routed map')
        table[a] = b
    require(set(table) == logical, 'Actual routed reset binding coverage incomplete')
    return set(table.values())


def actual_endpoint_gate(endpoint_doc, graph):
    """Require the build03 endpoint audit, rather than trusting passed=true."""
    require(endpoint_doc.get('status') == 'PASS' and endpoint_doc.get('independent_registers') == 60,
            'Actual independent60 endpoint audit missing')
    rows = endpoint_doc.get('rows')
    require(isinstance(rows, list) and len(rows) == 60 and
            all(r.get('all_proven_checks_passed') is True for r in rows),
            'Actual endpoint rows/INIT/GRS/DCLK/reset checks incomplete')
    cells = [r.get('cell') for r in rows]
    require(len(set(cells)) == 60 and all(c in graph['primitives'] for c in cells),
            'Endpoint audit cells are not the current routed graph')
    return set(cells)


def routed_target_audit(path, name, expected, fields):
    doc = load(path)
    require(doc.get('passed') is True, name + ' actual audit did not pass')
    details = doc.get('details')
    require(isinstance(details, dict), name + ' details missing')
    require(set(details) == set(fields), name + ' corner/check schema incomplete')
    for key in fields:
        row = details[key]
        require(row.get('covered') == expected and not row.get('missing') and
                not row.get('unexpected') and nonnegative(row.get('worst_slack')),
                name + ' incomplete actual coverage: ' + key)
    return doc


def raw_target_details(path, expected, kinds, pair_mode=False):
    result = {c + '_' + k: {'actual': set(), 'worst': None}
              for c in ('Slow', 'Fast') for k in kinds}
    count = 0
    for row in records(path):
        count += 1
        key = str(row['corner']) + '_' + str(row['check'])
        require(key in result and nonnegative(row['slack']) and not row['exception'],
                'Unexpected/excepted/negative targeted raw timing record')
        actual = (row['start'], row['end']) if pair_mode else row['end']
        require(actual in expected, 'Target raw record not bound to current routed endpoints/pairs')
        if not pair_mode and kinds == ('Minimum Pulse Width',):
            require(row['start'] == row['end'], 'Unsupported primitive pulse width start/end form')
        item = result[key]
        item['actual'].add(actual)
        item['worst'] = row['slack'] if item['worst'] is None else min(item['worst'], row['slack'])
    require(count > 0, 'Empty fresh targeted report')
    for key, item in result.items():
        require(item['actual'] == expected and item['worst'] is not None,
                'Incomplete two-corner all-target coverage: ' + key)
    return result


def verify(manifest_path):
    return verify_document(load(manifest_path))


def verify_document(m):
    require(m.get('contract') == 'validatedDelivery/v1' and m.get('status') == 'validated',
            'Reviewed validatedDelivery/v1 required; prepare template is not delivery')
    build = delivery_build(m)
    require(m.get('mode') == 'sram' and m.get('target') == 'PG2L100H', 'SRAM PG2L100H only')
    require(m.get('programming_performed') is False and m.get('board_verified') is False,
            'Pre-program delivery state invalid')
    bit = bound(m['bitstream'])
    require(bit.is_relative_to(build) and bit.suffix.lower() in ('.bit', '.sbit'),
            'Bit must belong to new timing build')
    require(bound(m['programmer']) == VENDOR.resolve(), 'Unexpected programmer')
    artifacts = {name: bound(entry) for name, entry in m['artifacts'].items()}
    needed = {'route', 'sta_raw', 'sta_summary', 'mailbox_raw', 'mailbox_audit',
              'reset_raw', 'reset_audit', 'io_audit', 'hsst', 'motion', 'routed_dump',
              'routed_verilog', 'coverage', 'protected_before', 'protected_after',
               'inputs_before', 'inputs_after', 'mapping', 'reset_targets', 'reset_bindings',
                'routed_graph', 'routed_endpoint_audit', 'sync_pairs',
               'reset_mpw_raw', 'reset_mpw_audit', 'sync_later_raw',
               'sync_later_audit', 'acceptance'}
    require(needed <= artifacts.keys(), 'Required evidence artifact missing')
    for target in ('mailbox', 'reset', 'reset_mpw', 'sync_later'):
        groups = m.get('target_logs', {}).get(target, {})
        for role in ('shell', 'run'):
            names = groups.get(role, [])
            require(isinstance(names, list) and names and all(n in artifacts for n in names),
                    'Bound target shell/run logs required: ' + target + '/' + role)
            for name in names:
                target_log_check(artifacts[name])
    acceptance = load(artifacts['acceptance'])
    # New reviewed binding wrapper; all underlying evidence uses actual schemas below.
    require(acceptance.get('contract') == 'validatedDeliveryAcceptance/v1' and
            acceptance.get('accepted') is True and acceptance.get('reviewer') and
             acceptance.get('candidate_id') == m['candidate_id'] and
             acceptance.get('bit_sha256') == m['bitstream']['sha256'] and
             acceptance.get('bit_bytes') == m['bitstream']['bytes'] and
             acceptance.get('bit_path') == str(bit) and acceptance.get('build_root') == str(build) and
             acceptance.get('programmer_sha256') == m['programmer']['sha256'] and
            acceptance.get('artifact_sha256') == {k: v['sha256'] for k, v in m['artifacts'].items() if k != 'acceptance'},
            'Independent bit/build/evidence binding acceptance missing')
    audit_sources = {k: bound(v) for k, v in m['audit_sources'].items()}
    require({'audit_fixed', 'verify_routed11', 'summarize', 'raw_audit', 'consumer', 'routed_connection',
             'endpoint_recompute', *ENDPOINT_ROLES} <= audit_sources.keys() and
             audit_sources['consumer'] == Path(__file__).resolve() and
              audit_sources['routed_connection'] == HERE / 'routed_connection.py' and
              audit_sources['endpoint_recompute'] == HERE / 'endpoint_recompute.py' and
            acceptance.get('audit_sha256') == {k: sha(v) for k, v in audit_sources.items()},
            'Concrete reviewed audit source hashes missing')
    raw = raw_summaries(artifacts['sta_raw'])
    sta = load(artifacts['sta_summary'])
    require(sta['report_sha256'] == sha(artifacts['sta_raw']) and sta['routed_db_sha256'] == sha(artifacts['route']),
            'STA/route binding mismatch')
    groups = sta['all_corner_summaries']
    require(len(groups) == 10 and {(g['section'], g['corner']) for g in groups} == {(k, c) for k in KINDS for c in ('Slow', 'Fast')} and
             all(g['rows'] and g['sum_failing_endpoints'] == 0 and all(nonnegative(r['worst_slack_ns']) and r['failing_endpoints'] == 0 and r['total_negative_slack_ns'] == 0 and r['total_endpoints'] > 0 for r in g['rows']) for g in groups), 'STA summary incomplete')
    require([{'section': g['section'], 'corner': g['corner'], 'rows':
            [{k: r[k] for k in ('worst_slack_ns', 'total_negative_slack_ns', 'failing_endpoints', 'total_endpoints')} for r in g['rows']]} for g in groups] == raw['groups'], 'Saved/raw summary rows mismatch')
    require(sta['negative_slack_paths'] == 0, 'Summary negative paths present')
    require(type(sta['unscored_io_paths']) is int and sta['unscored_io_paths'] >= 0 and
            sta['unscored_io_paths'] == raw['unscored_io_paths'] and
            m['limitations']['unscored_io_paths'] == sta['unscored_io_paths'] and
            m['limitations']['unscored_io_note'] and acceptance.get('limitations') == m['limitations'],
            'Unscored IO limitation must be explicitly recorded/reviewed')
    mapping = load(artifacts['mapping'])
    graph = load(artifacts['routed_graph'])
    coverage = load(artifacts['coverage'])
    require(coverage.get('route_sha256') == sha(artifacts['route']) and
            coverage.get('graph_sha256') == sha(artifacts['routed_graph']),
            'Current routed DB/graph coverage binding missing or stale')
    actual_endpoint_gate(load(artifacts['routed_endpoint_audit']), graph)
    endpoint_proof = recompute(graph, audit_sources, build / 'runtime', require, sha)
    saved_endpoint = load(artifacts['routed_endpoint_audit'])
    require(saved_endpoint == endpoint_proof, 'Saved endpoint audit differs from current routed recomputation')
    pairs = phase_pairs(mapping, coverage, graph)
    expected = m['mailbox_expected_pairs']
    require(type(expected) is int and expected > 0 and len(pairs) == expected, 'Actual mailbox mapping count mismatch')
    require(expected == 1320 or (m.get('mapping_difference_reason') and acceptance.get('mapping_difference_accepted') is True),
            'Non-1320 mapping requires explicit manifest rationale and reviewed acceptance')
    mail = audit_metadata(artifacts['mailbox_audit'])
    require(mail.get('passed') is True and set(mail['details']) == {'Slow', 'Fast'}, 'Mailbox audit missing')
    corner_rows = {c: {'pairs': set(), 'worst': None, 'count': 0} for c in ('Slow', 'Fast')}
    for r in records(artifacts['mailbox_raw']):
        if r['exception'] and 'MaxDelay Path' in r['exception']:
            require(r['corner'] in corner_rows, 'Mailbox path corner missing')
            require(nonnegative(r['slack']), 'Mailbox raw slack missing/negative')
            item = corner_rows[r['corner']]
            item['pairs'].add((r['start'], r['end']))
            item['count'] += 1
            item['worst'] = r['slack'] if item['worst'] is None else min(item['worst'], r['slack'])
    for corner in ('Slow', 'Fast'):
        subset = corner_rows[corner]
        require(subset['pairs'] == pairs, 'Mailbox raw pair/slack coverage missing: ' + corner)
        detail = mail['details'][corner]
        require(detail['covered'] == expected and not detail['missing'] and not detail['unexpected'] and
             detail['worst_slack'] == subset['worst'], 'Mailbox saved detail mismatch')
    targets = phase_resets(load(artifacts['reset_targets']), load(artifacts['reset_bindings']), graph)
    actual_resets = [r for r in endpoint_proof['rows'] if r['chain'] in {'cr', 'hr', 'reset_pipe'}]
    actual_binding = [{'logical': r['logical'], 'physical': r['reset'], 'clock_physical': r['CLK']}
                      for r in actual_resets]
    require(len(targets) == 32 and targets == {r['reset'] for r in actual_resets} and
            load(artifacts['reset_targets'])['ends'] == sorted(r['logical'] for r in actual_resets) and
            load(artifacts['reset_bindings'])['bindings'] == actual_binding,
            'Reset32/DCLK actual routed binding mismatch')
    reset = audit_metadata(artifacts['reset_audit'])
    raw_target_details(artifacts['reset_raw'], targets, ('Recovery', 'Removal'))
    require(reset.get('passed') is True and set(reset['details']) == {c + '_' + k for c in ('Slow', 'Fast') for k in ('Recovery', 'Removal')}, 'Reset audit missing')
    reset_rows = {c + '_' + k: {'ends': set(), 'worst': None} for c in ('Slow', 'Fast') for k in ('Recovery', 'Removal')}
    for r in records(artifacts['reset_raw']):
        for kind in ('Recovery', 'Removal'):
            if r['check'] == kind:
                require(r['corner'] in ('Slow', 'Fast'), 'Reset path corner missing')
                require(nonnegative(r['slack']), 'Reset raw slack missing/negative')
                item = reset_rows[r['corner'] + '_' + kind]
                item['ends'].add(r['end'])
                item['worst'] = r['slack'] if item['worst'] is None else min(item['worst'], r['slack'])
    for corner in ('Slow', 'Fast'):
        for kind in ('Recovery', 'Removal'):
            subset = reset_rows[corner + '_' + kind]
            require(targets == subset['ends'] and subset['worst'] is not None, 'Reset target coverage/slack missing')
            d = reset['details'][corner + '_' + kind]
            require(d['covered'] == len(targets) and not d['missing'] and nonnegative(d['worst_slack']) and d['worst_slack'] == subset['worst'], 'Reset saved detail mismatch')
    clocks = {r['clock_physical'] for r in load(artifacts['reset_bindings'])['bindings']}
    require(len(clocks) > 0, 'Actual reset clock binding missing')
    for name in ('reset_raw', 'reset_mpw_raw', 'sync_later_raw', 'routed_endpoint_audit', 'sync_pairs'):
        require(artifacts[name].is_relative_to(build) and
                artifacts[name].stat().st_mtime >= artifacts['route'].stat().st_mtime,
                'Target report/binding is outside current build or predates routed DB: ' + name)
    mpw_raw = raw_target_details(artifacts['reset_mpw_raw'], clocks, ('Minimum Pulse Width',))
    mpw_audit = routed_target_audit(artifacts['reset_mpw_audit'], 'Reset MPW', len(clocks), ('Slow', 'Fast'))
    require(mpw_audit.get('clock_targets') == sorted(clocks), 'Reset MPW clock targets mismatch')
    for corner in ('Slow', 'Fast'):
        require(mpw_audit['details'][corner]['worst_slack'] == mpw_raw[corner + '_Minimum Pulse Width']['worst'],
                'Reset MPW saved/raw worst slack mismatch')
    sync_doc = load(artifacts['sync_pairs'])
    sync_pairs = {tuple(r['physical']) for r in sync_doc['bindings']}
    require(len(sync_pairs) == 16 and all(len(p) == 2 for p in sync_pairs),
            'Actual 16 same-clock sync bindings required')
    require(sync_doc['bindings'] == [{'logical': [r['launch_CLK'], r['capture_D']],
                                      'physical': [r['launch_CLK'], r['capture_D']]}
                                     for r in endpoint_proof['ordinary_pairs']],
            'Sync16 actual Q/D/clock/reset graph binding mismatch')
    sync_audit = load(artifacts['sync_later_audit'])
    require(sync_audit.get('passed') is True and set(sync_audit.get('details', {})) ==
            {c + '_' + k for c in ('Slow', 'Fast') for k in ('Setup', 'Hold')},
            'Sync later audit missing four actual corner/check cells')
    for key, detail in sync_audit['details'].items():
        require(detail.get('covered') == 16 and not detail.get('missing') and
                not detail.get('unexpected') and nonnegative(detail.get('worst_slack')),
                'Sync later pair coverage/slack missing: ' + key)
    sync_raw = raw_target_details(artifacts['sync_later_raw'], sync_pairs, ('Setup', 'Hold'), True)
    for key, item in sync_raw.items():
        require(sync_audit['details'][key]['worst_slack'] == item['worst'],
                'Sync later saved/raw worst slack mismatch: ' + key)
    io = load(artifacts['io_audit'])
    require(io.get('passed') is True and io.get('pins') == 112 and io.get('matches_frozen_v7') is True, '112 PCB IO gate missing')
    phy = load(artifacts['hsst'])
    require(phy.get('sites_identical_to_baseline') is True and phy.get('dedicated_connections_identical_to_baseline') is True and
            phy.get('hsst_sites') and phy.get('dedicated_connections') and phy['dump_sha256'] == sha(artifacts['routed_dump']), 'HSST gate missing')
    motion = load(artifacts['motion'])
    require(motion['dump_sha256'] == sha(artifacts['routed_dump']) and motion['verilog_sha256'] == sha(artifacts['routed_verilog']) and
            motion['logical_total_bits'] == 614400 and motion['routed_history_DRM36K_total'] == 32 and motion['connect_evidence_blocks'] > 0, 'Motion route binding/32 DRM missing')
    histories = motion['histories']
    require(len(histories) == 4 and {h['instance'] for h in histories} == {c + '/u_motion_tap/u_detector' for c in ('ov5640_top', 'cam2_ov5640_top', 'cam3_ov5640_top', 'cam4_ov5640_top')} and
            all(h['logical_depth'] == 19200 and h['logical_width'] == 8 and h['mode'] == 'read_first' and h['routed_DRM36K_instances'] == 8 and len(h['cells']) == 8 and all(c['physical_placement'] and c['definition'] and c['parameters']['CP_WRITE_MODE_A_0'] == '"READ_BEFORE_WRITE"' for c in h['cells']) for h in histories), 'Four motion history geometry/mode gate missing')
    for label in ('protected', 'inputs'):
        before = load(artifacts[label + '_before'])
        require(before and before == load(artifacts[label + '_after']), 'Protection/input inventory drift')
        for path, digest in before.items():
            p = Path(path)
            if not p.is_absolute():
                require(label == 'inputs', 'Protected inventory must use absolute paths')
                p = build / p
            require(sha(p.resolve(strict=True)) == digest, 'Protected/input live hash drift')
    return m, bit


def verify_owner_preflight(pre, manifest_digest, bit_digest):
    require(pre.get('contract') == 'boardOwnerPreflight/v1' and pre.get('accepted') is True and pre.get('reviewer') and
            pre.get('delivery_manifest_sha256') == manifest_digest and pre.get('bit_sha256') == bit_digest and
            all(pre.get(k) is True for k in ('identity_matches_baseline', 'exclusive_owner', 'driver_ready')) and
            type(pre.get('captured_unix')) in (int, float) and
            0 <= time.time() - pre['captured_unix'] <= 300, 'Fresh owner/boot/driver evidence not accepted')
    files = {k: bound(v) for k, v in pre['artifacts'].items()}
    require({'identity', 'boot_current', 'driver_current', 'ownership'} <= files.keys(), 'Owner raw evidence incomplete')
    if pre.get('boundary_kind') == 'proven_dma_idle':
        require(pre.get('dma_quiesced') is True and 'dma_idle' in files, 'Real DMA idle evidence required')
    elif pre.get('boundary_kind') == 'cold_reset_rebuilt':
        require(pre.get('cold_reset_rebuilt') is True and
                {'cold_reset_action', 'boot_before', 'boot_after', 'pcie_reenumeration', 'driver_rebind'} <= files.keys(),
                'Cold reset rebuilt safety boundary evidence missing')
        require(files['boot_before'].read_bytes().strip() != files['boot_after'].read_bytes().strip() and
                files['boot_after'].read_bytes().strip() == files['boot_current'].read_bytes().strip(),
                'Cold reset boot identity not rebuilt/current')
    else:
        raise ValueError('DMA safety boundary must be proven idle or real cold reset rebuilt')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=HERE / 'delivery_manifest.json')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--execute', action='store_true')
    parser.add_argument('--owner-preflight', type=Path)
    parser.add_argument('--timeout', type=int, default=300)
    args = parser.parse_args()
    directory = HERE / ('candidate_run_' + time.strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:8])
    directory.mkdir()
    receipt = {'status': 'blocked', 'target': 'PG2L100H', 'mode': 'sram', 'check_only': not args.execute,
               'board_operation_verified': False, 'stages': {}, 'retained_directory': str(directory)}
    try:
        require(1 <= args.timeout <= 1800, 'Timeout outside 1..1800')
        manifest_path = args.manifest.resolve(strict=True)
        manifest_digest = sha(manifest_path)
        m, bit = verify(manifest_path)
        require(sha(manifest_path) == manifest_digest, 'Manifest changed during verification')
        receipt.update(bit=str(bit), bit_sha256=m['bitstream']['sha256'], bit_bytes=m['bitstream']['bytes'],
                       delivery_manifest_sha256=manifest_digest, programmer_sha256=sha(VENDOR), candidate_id=m['candidate_id'],
                       limitations=m['limitations'])
        (directory / 'validated_delivery.json').write_bytes(manifest_path.read_bytes())
        if not args.execute:
            receipt['status'] = 'validated_only'
        else:
            require(args.owner_preflight is not None, 'Execute requires current owner/boot/driver preflight evidence')
            pre = load(args.owner_preflight)
            verify_owner_preflight(pre, manifest_digest, m['bitstream']['sha256'])
            receipt['owner_preflight_sha256'] = sha(args.owner_preflight)
            # Repeat all local gates immediately before loading vendor code.
            verify(manifest_path)
            require(sha(manifest_path) == manifest_digest, 'Manifest changed before execute')
            spec = importlib.util.spec_from_file_location('candidate_vendor', VENDOR)
            vendor = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(vendor)
            receipt['status'] = 'started'
            vendor.run(SimpleNamespace(mode='sram', timeout=args.timeout), receipt, directory, bit, m['bitstream']['sha256'])
            require(receipt.get('status') == 'success' and receipt.get('stages') and all(v is True for v in receipt['stages'].values()), 'Vendor receipt incomplete')
    except Exception as error:
        receipt['status'] = 'failed' if receipt['status'] == 'started' else 'blocked'
        receipt['error_type'] = type(error).__name__
        # Do not print arbitrary evidence contents or credentials.
        receipt['error'] = str(error) if isinstance(error, (ValueError, FileNotFoundError)) else 'Evidence/schema/vendor error; inspect retained artifacts'
    finally:
        (directory / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0 if receipt['status'] in ('validated_only', 'success') else 1


if __name__ == '__main__':
    sys.exit(main())
