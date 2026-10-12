"""Read-only byte-level audit of admission and shared marker routing."""
from pathlib import Path

here = Path(__file__).resolve().parent
project = here.parent.parent
sections = {
    'source/sfp/sfp_rx_cam_if.v': [(38, 61), (71, 95), (122, 130)],
    'source/ov5640/ov5640_ddr/ov5640_ddr_w_en.v': [(41, 59), (88, 94)],
    'source/ov5640/ov5640_ddr/ov5640_ddr_w_ctrl.v':
        [(45, 58), (104, 132), (172, 184), (237, 249)],
    'source/ov5640/ov5640_ddr/ov5640_ddr.v': [(70, 82), (115, 139)],
    'source/top.v': [(1761, 1776), (1782, 1805), (1863, 1886)]}
out = []
for name, ranges in sections.items():
    lines = (project / name).read_bytes().splitlines()
    out.append(name)
    for lo, hi in ranges:
        out.extend(f'{i}: {lines[i-1].decode("ascii", errors="replace")}'
                   for i in range(lo, hi+1))
(here / 'source_audit.log').write_bytes(('\n'.join(out)+'\n').encode('ascii', errors='replace'))
print('Read-only source audit saved inside experiment directory')
