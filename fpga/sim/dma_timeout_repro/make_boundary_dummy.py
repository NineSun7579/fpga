from pathlib import Path
p=Path(__file__).resolve().parent
src=(p/'tb_frame_boundary.sv').read_bytes()
src=src.replace(b'module tb_frame_boundary;',b'module tb_frame_boundary_dummy;')
src=src.replace(b'for(extra=0;extra<=8;extra=extra+8)',b'for(extra=1;extra<=1;extra=extra+1)')
src=src.replace(b'for(kind=1;kind<=3;kind=kind+1)',b'for(kind=1;kind<=0;kind=kind+1)')
def new(name,data):
    f=p/name
    if f.exists():raise RuntimeError('Do not overwrite '+str(f))
    f.write_bytes(data)
new('tb_frame_boundary_dummy.sv',src)
for vendor in (False,True):
    suffix='_vendor' if vendor else ''
    data=(p/('boundary'+suffix+'.do')).read_bytes()
    data=data.replace(b'work_boundary',b'work_boundary_dummy').replace(b'tb_frame_boundary',b'tb_frame_boundary_dummy')
    new('boundary_dummy'+suffix+'.do',data)
