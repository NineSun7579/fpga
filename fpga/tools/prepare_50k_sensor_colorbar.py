"""Prepare isolated, byte-preserving OV5640 colorbar RTL; never write production."""
import argparse
import difflib
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RTL = ROOT / 'ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl'

def replace_once(data, old, new):
    assert data.count(old) == 1, repr(old)
    return data.replace(old, new, 1)

def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'project/sim/sensor_colorbar_candidate')
    args = parser.parse_args()
    out = args.out.resolve()
    assert out != RTL.resolve() and RTL.resolve() not in out.parents
    out.mkdir(parents=True, exist_ok=True)
    names = ['reg_config.v', 'hdmi_ddr_ov5640_top.v', 'i2c_com.v', 'power_on_delay.v']
    originals = {name: (RTL / name).read_bytes() for name in names}
    config = originals['reg_config.v']
    nl = b'\r\n' if b'\r\n' in config else b'\n'
    config = replace_once(config, b'module reg_config(',
                          b'module reg_config #(parameter COLOR_BAR_TEST = 0)(')
    config = replace_once(config, b'if(reg_index<357)',
                          b'if(reg_index < (COLOR_BAR_TEST ? 358 : 357))')
    anchor = b"\t default:reg_data<=24'hffffff;"
    config = replace_once(config, anchor,
                          b"     357  :reg_data <=24'h503D80; // OV5640 standard sensor color bars" + nl + anchor)
    top = originals['hdmi_ddr_ov5640_top.v']
    top = replace_once(top, b'parameter MEM_ROW_ADDR_WIDTH',
                       b'parameter COLOR_BAR_TEST = 0, // Both OV5640 sensors; normal image by default\n\tparameter MEM_ROW_ADDR_WIDTH')
    for sensor in (1, 2):
        old = b'reg_config\tcoms%d_reg_config(' % sensor
        top = replace_once(top, old, b'reg_config #(.COLOR_BAR_TEST(COLOR_BAR_TEST))\tcoms%d_reg_config(' % sensor)
    patched = dict(originals, **{'reg_config.v': config, 'hdmi_ddr_ov5640_top.v': top})
    # A separate build-ready diagnostic top makes the override concrete without
    # depending on undocumented PDS top-parameter override syntax.
    diagnostic_top = replace_once(top, b'parameter COLOR_BAR_TEST = 0,', b'parameter COLOR_BAR_TEST = 1,')
    (out / 'diagnostic_hdmi_ddr_ov5640_top.v').write_bytes(diagnostic_top)
    for name, data in patched.items():
        (out / name).write_bytes(data)
        (out / ('before_' + name)).write_bytes(originals[name])
    diff = []
    for name in names[:2]:
        diff.extend(difflib.unified_diff(originals[name].decode('gbk', 'backslashreplace').splitlines(True),
                    patched[name].decode('gbk', 'backslashreplace').splitlines(True),
                    fromfile='production/' + name, tofile='candidate/' + name))
    (out / 'minimal.patch').write_text(''.join(diff), encoding='utf-8')
    # Independent golden command stream comes from untouched production bytes.
    table = {int(k): int(v, 16) for k, v in re.findall(rb"(\d+)\s*:reg_data\s*<=24'h([0-9a-fA-F]{6})", originals['reg_config.v'])}
    assert table[356] == 0x350300 and 357 not in table
    words = [0x78000000 | table.get(i, 0xffffff) for i in range(357)]
    (out / 'baseline_commands.mem').write_text(''.join('%08x\n' % w for w in words), encoding='ascii')
    # Extract the actual two production instance blocks after parameter wiring.
    blocks = re.findall(rb'reg_config #\(.COLOR_BAR_TEST\(COLOR_BAR_TEST\)\)\s+coms[12]_reg_config\(.*?\);', top, re.S)
    assert len(blocks) == 2
    (out / 'actual_sensor_instances.vh').write_bytes(b'\n'.join(blocks))
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in originals.items()}
    (out / 'production_hashes.json').write_text(json.dumps(hashes, indent=2), encoding='ascii')
    assert all((RTL / name).read_bytes() == data for name, data in originals.items())
    print('PREPARED isolated candidate:', out)
    print('Normal=357 commands; colorbar=358 commands ending 78 50 3D 80; both top instances wired.')

if __name__ == '__main__':
    main()
