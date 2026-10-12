"""Isolated SCCB golden from immutable normal rollback and explicit edits."""
from pathlib import Path
import hashlib, json, re, shutil, zipfile
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RTL = ROOT / 'ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl'
BASE = RTL.parents[1] / 'bitstream_final_50k_20261003_023911'
TEST = HERE / 'margin_sccb'
TEST.mkdir(exist_ok=True)
with zipfile.ZipFile(BASE / 'sources.zip') as z:
    before = z.read('source/rtl/reg_config.v')
assert hashlib.sha256(before).hexdigest() == '305b82b140c880c5ccdb43589629f792d1e3a181f58e612faa08e07eedc33d0c'
candidate = (HERE / 'candidate/reg_config.v').read_bytes()
assert hashlib.sha256(candidate).hexdigest() == '1cd4405242a95f054fec9b7dd1e3ec7b84a46f5a5d15a02fad9a6902534e7124'
def commands(data):
    pairs = re.findall(rb'(\d+)\s*:reg_data\s*<=24\x27h([0-9a-fA-F]{6})', data)
    indexes = [int(i) for i, _ in pairs]
    assert len(indexes) == len(set(indexes)), 'duplicate command indexes'
    return {int(i): int(v, 16) for i, v in pairs}
old, new = commands(before), commands(candidate)
expected = dict(old)
for i, a, b in [(147, 0x381100, 0x381110), (316, 0x3801a0, 0x380180), (320, 0x38059f, 0x3805bf)]:
    assert old[i] == a
    expected[i] = b
assert new == expected
assert set(range(2,102)).isdisjoint(new)
assert set(range(102,357)).issubset(new)
writes = {}
for i in range(357):
    word = new.get(i, 0xffffff)
    writes.setdefault(word >> 8, []).append({'index': i, 'value': word & 255})
effective = {address: values[-1]['value'] for address, values in writes.items()}
for address, value in {0x3811:0x10, 0x3800:2, 0x3801:0x80, 0x3804:7, 0x3805:0xbf,
                       0x3808:2, 0x3809:0x80, 0x380a:1, 0x380b:0xe0}.items():
    assert effective[address] == value, (hex(address), writes[address])
assert 0x503d not in writes, 'normal mode must not enable test bars'
proof = {'normal_commands':357, 'changes': [147,316,320],
         'write_history':{f'{a:04x}':v for a,v in writes.items()},
         'effective_final_map':{f'{a:04x}':f'{v:02x}' for a,v in effective.items()},
         'input_x':[640,1983], 'output':[640,480], 'nominal_visible_x':[672,1951]}
(TEST / 'effective_register_map.json').write_text(json.dumps(proof, indent=2))
(TEST / 'baseline_commands.mem').write_text(''.join(f'78{expected.get(i,0xffffff):06x}\n' for i in range(357)))
(TEST / 'reg_config.v').write_bytes(candidate)
for name in ('i2c_com.v', 'power_on_delay.v'):
    shutil.copy2(RTL / name, TEST / name)
for name in ('actual_sensor_instances.vh', 'tb_sensor_colorbar.sv'):
    shutil.copy2(ROOT / 'project/sim/sensor_colorbar_candidate' / name, TEST / name)
print(json.dumps({k:proof[k] for k in ('normal_commands','changes','input_x','output','nominal_visible_x')}))
print('3811 write history:', writes[0x3811])
