"""Compile the isolated driver against the board's matching kernel; do not load."""
from pathlib import Path
import hashlib
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_ssh

root = Path(__file__).resolve().parent
source = root / 'driver'
files = [p for p in source.rglob('*') if p.is_file() and
         (p.suffix in ('.c', '.h') or p.name == 'Makefile')]
if not any(p.name == 'Makefile' for p in files):
    raise RuntimeError('Isolated driver Makefile not yet available')
remote = '/userdata/linaro/fpga-zero-copy-driver-stage'
client = board_ssh.connect()
try:
    rc, out, err = board_ssh.run(client, 'mkdir -p ' + remote)
    if rc:
        raise RuntimeError(out + err)
    with client.open_sftp() as sftp:
        for path in files:
            relative = path.relative_to(source).as_posix()
            if '/' in relative:
                folder = remote + '/' + relative.rsplit('/', 1)[0]
                rc, out, err = board_ssh.run(client, 'mkdir -p ' + folder)
                if rc:
                    raise RuntimeError(out + err)
            sftp.put(str(path), remote + '/' + relative)
    rc, out, err = board_ssh.run(client,
        'test "$(uname -r)" = "$(cat /usr/src/linux-headers-6.1-rockchip/include/config/kernel.release)" '
        '&& make -C /usr/src/linux-headers-6.1-rockchip M=' + remote + ' modules', timeout=120)
    (root / 'driver_build.log').write_text(out + err, encoding='utf-8')
    receipt = {'return_code': rc, 'scope': 'compiled only, loaded driver untouched',
               'sources': {p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    if rc == 0:
        with client.open_sftp() as sftp:
            modules = [entry for entry in sftp.listdir(remote) if entry.endswith('.ko')]
            for name in modules:
                target = root / name
                sftp.get(remote + '/' + name, str(target))
                receipt.setdefault('modules', {})[name] = hashlib.sha256(target.read_bytes()).hexdigest()
    (root / 'driver_build_manifest.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(out + err)
    print(json.dumps(receipt, indent=2))
    if rc:
        raise SystemExit(rc)
finally:
    client.close()
