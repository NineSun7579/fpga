from pathlib import Path
import shutil
p=Path(__file__).resolve().parents[2]/'source/ov5640/ov5640_ddr/ov5640_ddr.v'
s=p.read_bytes()
a=b'if(dma_done || dma_abort) flush_count <= 4;'
b=b'if(dma_abort || (dma_done && (!frame_active || !frame_good))) flush_count <= 4;'
assert a in s
shutil.copyfile(p,p.with_name(p.name+'.flush_boundary.bak'))
p.write_bytes(s.replace(a,b))
