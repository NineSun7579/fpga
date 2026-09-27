from pathlib import Path
import hashlib
p=Path(__file__).resolve().parent
lines=[b'Boundary evidence: all four simulations completed; 432 cases total.\n']
for name in ('boundary_behavior.log','boundary_vendor.log','boundary_dummy_behavior.log','boundary_dummy_vendor.log'):
    data=(p/name).read_bytes()
    assert b'BOUNDARY SUMMARY' in data and b'** Fatal:' not in data
    lines.append(b'\nFILE '+name.encode()+b' SHA256 '+hashlib.sha256(data).hexdigest().encode()+b'\n')
    lines.extend(x+b'\n' for x in data.splitlines() if b'BOUNDARY SUMMARY' in x or b'BAD_PUBLISHED' in x or b'Errors:' in x)
    if name=='boundary_dummy_vendor.log':
        lines.append(b'\nVendor quota+1 case 21 exact trace:\n')
        lines.extend(x+b'\n' for x in data.splitlines() if b'case=21 ' in x)
rows=(p/'boundary_source_hashes.txt').read_bytes().splitlines()
changed=[r for r in rows if hashlib.sha256(Path(r[65:].decode()).read_bytes()).hexdigest().encode()!=r[:64]]
assert not changed
lines.append(f'\nFinal source hash audit: {len(rows)} files checked, zero changed.\n'.encode())
out=p/'boundary_evidence.txt'
assert not out.exists()
out.write_bytes(b''.join(lines))
print(b''.join(x for x in lines if b'BOUNDARY SUMMARY' in x or b'Final source' in x).decode())
