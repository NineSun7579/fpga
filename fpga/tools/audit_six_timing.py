"""Reject implementation summaries with missing clocks or violated constraints."""
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_bytes().decode('ascii', errors='replace')
if 'Design Summary : All Constraints Met.' not in text:
    print('FAIL: implementation does not meet all timing constraints')
    raise SystemExit(1)
for clock in ('sfp_fabric', 'cam1_sccb', 'cam2_sccb', 'cam3_sccb', 'cam4_sccb'):
    if not any(line.split()[:2] == [clock, clock] for line in text.splitlines()):
        print('FAIL: clock absent from timing summary:', clock)
        raise SystemExit(1)
print('PASS: all reported constraints met; SFP and four SCCB clocks included')
