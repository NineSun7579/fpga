"""Byte-preserving, no-overwrite preparation from the deployed frozen inputs."""
from pathlib import Path
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FROZEN = ROOT / 'project/motion_100h/run_20261003_212303'
TOP = HERE / 'source/top.v'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')

def candidate():
    raw = (FROZEN / 'inputs/source/top.v').read_bytes()
    result = raw
    for cam in (3, 4):
        pattern = rb'ov5640_top\s*#\((?:(?!ov5640_top).)*?\)\s*cam' + str(cam).encode() + rb'_ov5640_top\s*\('
        matches = list(re.finditer(pattern, result, re.S))
        assert len(matches) == 1, cam
        match = matches[0]
        block = match.group()
        assert block.count(b'.TOTAL_V_PIXEL   (12\'d984)') == 1
        assert b'.SENSOR_PLL_MULT (8\'h30)' in block
        assert b'.TOTAL_H_PIXEL   (12\'d1896)' in block
        new = block.replace(b'.TOTAL_V_PIXEL   (12\'d984)', b'.TOTAL_V_PIXEL   (12\'d843)')
        result = result[:match.start()] + new + result[match.end():]
    changed = [i + 1 for i, (a, b) in enumerate(zip(raw.splitlines(), result.splitlines())) if a != b]
    assert changed == [1571, 1672], changed
    assert result.replace(b'.TOTAL_V_PIXEL   (12\'d843)', b'.TOTAL_V_PIXEL   (12\'d984)') == raw
    return result, changed

def project_bytes():
    raw = (FROZEN / 'project.pds').read_bytes()
    def replace(match):
        name = match.group(1).decode('ascii')
        if name == '../source/top.v':
            path = TOP
        elif name.startswith(('../source/', '../ipcore/')):
            path = FROZEN / 'inputs' / name[3:]
        else:
            raise RuntimeError('Unexpected registered path: ' + name)
        assert path.is_file(), path
        return b'"' + path.resolve().as_posix().encode('ascii') + b'"'
    return re.sub(rb'"(\.\./(?:source|ipcore)/[^"\r\n]+)"', replace, raw)

def check():
    assert sha(FROZEN / 'input_sha256.json') == 'e1059783fe49166f4507257dafc57ce4abc06e27e294607ce07b59c5401c6c0a'
    assert sha(FROZEN / 'project.pds') == '53f984033879551cb99ffa23b923f9828450996ae84881114991b38fca990169'
    assert sha(FROZEN / 'top.sbit') == 'e3da6e1fbc7d0bb2abcc2ee57342906e395fb74cecd1f3163e9ada33e89e96f7'
    expected = json.loads((FROZEN / 'input_sha256.json').read_text())
    inputs = {k: v for k, v in expected.items() if k.startswith(('source/', 'ipcore/'))}
    actual = {p.relative_to(FROZEN / 'inputs').as_posix() for tree in ('source', 'ipcore')
              for p in (FROZEN / 'inputs' / tree).rglob('*') if p.is_file()}
    assert actual == set(inputs), 'Frozen input inventory changed'
    for name, digest in inputs.items():
        assert sha(FROZEN / 'inputs' / name) == digest, name
    assert sha(FROZEN / 'top.sbit') == json.loads((FROZEN / 'bit_provenance.json').read_text())['bit_sha256']
    raw, changed = candidate()
    assert TOP.read_bytes() == raw
    assert (HERE / 'cloned.pds').read_bytes() == project_bytes()
    pds = (HERE / 'cloned.pds').read_bytes()
    paths = re.findall(rb'\(_(?:file|ip|ip_source_item)\s+"([^"]+)"', pds)
    for path in paths:
        assert Path(path.decode('ascii')).is_file(), path
    assert pds.count(TOP.as_posix().encode()) == 1
    # Actual parameter-to-ROM connection; test ROM ports separately in ModelSim.
    outer = (FROZEN / 'inputs/source/ov5640/ov5640_top.v').read_bytes()
    inner = (FROZEN / 'inputs/source/ov5640/ov5640/ov5640.v').read_bytes()
    for token in (b'.TOTAL_V_PIXEL(TOTAL_V_PIXEL)', b'.SENSOR_PLL_MULT(SENSOR_PLL_MULT)'):
        assert token in outer
    for token in (b'.total_v_pixel(TOTAL_V_PIXEL)', b'.SENSOR_PLL_MULT(SENSOR_PLL_MULT)'):
        assert token in inner
    return {'changed_lines': changed, 'registered_paths': len(paths),
            'baseline_bit_sha256': sha(FROZEN / 'top.sbit'),
            'frozen_manifest_sha256': sha(FROZEN / 'input_sha256.json'),
            'frozen_project_sha256': sha(FROZEN / 'project.pds'),
            'baseline_top_sha256': sha(FROZEN / 'inputs/source/top.v'),
            'candidate_top_sha256': sha(TOP), 'cloned_pds_sha256': sha(HERE / 'cloned.pds'),
            'constraint_sha256': {k: v for k, v in inputs.items() if k.startswith('source/constraints/')},
            'parameter_propagation_static': 'PASS', 'protected_inputs_verified': len(inputs)}

def main():
    TOP.parent.mkdir(exist_ok=True)
    raw, _ = candidate()
    if not TOP.exists():
        with TOP.open('xb') as stream:
            stream.write(raw)
    pds = project_bytes()
    if not (HERE / 'cloned.pds').exists():
        with (HERE / 'cloned.pds').open('xb') as stream:
            stream.write(pds)
    receipt = check()
    save(HERE / 'preparation.json', receipt)
    print(json.dumps(receipt, indent=2))

if __name__ == '__main__':
    main()
