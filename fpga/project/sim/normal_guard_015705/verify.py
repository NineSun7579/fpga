"""Verify isolated sources and serial regression evidence; write local proof only."""
from prepare_apply import HERE, RTL, NAMES, sha, load, require, replace_once
import json
import re

m = load(HERE / 'manifest.json')
for n in NAMES:
    require(sha((RTL / n).read_bytes()) == m['original_sha256'][n], 'production changed: ' + n)
    require(sha((HERE / 'normal' / n).read_bytes()) == m['normal_source_sha256'][n], 'candidate changed: ' + n)
top = (HERE / 'normal/hdmi_ddr_ov5640_top.v').read_bytes()
require(top == replace_once((HERE / 'original/hdmi_ddr_ov5640_top.v').read_bytes(),
    b'parameter COLOR_BAR_TEST = 1,', b'parameter COLOR_BAR_TEST = 0,'), 'top must change only default')
blocks = re.findall(rb'reg_config #\(.COLOR_BAR_TEST\(COLOR_BAR_TEST\)\)\s+coms[12]_reg_config\(.*?\);', top, re.S)
require(len(blocks) == 2 and b'\n'.join(blocks) == (HERE / 'actual_sensor_instances.vh').read_bytes(), 'actual wiring mismatch')
for mode, count in [(0, 357), (1, 358)]:
    log = (HERE / ('mode_%d.log' % mode)).read_bytes()
    require(('TEST PASS mode=%d' % mode).encode() in log, 'mode PASS missing')
    for camera in [1, 2]:
        for run in [1, 2]:
            require(('SCCB PASS camera=%d run=%d commands=%d START=%d STOP=%d completions=%d ACK=%d' %
                (camera, run, count, count, count, count, 4*count)).encode() in log, 'missing serial bus proof')
proof = {'pass': True, 'mode': 'normal_acquisition', 'normal_source_sha256': m['normal_source_sha256'],
    'top_wiring_lint': 'both actual parameter-passed instances; only top default changed',
    'normal_sccb': '357 original commands per sensor, two rounds, reset while source clock stopped',
    'diagnostic_sccb': '358 commands per sensor, two rounds, appended 78503d80',
    'hardware_tested': False, 'production_applied': False,
    'logs_sha256': {str(mode): sha((HERE / ('mode_%d.log' % mode)).read_bytes()) for mode in [0, 1]}}
(HERE / 'test_result.json').write_text(json.dumps(proof, indent=2), encoding='ascii')
print('PASS: mode-labeled SCCB tests, actual instance wiring lint, production unchanged')
