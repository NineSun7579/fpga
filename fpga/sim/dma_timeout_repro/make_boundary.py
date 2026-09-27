from pathlib import Path
import hashlib

p = Path(__file__).resolve().parent
base = (p / 'tb_frame_recovery.sv').read_bytes()
tail = (p / 'boundary_scenarios.sv').read_bytes()
out = base[:base.index(b' integer a,t,s;')].replace(b'module tb_frame_recovery;', b'module tb_frame_boundary;') + tail
def save(name, data):
    f = p / name
    if f.exists():
        backup = f.with_name(f.name + '.bak')
        if backup.exists():
            raise RuntimeError('Backup already exists: ' + str(backup))
        backup.write_bytes(f.read_bytes())
    f.write_bytes(data)
save('tb_frame_boundary.sv', out)
for vendor in (False, True):
    src = 'frame_recovery_vendor.do' if vendor else 'frame_recovery.do'
    data = (p / src).read_bytes().replace(b'work_vendor', b'work_boundary_vendor').replace(b'work_recovery', b'work_boundary')
    data = data.replace(b'tb_frame_recovery', b'tb_frame_boundary')
    save('boundary_vendor.do' if vendor else 'boundary.do', data)
sources = list((p.parents[1] / 'source').rglob('*.v'))
save('boundary_source_hashes.txt', ''.join(f'{hashlib.sha256(f.read_bytes()).hexdigest()} {f}\n' for f in sources).encode())
