"""Read-only GBK-safe address/source audit; outputs only in this directory."""
from pathlib import Path
import re

here = Path(__file__).resolve().parent
frozen = here.parent.parent / 'whole_candidate_v7_route_01'
paths = [
    'rtl/ovreg_axil_decode_tc01.v',
    'rtl/fpga_v8_coop_axil_router.v',
    'rtl/fpga_v8_coop_axi128_endpoint.v',
    'rtl/fpga_v8_cooperative_top_v2_rfg01.v',
    'rtl/fpga_v8_capture_control_axil_arm_v2.v',
    'inputs/source/ov5640/ov5640_reg.v',
    'inputs/source/preprocess/prep_regs.v',
]
lines = ['Address evidence from frozen candidate; byte-level search.',
         'Proposed NEW exact decode: 0x20001000..0x200013ff.',
         'NOT reachable safely through the current low-bit decoder: upstream exact interception required.']
pattern = re.compile(rb'2000|4001|motion_.*page|motion_[aw][wr]|addr.*>=|ADDR_SEL_LSB|REG_.*BASE_ADDR', re.I)
for rel in paths:
    p = frozen / rel
    for i, line in enumerate(p.read_bytes().splitlines(), 1):
        if pattern.search(line):
            lines.append(f'{rel}:{i}: {line.decode("gbk", errors="replace")}')
conflicts = []
literal = re.compile(rb"32\s*'\s*h\s*([0-9a-fA-F_]+)")
for base in (frozen / 'rtl', frozen / 'inputs/source'):
    for p in base.rglob('*.v'):
        for m in literal.finditer(p.read_bytes()):
            n = int(m[1].replace(b'_', b''), 16)
            if 0x20001000 <= n <= 0x200013ff:
                conflicts.append(str(p))
lines.append(f'Existing literal assignments in proposed range: {len(conflicts)}')
lines.append('Literal absence alone is NOT a decode proof; legacy alias warning above is mandatory.')
assert not conflicts, conflicts
(here / 'address_audit.txt').write_text('\n'.join(lines) + '\n', encoding='utf8')
print(f'ADDRESS_AUDIT files={len(paths)} candidate_literal_conflicts=0; legacy alias requires NEW exact decoder')
