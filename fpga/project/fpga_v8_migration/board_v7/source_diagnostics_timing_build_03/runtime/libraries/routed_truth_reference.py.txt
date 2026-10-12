"""Read-only build01 graph audit. Writes only beside this script; no PDS imports."""
import collections
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
BUILD = OUT.parent / 'source_diagnostics_timing_build_01'
E = BUILD / 'evidence'

def load(p):
    return json.loads(p.read_bytes())

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()

def descendants(n, tag):
    if isinstance(n, list):
        if n and n[0] == tag:
            yield n
        for x in n:
            yield from descendants(x, tag)

g = load(E / 'routed/analysis/graph.json')
sg = load(E / 'actual_post_constraints/analysis/graph.json')
m = load(E / 'actual_post_constraints/analysis/manifest.json')
c = load(E / 'actual_post_constraints/analysis/classification.json')
pr, pn, aliases = g['primitives'], g['pin_net'], g['net_aliases']
drivers = {n: [p for p in pp if pr[p.rsplit('/', 1)[0]]['ports'][p.rsplit('/', 1)[1]]['direction'] == 'OUTPUT'] for n, pp in g['netpins'].items()}
def canon(a):
    return a.replace('/@', '/').lstrip('/')
an = collections.defaultdict(set)
for n, aa in aliases.items():
    for a in aa:
        an[canon(a)].add(n)

def net_for(logical):
    candidates = set(an.get(canon(logical), []))
    sn = sg['pin_net'].get(logical)
    for a in sg['net_aliases'].get(sn, []):
        candidates.update(an.get(canon(a), []))
    assert len(candidates) == 1, ('alias binding', logical, sorted(candidates))
    return next(iter(candidates))

def param(cell, key):
    r = pr[cell]
    ps = {x[1]: x for x in r['default_parameters']}
    for x in r['parameters']:
        for z in descendants(x, 'PARAMETER'):
            ps[z[1]] = z
    v = ps[key]
    bs = list(descendants(v, 'B'))
    if bs:
        return int(bs[0][2].strip('"'), 2)
    return next(descendants(v, 'STRING'))[1].strip('"')

def lut_expr(cell, names, init, ov, memo, active):
    args = [symbolic(pn[cell + '/' + x], ov, memo, active) if cell + '/' + x in pn else ('var', 'UNCONNECTED/' + cell + '/' + x) for x in names]
    remaining = [a for a in args if a[0] != 'const']
    table = []
    for mask in range(1 << len(remaining)):
        pos = index = 0
        for j, a in enumerate(args):
            if a[0] == 'const':
                x = a[1]
            else:
                x = (mask >> pos) & 1
                pos += 1
            index |= x << j
        table.append((init >> index) & 1)
    used = [j for j in range(len(remaining)) if any(table[z] != table[z ^ (1 << j)] for z in range(len(table)))]
    table = [table[sum(((z >> i) & 1) << j for i, j in enumerate(used))] for z in range(1 << len(used))]
    remaining = [remaining[j] for j in used]
    if len(set(table)) == 1:
        return ('const', table[0])
    for j, a in enumerate(remaining):
        if all(x == ((z >> j) & 1) for z, x in enumerate(table)):
            return a
    return ('lut', sum(x << j for j, x in enumerate(table)), remaining)

visited = set()
def output_expr(p, ov, memo, active, combinational=False):
    cell, port = p.rsplit('/', 1)
    r = pr[cell]
    t = r['type']
    visited.add(p)
    if port in ('Q', 'Q0', 'CR0', 'L5Q', 'L6Q', 'L8Q') and not combinational:
        return ('var', p)
    if t == 'gopCLKROUTE' and port == 'CR':
        return symbolic(pn[cell + '/M'], ov, memo, active)
    if t.startswith('gopIOL'):
        return ('var', p)
    if t in ('GTP_GND', 'GND', 'gopGND'):
        return ('const', 0)
    if t in ('GTP_VCC', 'VCC', 'gopVCC'):
        return ('const', 1)
    if 'LUT7' in t:
        def branch(k):
            return lut_expr(cell, [k + str(i) for i in range(6)], param(cell, 'INIT' + k), ov, memo, active)
        if port == 'L6A': return branch('A')
        if port == 'L6B': return branch('B')
        assert port == 'L7', (p, t)
        sel = symbolic(pn[cell + '/M'], ov, memo, active)
        if sel[0] == 'const': return branch('B' if sel[1] else 'A')
        return ('mux', sel, branch('A'), branch('B'))
    if 'LUT6' in t:
        assert port in ('L5', 'L6', 'L5Q', 'L6Q'), (p, t)
        count = 5 if port.startswith('L5') else 6
        return lut_expr(cell, ['I' + str(i) for i in range(count)], param(cell, 'INIT'), ov, memo, active)
    raise ValueError(('unsupported', p, t))

def symbolic(net, ov, memo, active):
    if net in ov: return ('const', ov[net])
    if net in memo: return memo[net]
    assert net not in active, ('cycle', net)
    literals = {a.rsplit('$constant_', 1)[1] for a in aliases[net] if '$constant_' in a}
    if literals == {'y'}:
        return ('var', 'DONTCARE/' + net)
    const = {int(a) for a in literals}
    if const:
        assert len(const) == 1
        return ('const', next(iter(const)))
    outs = drivers.get(net, [])
    assert len(outs) == 1, ('drivers', net, outs)
    result = output_expr(outs[0], ov, memo, active | {net})
    memo[net] = result
    return result

def support(e):
    if e[0] == 'var': return {e[1]}
    if e[0] == 'const': return set()
    if e[0] == 'lut': return set().union(*(support(x) for x in e[2]))
    if e[0] == 'mux': return set().union(*(support(x) for x in e[1:]))
    raise ValueError(e)

def evaluate(e, env):
    if e[0] == 'const': return e[1]
    if e[0] == 'var': return env[e[1]]
    if e[0] == 'lut': return (e[1] >> sum(evaluate(x, env) << i for i, x in enumerate(e[2]))) & 1
    if e[0] == 'mux': return evaluate(e[3] if evaluate(e[1], env) else e[2], env)
    raise ValueError(e)

def trace_driver(net):
    steps, seen = [], set()
    while True:
        assert net not in seen, ('buffer cycle', net)
        seen.add(net)
        outs = drivers.get(net, [])
        assert len(outs) == 1, ('drivers', net, outs)
        p = outs[0]
        cell, port = p.rsplit('/', 1)
        steps.append({'net': net, 'driver': p, 'type': pr[cell]['type']})
        if pr[cell]['type'] == 'gopCLKROUTE' and port == 'CR':
            assert [param(cell, 'INIT' + k) for k in 'ABCD'] == [0, (1 << 64) - 1, 0, (1 << 64) - 1], ('non-identity CLKROUTE', cell)
            net = pn[cell + '/M']
        else:
            return p, steps

rows, errors, pairs = [], [], {}
for cam in range(4):
    prefix = f'source_diagnostics/cameras[{cam}].source/'
    for word in range(16):
        ov = {net_for(prefix + 'snapshot_valid/Q'): 1}
        for j in range(4):
            ov[net_for('source_diagnostics/word_sel[' + str(j) + ']/Q')] = (word >> j) & 1
        memo = {}
        for bit in range(32):
            logical = word * 32 + bit
            expected = m['resolved'][cam * 512 + logical]['mapping']
            try:
                readnet = net_for(prefix + f'read_data[{bit}]/Q')
                readq = drivers[readnet]
                assert len(readq) == 1
                expr = output_expr(readq[0], ov, memo, set(), combinational=True)
                ss = sorted(support(expr))
                assert len(ss) <= 12, ss
                values = [evaluate(expr, {s: (mask >> i) & 1 for i, s in enumerate(ss)}) for mask in range(1 << len(ss))]
                identity = next((s for i, s in enumerate(ss) if all(v == ((mask >> i) & 1) for mask, v in enumerate(values))), None)
                kind = 'constant_zero' if not any(values) else 'register'
                if kind == 'register': assert identity, ('not identity', ss, values)
                assert kind == expected['kind'], (kind, expected)
                row = {'camera': cam, 'logical_bit': logical, 'word': word, 'bit': bit, 'kind': kind, 'read_Q': readq[0], 'support': ss, 'assignments': len(values)}
                if identity:
                    assert pn[identity] == net_for(expected['capture_q']), ('wrong capture', identity, expected)
                    cap = identity.rsplit('/', 1)[0]
                    assert identity.endswith('/Q') and cap + '/D' in pn, ('packed capture requires adapter', identity)
                    launch, steps = trace_driver(pn[cap + '/D'])
                    assert pn[launch] == net_for(expected['launch_Q']), ('wrong launch', launch, expected)
                    row.update(capture_Q=identity, capture_D=cap + '/D', launch_Q=launch, launch_CLK=launch.rsplit('/', 1)[0] + '/CLK', driver_trace=steps)
                    pairs[(launch, cap + '/D')] = row
                rows.append(row)
            except Exception as exc:
                errors.append({'camera': cam, 'logical_bit': logical, 'error': str(exc)})
    print('camera', cam, 'resolved', len(rows), 'errors', len(errors), flush=True)

chain_rows = []
for x in c['chains']:
    cell = x['cell']
    try:
        try:
            qnet = net_for(cell + '/Q')
            q = drivers[qnet]
        except AssertionError:
            # Stage zero is internal to SRL2: Q0 is not exported to a fabric net.
            physical = cell + '/opit_0_srl'
            assert pr[physical]['type'].startswith('gopSRL2')
            assert physical + '/Q0' not in pn
            q = [physical + '/Q0']
        assert len(q) == 1
        chain_rows.append({**{k: x[k] for k in ('camera', 'signal', 'stage')}, 'logical': cell, 'physical_Q': q[0], 'type': pr[q[0].rsplit('/', 1)[0]]['type'], 'internal': q[0] not in pn})
    except Exception as exc:
        chain_rows.append({'logical': cell, 'error': str(exc)})

reset_rows = []
for x in c['reset']:
    cell = x['actual_Q'][0].rsplit('/', 1)[0]
    try:
        try:
            n = net_for(cell + '/Q')
            q = drivers[n][0]
            physical = q.rsplit('/', 1)[0]
        except AssertionError:
            physical = cell + '/opit_0_srl'
            assert pr[physical]['type'].startswith('gopSRL2')
        reset_rows.append({'logical': cell, 'physical_RS': physical + '/RS', 'type': pr[physical]['type'], 'connected': physical + '/RS' in pn, 'parameters': pr[physical]['default_parameters']})
    except Exception as exc:
        reset_rows.append({'logical': cell, 'error': str(exc)})

chain_index = {x['logical']: x for x in chain_rows}
sync_pairs = []
for x in c['ordinary_pairs']:
    a, b = x['launch_CLK'].rsplit('/', 1)[0], x['capture_D'].rsplit('/', 1)[0]
    ar, br = chain_index[a], chain_index[b]
    aq, bq = ar['physical_Q'], br['physical_Q']
    ac, bc = aq.rsplit('/', 1)[0], bq.rsplit('/', 1)[0]
    if ar['internal']:
        assert ac == bc and bq.endswith('/CR0') and aq.endswith('/Q0')
        sync_pairs.append({'logical': [a, b], 'physical': [aq, bq], 'topology': 'internal_SRL2_Q0_to_CR0', 'CLK': ac + '/CLK'})
    else:
        driver, steps = trace_driver(pn[bc + '/D'])
        assert driver == aq, (a, b, driver, aq)
        sync_pairs.append({'logical': [a, b], 'physical': [ac + '/CLK', bc + '/D'], 'topology': 'external_Q_to_D', 'trace': steps})

raw = (E / 'routed/synthesis_export/synthesis_dump.txt').read_bytes()
raw_counts = {term: raw.count(term.encode()) for term in ('cam_href_d', 'cmos_frame_href_r', 'hsync_sync', 'keepbuf', 'CLKROUTE_291')}
cleanup = []
for f in (E / 'dev_map.log', E / 'pnr.log'):
    for i, line in enumerate(f.read_bytes().splitlines(), 1):
        if b'Public-4008' in line and any(t in line for t in (b'cam_href_d', b'cmos_frame_href_r', b'hsync_sync')):
            cleanup.append({'path': str(f), 'line': i, 'text': line.decode('gbk', errors='replace')})
clones = [k for k in pr if k.startswith('cam2_ov5640_top/ov5640/cmos_frame_valid_r/')]
clone_evidence = [{'cell': k, 'parameters': pr[k]['default_parameters'], 'nets': {port: pn.get(k + '/' + port) for port in ('Q', 'D', 'CLK', 'RS', 'CE')}} for k in clones]
assert len(clones) == 2 and clone_evidence[0]['parameters'] == clone_evidence[1]['parameters']
assert all(clone_evidence[0]['nets'][p] == clone_evidence[1]['nets'][p] for p in ('D', 'CLK', 'RS', 'CE'))
files = [E / 'routed/analysis/graph.json', E / 'routed/synthesis_export/synthesis_dump.txt', E / 'routed/synthesis_export/synthesis_dump.v', E / 'actual_post_constraints/analysis/manifest.json', E / 'actual_post_constraints/analysis/graph.json', E / 'coverageproof_routed.json', E / 'pnr.log', E / 'dev_map.log', BUILD / 'routed_acceptance.py', BUILD / 'analysis_tools/parse_objects.py']
result = {'inputs': [{'path': str(p), 'sha256': sha(p), 'bytes': p.stat().st_size} for p in files], 'old_errors': load(E / 'coverageproof_routed.json')['errors'], 'resolved': rows, 'errors': errors, 'kind_counts': dict(collections.Counter(x['kind'] for x in rows)), 'unique_pairs': len(pairs), 'buffered_pairs': [x for x in pairs.values() if len(x['driver_trace']) > 1], 'visited_outputs': sorted(visited), 'chains': chain_rows, 'resets': reset_rows, 'reset_unique_RS': len({x['physical_RS'] for x in reset_rows if 'physical_RS' in x}), 'sta_status': 'UNKNOWN: original routed_binding early return precedes target/global STA'}
(OUT / 'review.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
result.update(sync_pairs=sync_pairs, raw_token_counts=raw_counts, cleanup_warnings=cleanup, valid_clone_evidence=clone_evidence, script_sha256=sha(Path(__file__)))
(OUT / 'review.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
print(json.dumps({k: result[k] for k in ('kind_counts', 'unique_pairs', 'reset_unique_RS')}, indent=2))
print('errors', errors[:5], 'chain errors', [x for x in chain_rows if 'error' in x], 'reset errors', [x for x in reset_rows if 'error' in x])
