from pathlib import Path
import re
p=Path(r'gen_temp_20260920/project.pds')
b=p.read_bytes()
for name in (b'compile', b'synthesize', b'devmap', b'pnr'):
    pat=rb'(\(_command cmd_'+name+rb'.*?_gci_state \(_integer )0(\)\))'
    b,n=re.subn(pat, rb'\g<1>2\g<2>', b, count=1, flags=re.S)
    print(name,n)
p.write_bytes(b)
