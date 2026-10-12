from pathlib import Path
from datetime import datetime

stamp=datetime.now().strftime('%Y%m%d_%H%M%S')
for name,expected in [('ov5640.fdc',6),('clock.fdc',3)]:
    p=Path('source/constraints')/name
    b=p.read_bytes()
    p.with_name(p.name+'.bak_cam3confirmed_'+stamp).write_bytes(b)
    lines=b.splitlines(keepends=True)
    n=0
    for i,line in enumerate(lines):
        if b'cmos3' in line and line.startswith(b'#') and not line.startswith(b'##'):
            lines[i]=line[1:]
            n+=1
    assert n==expected,(name,n)
    p.write_bytes(b''.join(lines))
    print(name,'restored',n,'lines; user confirmed full pin mapping')
