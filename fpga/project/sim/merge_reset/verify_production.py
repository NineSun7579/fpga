"""Read-only production audit and production-top reset extraction for simulation."""
from pathlib import Path
import hashlib
import json
import re
import os

here = Path(__file__).resolve().parent
rtl = here.parents[2] / 'ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl'
names = ['hdmi_ddr_ov5640_top.v', 'reg_config.v', 'i2c_com.v',
         'power_on_delay.v', 'cam2_merge.v', 'video_async_fifo.v', 'cmos_8_16bit.v']
hashes = {n: hashlib.sha256((rtl/n).read_bytes()).hexdigest() for n in names}
for name in ['reg_config.v', 'i2c_com.v']:
    assert (rtl/name).read_bytes() == (here/('candidate_'+name)).read_bytes(), name
    print('EXACT CANDIDATE MATCH', name)
table = (rtl/'reg_config.v').read_bytes().split(b'always@(reg_index)', 1)[1]
legacy = (here/'legacy_reg_config.v').read_bytes().split(b'always@(reg_index)', 1)[1]
assert table == legacy, 'sensor table changed'
hashes['sensor_table'] = hashlib.sha256(b'always@(reg_index)'+table).hexdigest()

def clean(data):
    return re.sub(rb'//[^\r\n]*', b'', data).decode('ascii').strip()

def compact(text):
    return re.sub(r'\s+', '', text)

top = Path(os.environ.get('TOP_RESET_CANDIDATE', str(rtl/'hdmi_ddr_ov5640_top.v'))).read_bytes()
hashes['hdmi_ddr_ov5640_top.v'] = hashlib.sha256(top).hexdigest()
decl = re.findall(rb'reg\s+\[15:0\]\s+rstn_1ms\s*=\s*16\x27d0\s*;', top)
assert len(decl) == 1, 'counter initialization'
counter = top[top.index(b'    reg startup_ready'):top.index(b'    (* ASYNC_REG')]
counter = clean(counter)
expected = """reg startup_ready = 1'b0;
always @(posedge cfg_clk or negedge locked)
if (!locked) startup_ready <= 1'b0;
else startup_ready <= (rstn_1ms == 16'h2710);
always @(posedge cfg_clk or negedge locked) begin
if (!locked) rstn_1ms <= 16'd0;
else begin
if (rstn_1ms == 16'h2710) rstn_1ms <= rstn_1ms;
else rstn_1ms <= rstn_1ms + 1'b1;
end end
assign rstn_int = locked & startup_ready;"""
assert compact(counter) == compact(expected), 'actual top counter/reset mismatch'
block = clean(top[top.index(b'    wire merge_req_n'):top.index(b'    cam2_merge #(')])
mapping = {'cmos1_pclk_16bit': 'a_clk', 'cmos2_pclk_16bit': 'b_clk',
           'mrg_clk': 'mrg_clk', 'cmos_init_done_int': 'config_done'}
for old, new in mapping.items():
    block = block.replace(old, new)
candidate = clean((here/'reset_candidate.sv').read_bytes())
expected_block = candidate[candidate.index('assign merge_req_n'):candidate.index('assign a_rst_n')]
expected_block = expected_block.replace('assign merge_req_n', 'wire merge_req_n')
assert compact(block) == compact(expected_block), 'three-domain common reset mismatch'
merge = clean(top[top.index(b'    cam2_merge #('):top.index(b'/* [SLIM Rev3.2] fram_buf')])
for port, signal in [('a_clk','cmos1_pclk_16bit'),('b_clk','cmos2_pclk_16bit'),('o_clk','mrg_clk'),
                     ('a_rst_n','merge_a_sync[1]'),('b_rst_n','merge_b_sync[1]'),('o_rst_n','merge_o_sync[1]')]:
    assert f'.{port}({signal})' in compact(merge), (port, signal)
power = clean(top[top.index(b'    power_on_delay'):top.index(b'//CMOS1 Camera')])
assert '.reset_n(sys_rst_n)' in compact(power), 'power sequencer reset wiring'
sys_block = clean(top[top.index(b'    (* ASYNC_REG'):top.index(b'    // Local diagnostic reset')])
expected_sys = """(* ASYNC_REG = "TRUE" *) reg [1:0] sys_rst_sync = 2'b00;
always @(posedge sys_clk or negedge rstn_int)
if (!rstn_int) sys_rst_sync <= 2'b00;
else sys_rst_sync <= {sys_rst_sync[0], 1'b1};
wire sys_rst_n = sys_rst_sync[1];"""
assert compact(sys_block) == compact(expected_sys), 'sys reset synchronizer mismatch'
diag_block = clean(top[top.index(b'    (* ASYNC_REG = "TRUE" *) reg [1:0] diag_rst_sync'):top.index(b'    assign rstn_out')])
expected_diag = expected_sys.replace('sys_rst', 'diag_rst').replace('sys_clk', 'clk_25M')
assert compact(diag_block) == compact(expected_diag), 'diagnostic reset synchronizer mismatch'
assert re.sub(rb'\s+', b'', top).count(b'.rst_n(diag_rst_n)') == 2
hsst = compact(clean(top[top.index(b'    hsst_test u_hsst('):top.index(b'// SFP0', top.index(b'    hsst_test u_hsst('))]))
assert '.i_free_clk(sys_clk)' in hsst
assert '.i_wtchdg_clr_0(~sys_rst_n)' in hsst
assert '.i_pll_rst_0(~sys_rst_n)' in hsst
# Audit active sys consumers, excluding preserved commented-out legacy examples.
active_top = clean(re.sub(rb'/\*.*?\*/', b'', top, flags=re.S))
assert active_top.count('posedge sys_clk or negedge rstn_int') == 1
assert active_top.count('posedge sys_clk or negedge sys_rst_n') == 2
assert active_top.count('if (!sys_rst_n)') == 3

# Compile literal production blocks rather than trusting a hand-coded candidate.
# Only the delay constant is parameterized for the small merge recovery test.
extraction = """`timescale 1ns/1ps
module merge_reset_top_candidate #(parameter DELAY=16'h2710)(
input cfg_clk, locked, input [1:0] config_done,
input a_clk, b_clk, mrg_clk,
output rstn_int, merge_req_n, a_rst_n, b_rst_n, o_rst_n);
"""
extraction += clean(decl[0]) + '\n' + counter.replace("16'h2710", 'DELAY') + '\n'
# merge_req_n is an output wire already declared in the wrapper.
extraction += block.replace('wire merge_req_n', 'assign merge_req_n') + '\n'
extraction += """assign a_rst_n=merge_a_sync[1];
assign b_rst_n=merge_b_sync[1];
assign o_rst_n=merge_o_sync[1];
endmodule
"""
extraction += """module production_sys_reset(input sys_clk, rstn_int, output sys_rst_n);
""" + sys_block.replace('wire sys_rst_n = sys_rst_sync[1];',
                          'assign sys_rst_n = sys_rst_sync[1];') + '\nendmodule\n'
extraction += """module production_diag_reset(input clk_25M, rstn_int, output diag_rst_n);
""" + diag_block.replace('wire diag_rst_n = diag_rst_sync[1];',
                          'assign diag_rst_n = diag_rst_sync[1];') + '\nendmodule\n'
(here/'actual_top_reset_extracted.sv').write_text(extraction, encoding='ascii')
(here/'production_hashes.json').write_text(json.dumps(hashes, indent=2)+'\n', encoding='ascii')
print('ACTUAL TOP MATCH: initialized/asynchronous PLL counter, qualified reset, sys async-assert/sync-release, power/heartbeat/diagnostic reset, common request, three clock domains and merge port wiring')
print(json.dumps(hashes, indent=2))
