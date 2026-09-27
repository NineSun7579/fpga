from pathlib import Path
from datetime import datetime

p = Path('source/ov5640/ovreg_axil_decode.v')
b = p.read_bytes()
backup = p.with_name(p.name + '.bak_decode_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
backup.write_bytes(b)
changes = [
    (b'reg [2:0] aw_sel;', b'reg [3:0] aw_sel;'),
    (b'reg [2:0] ar_sel;', b'reg [3:0] ar_sel;'),
    (b"aw_sel <= 3'b000;", b"aw_sel <= 4'b0000;"),
    (b"ar_sel <= 3'b000;", b"ar_sel <= 4'b0000;"),
    (b'wire [2:0] aw_sel_live', b'wire [3:0] aw_sel_live'),
    (b'wire [2:0] ar_sel_live', b'wire [3:0] ar_sel_live'),
    (b'aw_sel_live[2:1]', b'aw_sel_live[3:2]'),
    (b'ar_sel_live[2:1]', b'ar_sel_live[3:2]'),
    (b'aw_sel[2:1]', b'aw_sel[3:2]'),
    (b'ar_sel[2:1]', b'ar_sel[3:2]'),
    (b'// [CAM3] 3-bit:', b'// [CAM3] 4-bit:'),
    (b'assign m2_awvalid = s_awvalid & aw_m2;',
     b'assign m2_awvalid = s_awvalid & aw_m2;\n    assign m3_awvalid = s_awvalid & aw_m3;'),
]
for old,new in changes:
    assert b.count(old)==1, (old,b.count(old))
    if b'\r\n' in b:
        new=new.replace(b'\n',b'\r\n')
    b=b.replace(old,new)
p.write_bytes(b)
print('Backup:',backup)
print('Fixed selector width, page bits, and CAM3 AWVALID')
