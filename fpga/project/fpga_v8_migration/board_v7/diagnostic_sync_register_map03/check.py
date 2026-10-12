"""Read-only, bounded twoFF structural/semantic sanity check; never starts PDS."""
from pathlib import Path
import argparse
import hashlib
import itertools
import json
import re

H = Path(__file__).resolve().parent
MODEL = Path('C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation/GTP_DFF_CE.v')
MODEL_HASH = '0bb065edebb4359a06146a2075ef0fe32b4466b7a12e674239552d9921a1a201'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_rtl(path):
    text = re.sub(r'//[^\n]*', '', path.read_bytes().decode('ascii'))
    text = re.sub(r'\s+', '', text)
    header = 'modulemap03_twoff_probe(inputwireclk,rst,d,outputwireq0,q1);'
    require(text.startswith(header) and text.endswith('endmodule'), 'primary output interface changed')
    body = text[len(header):-len('endmodule')]
    pattern = r'\(\*syn_noprune=1\*\)GTP_DFF_CE#\(\.GRS_EN\("TRUE"\),\.INIT\(1\x27b0\)\)(ff[01])\((.*?)\);'
    matches = list(re.finditer(pattern, body))
    require(''.join(m.group(0) for m in matches) == body and len(matches) == 2,
            'unexpected RTL, attributes or primitive parameters')
    cells = {}
    for m in matches:
        ports = dict(re.findall(r'\.(Q|D|CLK|C|CE)\(([^()]+)\)', m[2]))
        require(','.join('.' + p + '(' + v + ')' for p, v in ports.items()) == m[2], 'unexpected ports')
        require(m[1] not in cells, 'duplicate stage')
        cells[m[1]] = ports
    require(cells == {
        'ff0': {'Q': 'q0', 'D': 'd', 'CLK': 'clk', 'C': 'rst', 'CE': "1'b1"},
        'ff1': {'Q': 'q1', 'D': 'q0', 'CLK': 'clk', 'C': 'rst', 'CE': "1'b1"}}, 'chain/control contract changed')
    return cells


def evaluate(cells, state, d, rst, grs, rising):
    # Bounded two-state model of the installed primitive, not an HDL simulator.
    # RS = !GRSNET, RS -> INIT=0; C -> 0; CE=1 and posedge CLK -> D.
    nets = {'q0': state[0], 'q1': state[1], 'd': d}
    result = dict(nets)
    for ports in cells.values():
        if grs or rst:
            result[ports['Q']] = 0
        elif rising:
            result[ports['Q']] = nets[ports['D']]
    return result['q0'], result['q1']


def check():
    manifest = json.loads((H/'evidence/prepared_hashes.json').read_bytes())
    for name, digest in manifest.items():
        require(sha(H/name) == digest, 'prepared hash mismatch: ' + name)
    names = sorted(str(p.relative_to(H/'baseline')).replace('\\', '/')
                   for p in (H/'baseline').rglob('*') if p.is_file())
    site_names = sorted(str(p.relative_to(H/'site')).replace('\\', '/')
                        for p in (H/'site').rglob('*') if p.is_file())
    require(names == site_names, 'arm file lists differ')
    require(set(manifest) == {arm + '/' + name for arm in ['baseline', 'site'] for name in names},
            'unrecorded or missing prepared files')
    delta = [name for name in names if (H/'baseline'/name).read_bytes() != (H/'site'/name).read_bytes()]
    require(delta == ['constraints/site.lcf', 'constraints/site_reference.pcf'], 'unexpected arm delta')
    require(sha(MODEL) == MODEL_HASH, 'installed primitive semantic reference changed')
    basis = json.loads((H/'evidence/official_site_probe_basis.json').read_bytes())
    ref = basis['actual_sites_reference']
    require(sha(Path(ref['file'])) == ref['sha256'], 'actual-site reference changed')
    require(basis['proposed_sites'] == ['CLMA_33_450', 'CLMA_45_462'], 'site provenance changed')
    count = 0
    for arm in ['baseline', 'site']:
        cells = parse_rtl(H/arm/'rtl/twoff_probe.v')
        for a, b, d, rst, grs, rising in itertools.product([0, 1], repeat=6):
            golden = (0, 0) if (rst or grs) else ((d, a) if rising else (a, b))
            require(evaluate(cells, (a, b), d, rst, grs, rising) == golden, 'golden transition mismatch')
            count += 1
        for bits in itertools.product([0, 1], repeat=6):
            state = (0, 0)  # Both INIT=0, as verified in source and vendor model.
            history = [0, 0]
            for d in bits:
                state = evaluate(cells, state, d, 0, 0, True)
                history.append(d)
                require(state == (history[-1], history[-2]), 'two-stage cycle mismatch')
                count += 1
            require(evaluate(cells, state, 1, 1, 0, False) == (0, 0), 'asynchronous C reset mismatch')
            require(evaluate(cells, state, 1, 0, 1, False) == (0, 0), 'asynchronous GRS INIT mismatch')
    return {'status': 'OFFLINE_CHECK_OK', 'scope': 'twoFF method probe only; bounded two-state sanity, no HDL simulation',
            'source_sha256': manifest['baseline/rtl/twoff_probe.v'], 'arm_delta': delta,
            'golden_transition_and_cycle_checks': count, 'primitive_model_sha256': MODEL_HASH,
            'physical_status': 'PENDING_NOT_EXECUTED', 'map_constraint_binding': 'PENDING',
            'PDS_started': False, 'production_60_cell_evidence': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='default; read-only offline checks')
    parser.parse_args()  # No run/launch/controller-bypass option exists.
    print(json.dumps(check(), indent=2))
