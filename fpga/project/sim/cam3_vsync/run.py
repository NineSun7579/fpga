"""Run the exact inline production filter and real cmos_capture in ModelSim."""
from pathlib import Path
import subprocess
import hashlib
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BIN = Path(r'C:\modeltech64_10.6e\win64')
rtl = ROOT / 'source/ov5640/ov5640/ov5640.v'
data = rtl.read_bytes()
block = data.split(b'// VSYNC_FILTER_BEGIN', 1)[1].split(b'// VSYNC_FILTER_END', 1)[0]
# Fail if integration has drifted: raw probe and capture pin must be distinct.
assert b'dbg_vr_ff <= {dbg_vr_ff[1:0], cam_vsync}' in data
assert b'.cam_vsync  (capture_vsync)' in data
assert b'.cam_href   (cam_href)' in data and b'.cam_data   (cam_data)' in data
top = (ROOT / 'source/top.v').read_bytes()
assert top.count(b'.VSYNC_STABLE_CYCLES(64)') == 1
assert re.search(rb'ov5640_top\s*#\([^;]*\.VSYNC_STABLE_CYCLES\(64\)[^;]*\)\s*cam3_ov5640_top', top)
mid = (ROOT / 'source/ov5640/ov5640_top.v').read_bytes()
assert b'.VSYNC_STABLE_CYCLES(VSYNC_STABLE_CYCLES)' in mid
wrapper = b'''module filter_under_test #(parameter VSYNC_STABLE_CYCLES=64)(
input cam_pclk, ov_rst_n, cam_vsync, output filtered);
''' + block + b'assign filtered=capture_vsync;\nendmodule\n'
(HERE / 'filter_extracted.v').write_bytes(wrapper)
print('Production RTL SHA256', hashlib.sha256(data).hexdigest(), flush=True)
for exe, args in [
    ('vlib', ['work']),
    ('vlog', ['-logfile', 'compile_camera.log', str(rtl), str(ROOT / 'source/ov5640/ov5640_top.v')]),
    ('vlog', ['-sv', 'filter_extracted.v', str(ROOT / 'source/ov5640/ov5640/cmos_capture.v'), 'tb.sv']),
    ('vsim', ['-c', '-l', 'results.log', 'work.tb', '-do', 'onerror {quit -code 1}; run -all; quit -code 0']),
]:
    subprocess.run([str(BIN / (exe + '.exe')), *args], cwd=HERE, check=True)
assert 'PASS cam3 VSYNC' in (HERE / 'results.log').read_text()
