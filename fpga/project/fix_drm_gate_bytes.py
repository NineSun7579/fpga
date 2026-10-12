from pathlib import Path
import hashlib
root = Path(__file__).parent
p = root / 'source/ov5640/ov5640_ddr/ov5640_ddr_w.v'
old = b'wire rd_en_drm = !(almost_full_drm | empty_drm | almost_full_out);'
new = b'wire rd_en_drm = !(empty_drm | almost_full_out);'
backup = p.with_name(p.name + '.bak_drm_gate')
data = p.read_bytes()
assert data.count(old) == 1, 'Expected exactly one original expression'
with backup.open('xb') as f:
    f.write(data)
assert backup.read_bytes() == data
p.write_bytes(data.replace(old, new, 1))
assert p.read_bytes() == backup.read_bytes().replace(old, new, 1)
print('BACKUP', backup)
print('SHA256 before', hashlib.sha256(data).hexdigest())
print('SHA256 after ', hashlib.sha256(p.read_bytes()).hexdigest())
print('PASS: sole byte replacement; original encoding and line endings preserved')
