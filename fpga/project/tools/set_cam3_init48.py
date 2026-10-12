from pathlib import Path
from datetime import datetime

root = Path(__file__).resolve().parents[1]
stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
changes = {
    'source/ov5640/ov5640_top.v': [
        (b'    parameter DATA_WIDTH = 16,', b"    parameter [7:0] SENSOR_PLL_MULT = 8'h54,\n    parameter DATA_WIDTH = 16,"),
        (b'    ov5640 #(', b'    ov5640 #(\n        .SENSOR_PLL_MULT(SENSOR_PLL_MULT),'),
    ],
    'source/ov5640/ov5640/ov5640.v': [
        (b'    parameter   DATA_WIDTH = 16,', b"    parameter [7:0] SENSOR_PLL_MULT = 8'h54,\n    parameter   DATA_WIDTH = 16,"),
        (b'ov5640_i2c_rgb565_cfg #( ', b'UNUSED'),
    ],
    'source/ov5640/ov5640/ov5640_i2c_rgb565_cfg.v': [
        (b'module ov5640_i2c_rgb565_cfg #(', b"module ov5640_i2c_rgb565_cfg #(\n      parameter [7:0] SENSOR_PLL_MULT = 8'h54,"),
        (b"{16'h3036,8'h54}", b"{16'h3036,SENSOR_PLL_MULT}"),
    ],
    'source/top.v': [
        (b"    .BASE_ADDR       (32'h2000_0400),", b"    .BASE_ADDR       (32'h2000_0400),\n    .SENSOR_PLL_MULT (8'h30), // cam3: initialize PLL for 48 MHz PCLK"),
    ],
}
changes['source/ov5640/ov5640/ov5640.v'][1] = (
    b'ov5640_i2c_rgb565_cfg #(',
    b'ov5640_i2c_rgb565_cfg #(\n    .SENSOR_PLL_MULT(SENSOR_PLL_MULT),')
prepared = []
for rel, replacements in changes.items():
    path = root / rel
    original = path.read_bytes()
    newline = b'\r\n' if b'\r\n' in original else b'\n'
    data = original
    for old, new in replacements:
        assert data.count(old) == 1, (rel, old, data.count(old))
        data = data.replace(old, new.replace(b'\n', newline), 1)
    prepared.append((path, original, data))
for path, original, data in prepared:
    path.with_name(path.name + '.' + stamp + '.bak').write_bytes(original)
    path.write_bytes(data)
    print('Updated:', path.relative_to(root))
