"""Read existing artifacts only; write owned per-instance evidence, no vendor calls."""
from pathlib import Path
import collections
import hashlib
import json
import re
import sys
sys.dont_write_bytecode = True
from mapping import verify_counter_mapping

OWN = Path(__file__).resolve().parent
HERE = OWN.parent

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def synthesized(run):
    net = run / 'work/synthesize/top_syn.vm'
    cs = net.parent / 'top_controlsets.txt'
    proof = verify_counter_mapping(net, cs)
    raw = net.read_bytes()
    modules = list(re.finditer(rb'\nmodule [\s\S]+?\nendmodule', raw))
    counters = {}
    for m in modules:
        name = re.match(rb'\nmodule (\S+)', m.group()).group(1)
        if not name.startswith(b'pll56_source_drop_counter'):
            continue
        cells = []
        for c in re.finditer(rb'\n    (GTP_DFF\S+) [^;]+;', m.group()):
            ports = dict((k.decode(), v.strip().decode()) for k, v in
                         re.findall(rb'\.(Q|D|CLK|C|CE)\s*\(([^)]+)\)', c.group()))
            cells.append(dict(primitive=c.group(1).decode(), ports=ports))
        assert len(cells) == 32
        assert {c['ports']['Q'] for c in cells} == {'value[%d]' % i for i in range(32)}
        counters[name.decode()] = cells
    instances = []
    for m in modules:
        name = re.match(rb'\nmodule (\S+)', m.group()).group(1)
        for c in re.finditer(rb'\n    (pll56_source_drop_counter\S*) u_src_drop [^;]+;', m.group()):
            cam = re.search(rb'\\((?:cam[234]_)?ov5640_top)/ov5640/', m.group())
            assert cam
            instances.append(dict(camera=cam.group(1).decode(), parent_module=name.decode(),
                                  counter_module=c.group(1).decode(), instance=c.group().decode()))
    assert len(instances) == 4
    assert len({i['camera'] for i in instances}) == 4
    assert {i['counter_module'] for i in instances} == set(counters)
    return dict(run=str(run), gate=proof, instances=instances, per_module_cells=counters)

def routed(path):
    b = path.read_bytes()
    cells = {}
    starts = list(re.finditer(rb'(?m)^    \((CELL|OPERATOR) (\S+)', b))
    for i, m in enumerate(starts):
        if m.group(1) != b'CELL':
            continue
        c = b[m.start():starts[i+1].start() if i+1 < len(starts) else b.find(b'\n  )', m.end())]
        cells[m.group(2)] = dict((k.decode(), v.decode()) for k, v in re.findall(
            rb'\(PARAMETER (\S+) \(DATATYPE STRING\) \(STRING "([^"]+)"\)', c))
    instances = list(re.finditer(rb'\(INSTANCE (\\[^\s]*u_src_drop/bits\[(\d+)\]\.ff/[^\s]+)\s+\(VIEWREF OPER \(CELLREF (\S+)', b))
    assert len(instances) == 128
    records = {m.group(1): dict(instance=m.group(1).decode(), bit=int(m.group(2)),
                              cell=m.group(3).decode(), parameters=cells[m.group(3)], pins={})
               for m in instances}
    net_starts = list(re.finditer(rb'(?m)^          \(NET (\S+)', b))
    for i, m in enumerate(net_starts):
        block = b[m.start():net_starts[i+1].start() if i+1 < len(net_starts) else len(b)]
        for pin, instance in re.findall(rb'\(PORTREF (\S+) \(INSTREF (\S+)\s*\)\)', block):
            if instance in records:
                records[instance]['pins'].setdefault(pin.decode(), []).append(m.group(1).decode())
    by_camera = collections.defaultdict(list)
    for inst, r in records.items():
        cam = inst.split(b'/')[0].decode().lstrip('\\')
        by_camera[cam].append(r['bit'])
        assert r['parameters']['LCE_EN'] == 'FALSE', r
        assert r['parameters']['RS_MODE'] == 'ASYNC', r
        assert r['parameters']['LRS_EN'] == 'TRUE', r
        assert 'CE' not in r['pins'], r
        assert len(r['pins'].get('CLK', [])) == 1, r
        assert len(r['pins'].get('RS', [])) == 1, r
        assert len(r['pins'].get('Q', []) + r['pins'].get('L6Q', [])) == 1, r
    assert len(by_camera) == 4
    assert all(sorted(bits) == list(range(32)) for bits in by_camera.values())
    return dict(status='PASS', path=str(path), sha256=sha(path),
                count=len(records), per_instance=list(records.values()),
                effective_ce='Disabled in all 128 referenced physical cell definitions (LCE_EN=FALSE)',
                ce_pin_connections=0,
                physical_ce_nets=dict(collections.Counter(n for r in records.values() for n in r['pins'].get('CE', []))))

def main():
    result = dict(synthesis=[synthesized(HERE / n) for n in
                  ('build_counter_p1crc4an', 'build_counter_9caopnhe')],
                  routed=routed(HERE / 'build_counter_9caopnhe/routed_phy.txt'))
    assert all(x['gate']['status'] == 'PASS' for x in result['synthesis'])
    sim = OWN / 'simulation/receipt.json'
    evidence = json.loads(sim.read_bytes())
    assert evidence['status'] == 'PASS'
    assert evidence['candidate_sha256'] == sha(OWN / 'ov5640_cdc.v')
    assert evidence['log_sha256'] == sha(sim.parent / 'simulation.log')
    result['simulation_verified'] = evidence
    result['conclusion'] = 'Report-scope false positive in p1crc4an; actual counter has no synthesized CE, and all 128 routed counter FFs have CE disabled. No preserve attribute or architecture change needed.'
    (OWN / 'independent_pin_proof.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(result['conclusion'])
    print('Physical CE nets:', result['routed']['physical_ce_nets'])

if __name__ == '__main__':
    main()
