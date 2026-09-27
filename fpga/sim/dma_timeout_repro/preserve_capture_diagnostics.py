from pathlib import Path
import shutil
p=Path(__file__).resolve().parents[2]/'source/ov5640/ov5640_ddr/ov5640_ddr_w.v'
s=p.read_bytes()
pos=s.index(b'// [ZDIAG 2026-09-18] zero-beat accounting')
tail=s[pos:]
assert b'if (local_rst)' in tail
tail=tail.replace(b'if (local_rst)',b'if (axi_rst)')
head=s[:pos].replace(b'//     if(local_rst)',b'//     if(axi_rst)')
backup=p.with_name(p.name+'.diagnostics.bak');assert not backup.exists()
shutil.copyfile(p,backup)
p.write_bytes(head+tail)
print('Kept debug zero counters latched across local capture flush; valid pipeline reset unchanged')
