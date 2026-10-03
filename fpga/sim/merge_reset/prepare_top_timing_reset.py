"""Prepare byte-preserving top-only candidate; apply only after candidate validation."""
from pathlib import Path
import hashlib
import json
import sys

here = Path(__file__).resolve().parent
rtl = here.parents[2] / 'ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl'
top = rtl / 'hdmi_ddr_ov5640_top.v'
before = here / 'timing_reset_top_before.bin'
candidate = here / 'timing_reset_top_candidate.v'
def sha(b): return hashlib.sha256(b).hexdigest()
if '--apply' in sys.argv:
    audit = json.loads((here/'timing_reset_candidate_hashes.json').read_text())
    assert sha(top.read_bytes()) == audit['before'], 'production top changed since preparation'
    assert sha(candidate.read_bytes()) == audit['candidate']
    top.write_bytes(candidate.read_bytes())
    print('APPLIED', sha(top.read_bytes()))
else:
    data = top.read_bytes()
    before.write_bytes(data)
    edits = [
        (b'    always @(posedge cfg_clk or negedge locked)',
         b"    // Registered startup request: comparator never drives reset pins directly.\r\n"
         b"    reg startup_ready = 1'b0;\r\n"
         b"    always @(posedge cfg_clk or negedge locked)\r\n"
         b"        if (!locked) startup_ready <= 1'b0;\r\n"
         b"        else startup_ready <= (rstn_1ms == 16'h2710);\r\n\r\n"
         b'    always @(posedge cfg_clk or negedge locked)'),
        (b'locked & (rstn_1ms == 16\'h2710)', b'locked & startup_ready'),
        (b'    assign rstn_out  = rstn_int;',
         b'    // Local diagnostic reset: async assertion, two clk_25M edges to release.\r\n'
         b'    (* ASYNC_REG = "TRUE" *) reg [1:0] diag_rst_sync = 2\'b00;\r\n'
         b'    always @(posedge clk_25M or negedge rstn_int)\r\n'
         b"        if (!rstn_int) diag_rst_sync <= 2'b00;\r\n"
         b"        else diag_rst_sync <= {diag_rst_sync[0], 1'b1};\r\n"
         b'    wire diag_rst_n = diag_rst_sync[1];\r\n\r\n'
         b'    assign rstn_out  = rstn_int;'),
        (b'.rst_n    ( rstn_out        )', b'.rst_n    ( diag_rst_n      )'),
        (b'.i_wtchdg_clr_0      (  ~rstn_int      )', b'.i_wtchdg_clr_0      (  ~sys_rst_n     )'),
        (b'.i_pll_rst_0         (  ~rstn_int      )', b'.i_pll_rst_0         (  ~sys_rst_n     )'),
    ]
    for old, new in edits:
        assert data.count(old) == (2 if old.startswith(b'.rst_n ') else 1), old
        data = data.replace(old, new)
    candidate.write_bytes(data)
    (here/'timing_reset_candidate_hashes.json').write_text(json.dumps({
        'before': sha(before.read_bytes()), 'candidate': sha(data)}, indent=2)+'\n')
    print('PREPARED', sha(data))
