"""Apply verified reset edits while preserving source encoding byte for byte."""
from pathlib import Path

root = Path(__file__).resolve().parents[2] / 'ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl'

def edit(name, replacements):
    path = root / name
    data = path.read_bytes()
    for old, new, count in replacements:
        old, new = old.encode('ascii'), new.encode('ascii')
        if data.count(old) != count:
            raise RuntimeError(f'{name}: unexpected match count for {old!r}')
        data = data.replace(old, new)
    path.write_bytes(data)

edit('reg_config.v', [
    ('always@(posedge clk_25M)', 'always@(posedge clk_25M or negedge camera_rstn)', 1),
    ('always@(posedge clock_20k)', 'always@(posedge clock_20k or negedge camera_rstn)', 1),
    ('0:begin', '0:begin if (initial_en) begin', 1),
    ('config_step<=1;', 'config_step<=1; end', 1),
])
edit('i2c_com.v', [
    ('always@(posedge clock_i2c)', 'always@(posedge clock_i2c or negedge camera_rstn)', 2),
])
path = root / 'hdmi_ddr_ov5640_top.v'
data = path.read_bytes()
lines = data.splitlines(keepends=True)
matches = [i for i, line in enumerate(lines) if b'reg ' in line and b'rstn_1ms' in line and b';' in line]
if len(matches) != 1:
    raise RuntimeError('reset counter declaration not unique')
index = matches[0]
lines[index] = lines[index].replace(b'rstn_1ms', b"rstn_1ms = 16'd0")
path.write_bytes(b''.join(lines))
edit('hdmi_ddr_ov5640_top.v', [
    ('always @(posedge cfg_clk)', 'always @(posedge cfg_clk or negedge locked)', 1),
    ('assign rstn_int  = (rstn_1ms == 16\'h2710);', 'assign rstn_int  = locked & (rstn_1ms == 16\'h2710);', 1),
    ('.reset_n                 (1\'b1           )', '.reset_n                 (rstn_int        )', 1),
    ('.a_rst_n (  cmos_init_done_int[0]                   )', '.a_rst_n (  merge_a_sync[1]                         )', 1),
    ('.b_rst_n (  cmos_init_done_int[1]                   )', '.b_rst_n (  merge_b_sync[1]                         )', 1),
    ('.o_rst_n (  fab_rst_n                          )', '.o_rst_n (  merge_o_sync[1]                     )', 1),
    ('    cam2_merge #(', '''    wire merge_req_n = rstn_int & (&cmos_init_done_int);
    reg [1:0] merge_a_sync = 2'b00;
    reg [1:0] merge_b_sync = 2'b00;
    reg [1:0] merge_o_sync = 2'b00;
    always @(posedge cmos1_pclk_16bit or negedge merge_req_n)
        if (!merge_req_n) merge_a_sync <= 2'b00;
        else merge_a_sync <= {merge_a_sync[0], 1'b1};
    always @(posedge cmos2_pclk_16bit or negedge merge_req_n)
        if (!merge_req_n) merge_b_sync <= 2'b00;
        else merge_b_sync <= {merge_b_sync[0], 1'b1};
    always @(posedge mrg_clk or negedge merge_req_n)
        if (!merge_req_n) merge_o_sync <= 2'b00;
        else merge_o_sync <= {merge_o_sync[0], 1'b1};
    cam2_merge #('''.replace('\n', '\r\n'), 1),
])
print('Applied 50K reset recovery preserving unrelated source bytes')
