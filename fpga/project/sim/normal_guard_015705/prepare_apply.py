"""ASCII byte-only preparation and gated normal apply. No vendor/hardware calls."""
import argparse
import difflib
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RTL = ROOT / 'ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl'
EXPECTED = {
    'hdmi_ddr_ov5640_top.v': '846ca35bc503ada4d678c751ab0a1930b22a8ca404bca654e39c6cc05d39d04c',
    'reg_config.v': '305b82b140c880c5ccdb43589629f792d1e3a181f58e612faa08e07eedc33d0c',
    'sfp_video_tx.v': '29a637f725a48323b8f8351221183cf823afa5917a41098bc748cd61969793cc',
}
NAMES = list(EXPECTED) + ['i2c_com.v', 'power_on_delay.v']
sha = lambda data: hashlib.sha256(data).hexdigest()

def require(ok, message):
    if not ok:
        raise RuntimeError(message)

def replace_once(data, old, new):
    require(data.count(old) == 1, 'ambiguous byte anchor: ' + repr(old))
    return data.replace(old, new, 1)

def load(path):
    return json.loads(path.read_bytes())

def prepare():
    originals = {n: (RTL / n).read_bytes() for n in NAMES}
    for n, expected in EXPECTED.items():
        require(sha(originals[n]) == expected, 'baseline SHA mismatch: ' + n)
    normal = dict(originals)
    normal['hdmi_ddr_ov5640_top.v'] = replace_once(originals['hdmi_ddr_ov5640_top.v'],
        b'parameter COLOR_BAR_TEST = 1,', b'parameter COLOR_BAR_TEST = 0,')
    alternative = dict(originals)
    alternative['sfp_video_tx.v'] = replace_once(originals['sfp_video_tx.v'],
        b'parameter TX_GE_SKIP_ENABLE=1', b'parameter TX_GE_SKIP_ENABLE=0')
    manifest = {'mode': 'normal_acquisition', 'production_applied': False,
        'normal_defaults': {'top_COLOR_BAR_TEST': 0, 'reg_COLOR_BAR_TEST': 0, 'TX_GE_SKIP_ENABLE': 1},
        'failure_isolation_defaults': {'top_COLOR_BAR_TEST': 1, 'reg_COLOR_BAR_TEST': 0, 'TX_GE_SKIP_ENABLE': 0},
        'original_sha256': {n: sha(b) for n, b in originals.items()},
        'normal_source_sha256': {n: sha(b) for n, b in normal.items()},
        'guard_only_source_sha256': {n: sha(b) for n, b in alternative.items()}}
    for directory, files in [('original', originals), ('normal', normal), ('guard_only_diagnostic', alternative)]:
        dest = HERE / directory
        dest.mkdir(exist_ok=True)
        for n, b in files.items():
            (dest / n).write_bytes(b)
    for label, files in [('normal', normal), ('guard_only_diagnostic', alternative)]:
        diff = []
        for n in NAMES:
            diff.extend(difflib.unified_diff(originals[n].decode('ascii', 'backslashreplace').splitlines(True),
                files[n].decode('ascii', 'backslashreplace').splitlines(True),
                fromfile='original/' + n, tofile=label + '/' + n))
        (HERE / (label + '.patch')).write_text(''.join(diff), encoding='ascii')
    old = ROOT / 'project/sim/sensor_colorbar_candidate'
    for n in ['tb_sensor_colorbar.sv', 'baseline_commands.mem']:
        (HERE / n).write_bytes((old / n).read_bytes())
    blocks = re.findall(rb'reg_config #\(.COLOR_BAR_TEST\(COLOR_BAR_TEST\)\)\s+coms[12]_reg_config\(.*?\);', normal['hdmi_ddr_ov5640_top.v'], re.S)
    require(len(blocks) == 2, 'both actual parameter-passed sensor instances required')
    (HERE / 'actual_sensor_instances.vh').write_bytes(b'\n'.join(blocks))
    require(b'parameter COLOR_BAR_TEST = 0' in normal['reg_config.v'], 'reg default')
    table = {int(k): int(v, 16) for k, v in re.findall(rb"(\d+)\s*:reg_data\s*<=24'h([0-9a-fA-F]{6})", normal['reg_config.v'])}
    golden = [int(w, 16) for w in (HERE / 'baseline_commands.mem').read_bytes().split()]
    require([0x78000000 | table.get(i, 0xffffff) for i in range(357)] == golden, 'original 357-command stream changed')
    require(table[1] == 0x300882 and table[357] == 0x503d80, 'reset/test-write provenance')
    (HERE / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='ascii')
    require(all((RTL / n).read_bytes() == b for n, b in originals.items()), 'production changed during preparation')
    print('PREPARED: normal top=0 reg=0 TX_SKIP=1; failure isolation top=1 reg=0 TX_SKIP=0')

def apply_normal():
    manifest = load(HERE / 'manifest.json')
    proof = load(HERE / 'test_result.json')
    require(proof['pass'] is True and proof['normal_source_sha256'] == manifest['normal_source_sha256'], 'missing exact candidate test proof')
    evidence = ROOT / 'log/six_guard_board_20261003'
    result = load(evidence / 'workflow_result.json')
    handoff = load(ROOT / 'log/six_guard_015705_handoff.json')
    require(result['pass'] is True and result['failures'] == [], 'guard board acceptance failed/pending')
    require(handoff['stage'] == 'finished' and handoff['status'] == 'verified', 'guard owner has not finished')
    require(handoff['result'] == result, 'owner/result mismatch')
    require(load(evidence / 'colorbar_geometry.json')['geometry_pass'] is True, 'geometry failed')
    require((evidence / 'rk3568_guard_screen.png').read_bytes().startswith(b'\x89PNG\r\n\x1a\n'), 'missing actual guard screenshot')
    burn = load(evidence / 'actual_last_burn.json')
    require(burn['sha256'] == result['actual_last_burn_sha256'] == handoff['bit_sha256'], 'burn provenance mismatch')
    require(sha(Path(burn['bitstream']).read_bytes()) == burn['sha256'], 'burned archive SHA changed')
    tree = load(HERE / 'source_tree_hashes.json')
    actual_tree = {p.relative_to(RTL).as_posix(): sha(p.read_bytes()) for p in RTL.rglob('*') if p.is_file()}
    require(actual_tree == tree['original_sha256'], 'complete source tree provenance mismatch')
    for n in NAMES:
        require(sha((RTL / n).read_bytes()) == manifest['original_sha256'][n], 'production SHA mismatch: ' + n)
        require(sha((HERE / 'normal' / n).read_bytes()) == manifest['normal_source_sha256'][n], 'candidate SHA mismatch: ' + n)
    target = RTL / 'hdmi_ddr_ov5640_top.v'
    require(target.read_bytes() == (HERE / 'original' / target.name).read_bytes(), 'original backup mismatch')
    target.write_bytes((HERE / 'normal' / target.name).read_bytes())
    require(all(sha((RTL / n).read_bytes()) == manifest['normal_source_sha256'][n] for n in NAMES), 'post-apply SHA mismatch')
    print('APPLIED normal source only. New archive/build/audit/burn/30s capture still required.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('action', choices=['prepare', 'apply-normal'])
    args = parser.parse_args()
    prepare() if args.action == 'prepare' else apply_normal()
