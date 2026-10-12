"""Byte-preserving simulation copies only; never writes production sources."""
from pathlib import Path
import difflib
import hashlib

here = Path(__file__).resolve().parent
rtl = here.parents[2] / 'ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl'
changes = {
    'reg_config.v': [
        (b'always@(posedge clk_25M)', b'always@(posedge clk_25M or negedge camera_rstn)'),
        (b'always@(posedge clock_20k)', b'always@(posedge clock_20k or negedge camera_rstn)'),
        (b'0:begin', b'0:begin if (initial_en) begin'),
    ],
    'i2c_com.v': [
        (b'always@(posedge clock_i2c)', b'always@(posedge clock_i2c or negedge camera_rstn)'),
    ],
}
diffs = []
for name, replacements in changes.items():
    original = (rtl / name).read_bytes()
    candidate = original
    for old, new in replacements:
        expected = 2 if name == 'i2c_com.v' else 1
        assert candidate.count(old) == expected, (name, old, candidate.count(old))
        candidate = candidate.replace(old, new)
    if name == 'reg_config.v':
        # Close only the new launch guard, leaving the 357-entry table unchanged.
        old = b'config_step<=1;'
        candidate = candidate.replace(old, old + b' end')
        table = original[original.index(b'always@(reg_index)'):]
        assert candidate[candidate.index(b'always@(reg_index)'):] == table
        print('UNCHANGED SENSOR TABLE sha256=' + hashlib.sha256(table).hexdigest())
    (here / ('candidate_' + name)).write_bytes(candidate)
    legacy = original.replace(b'module reg_config(', b'module reg_config_legacy(')
    legacy = legacy.replace(b'i2c_com u1', b'i2c_com_legacy u1')
    legacy = legacy.replace(b'module i2c_com(', b'module i2c_com_legacy(')
    (here / ('legacy_' + name)).write_bytes(legacy)
    # ASCII code changes only; decode comments identically on both sides.
    diffs.extend(difflib.unified_diff(
        original.decode('utf-8', errors='replace').splitlines(True),
        candidate.decode('utf-8', errors='replace').splitlines(True),
        fromfile='actual/' + name, tofile='sim_candidate/' + name))
(here / 'config_candidate.diff').write_text(''.join(diffs), encoding='utf-8')
print('Prepared isolated candidate and legacy copies')
