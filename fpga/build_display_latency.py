"""Build isolated source on RK3568; never replace installed viewer."""
import hashlib
import json
from pathlib import Path
import shlex

import board_ssh

root = Path(__file__).resolve().parent / 'display_latency_delivery'
source = root / 'src'
remote = '/userdata/linaro/display-latency-delivery'
client = board_ssh.connect()
try:
    files = [path for path in source.iterdir() if path.is_file() and path.suffix in ('.cpp', '.h', '.pro')]
    if not any(path.name == 'main.cpp' for path in files):
        raise RuntimeError('Candidate main.cpp missing')
    staged = '/tmp/display-latency-source'
    rc, out, err = board_ssh.run(client, 'mkdir -p ' + staged)
    if rc:
        raise RuntimeError(out + err)
    with client.open_sftp() as stream:
        for path in files:
            stream.put(str(path), staged + '/' + path.name)
    command = ('cp ' + staged + '/* ' + remote + '/; cd ' + remote
               + '; qmake detview.pro && make -j2 >build_latency.log 2>&1')
    rc, out, err = board_ssh.run(client, command, sudo=True, timeout=600)
    root.mkdir(exist_ok=True)
    with client.open_sftp() as stream:
        stream.get(remote + '/build_latency.log', str(root / 'build_latency.log'))
        if rc == 0:
            stream.get(remote + '/detview', str(root / 'detview_aarch64'))
    result = {'return_code': rc, 'scope': 'isolated candidate, installed viewer untouched',
              'sources': {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}}
    if rc == 0:
        result['binary_sha256'] = hashlib.sha256((root / 'detview_aarch64').read_bytes()).hexdigest()
    (root / 'build_manifest.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    if rc:
        print((root / 'build_latency.log').read_text(errors='replace')[-10000:])
        raise SystemExit(rc)
finally:
    client.close()
