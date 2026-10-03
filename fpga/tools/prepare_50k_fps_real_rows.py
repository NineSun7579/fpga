"""Isolated merge candidate that waits for real rows from both cameras."""
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'project/sim/fps50k_merge'
DEST = ROOT / 'project/sim/fps50k_real_rows'
DEST.mkdir(exist_ok=True)
for name in ['cmos_8_16bit.v','video_async_fifo.v','tb_merge_rows.sv','run.do']:
    shutil.copy2(SRC / name, DEST / name)
data = (SRC / 'cam2_merge.v').read_bytes()
old = b'if (a_ready[a_cur]) begin'
assert data.count(old) == 1
data = data.replace(old,b'if (a_ready[a_cur] && b_ready[b_cur]) begin')
data, count = re.subn(rb'if \(b_ready\[b_cur\]\) b_rep <= `UD 1\x27b0;\s*else\s+b_rep <= `UD 1\x27b1;[^\r\n]*',
                       b'b_rep <= `UD 1\x27b0; // both real rows ready before A starts', data)
assert count == 1
(DEST / 'cam2_merge.v').write_bytes(data)
print(DEST)
