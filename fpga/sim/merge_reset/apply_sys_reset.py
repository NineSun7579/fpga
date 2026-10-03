"""Scoped byte-preserving top patch; records exact diff and before/after SHA256."""
from pathlib import Path
import hashlib
import difflib
import json

here = Path(__file__).resolve().parent
top = here.parents[2] / 'ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl/hdmi_ddr_ov5640_top.v'
before = top.read_bytes()
assert b'reg [1:0] sys_rst_sync' not in before
anchor = b'    assign rstn_out  = rstn_int;'
assert before.count(anchor) == 1
nl = b'\r\n' if b'\r\n' in before else b'\n'
block = nl.join([
    b'    // Common sys_clk reset: asynchronous assertion, two-edge release.',
    b'    // Keep cfg startup delay and merge reset request in their original domains.',
    b'    (* ASYNC_REG = "TRUE" *) reg [1:0] sys_rst_sync = 2\'b00;',
    b'    always @(posedge sys_clk or negedge rstn_int)',
    b'        if (!rstn_int) sys_rst_sync <= 2\'b00;',
    b'        else sys_rst_sync <= {sys_rst_sync[0], 1\'b1};',
    b'    wire sys_rst_n = sys_rst_sync[1];', b'', b''])
after = before.replace(anchor, block + anchor)
old = b'.reset_n                 (rstn_int        )'
assert after.count(old) == 1
after = after.replace(old, b'.reset_n                 (sys_rst_n       )')
# Change only active sys_clk blocks; preserve commented legacy examples.
lines = after.splitlines(keepends=True)
inside = False
changes = 0
for i, line in enumerate(lines):
    if line.lstrip().startswith(b'//'):
        continue
    if b'always' in line:
        inside = b'posedge sys_clk' in line and b'sys_rst_sync' not in lines[min(i+1, len(lines)-1)]
    if inside and b'rstn_int' in line:
        lines[i] = line.replace(b'rstn_int', b'sys_rst_n')
        changes += 1
assert changes == 5, changes
after = b''.join(lines)
# Save a scoped backup for audit, without touching any other production file.
(here/'sys_reset_top_before.bin').write_bytes(before)
(here/'sys_reset_top.diff').write_text(''.join(difflib.unified_diff(
    before.decode('latin1').splitlines(True), after.decode('latin1').splitlines(True),
    fromfile='production top before', tofile='production top after')), encoding='latin1')
(here/'sys_reset_patch_hashes.json').write_text(json.dumps({
    'before': hashlib.sha256(before).hexdigest(),
    'after': hashlib.sha256(after).hexdigest()}, indent=2)+'\n')
top.write_bytes(after)
print((here/'sys_reset_patch_hashes.json').read_text())
