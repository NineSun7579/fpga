"""Checked byte edits to broaden the original ROM harness and stage receipts."""
from pathlib import Path
HERE = Path(__file__).resolve().parent

def edit(name, edits):
    path = HERE / name
    raw = path.read_bytes()
    for old, new, count in edits:
        assert raw.count(old) == count, (name, old, raw.count(old))
        raw = raw.replace(old, new)
    path.write_bytes(raw)

edit('tb_config.v', [
    (b'[3:0]', b'[5:0]', 2),
    (b'[0:3]', b'[0:5]', 2),
    (b'c<4', b'c<6', 1),
    (b'j<4', b'j<6', 3),
    (b".cmos_h_pixel(13'd640),.cmos_v_pixel(13'd480),\n .total_h_pixel(13'd1896),.total_v_pixel(13'd984),\n .i2c_exec(exec[c])",
     b".cmos_h_pixel(c==4 ? 13'd320 : c==5 ? 13'd1280 : 13'd640),\n .cmos_v_pixel(c==4 ? 13'd240 : c==5 ? 13'd720 : 13'd480),\n .total_h_pixel(13'd1896),.total_v_pixel(13'd984),\n .i2c_exec(exec[c])", 1),
    (b'end else if(data[j]!==baseline[index])', b'end else if(!(j>=4 && index>=223 && index<=226) && data[j]!==baseline[index])', 1),
    (b"data[j]!==24'h380802", b"data[j]!==(j==4 ? 24'h380801 : j==5 ? 24'h380805 : 24'h380802)", 1),
    (b"data[j]!==24'h380980", b"data[j]!==(j==4 ? 24'h380940 : j==5 ? 24'h380900 : 24'h380980)", 1),
    (b"data[j]!==24'h380a01", b"data[j]!==(j==4 ? 24'h380a00 : j==5 ? 24'h380a02 : 24'h380a01)", 1),
    (b"data[j]!==24'h380be0", b"data[j]!==(j==4 ? 24'h380bf0 : j==5 ? 24'h380bd0 : 24'h380be0)", 1),
    (b'4 profiles 264 transactions each', b'6 profiles 264 transactions each; additional 320x240/1280x720 encoding cases', 1),
])
edit('simulate.py', [(b'1056', b'1584', 3)])
edit('build_later.py', [
    (b'== 1056', b'== 1584', 1),
])
