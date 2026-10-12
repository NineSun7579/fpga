"""Build the real RK3568 paired benchmark; never open hardware or execute it."""
import hashlib
import json
from pathlib import Path
import re
import shlex
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_ssh

root = Path(__file__).resolve().parent
source = root.parent / 'fpga_acceleration_delivery/ddr_rgb_letterbox/host/paired_preprocess.cpp'
provider = source.parent / 'linux_provider.cpp'
migration = Path('D:/race/ov56401/project/fpga_v8_migration')
sdk = migration.parent / 'hardware_acceleration/rknn_io/prepared/sdk'
search = [migration, sdk]
remote = '/tmp/fpga_accel_host_compile_20261008'
pending, contents = [source, provider], {}
while pending:
    path = pending.pop().resolve()
    if path in contents:
        continue
    data = path.read_bytes()
    contents[path] = data
    for name in re.findall(rb'^\s*#\s*include\s*"([^"\r\n]+)"', data, re.M):
        candidates = [path.parent / name.decode()] + [folder / name.decode() for folder in search]
        found = next((item.resolve() for item in candidates if item.is_file()), None)
        if found is None:
            raise RuntimeError(f'Missing quoted include {name!r} from {path}')
        pending.append(found)

def target(path):
    return remote + '/' + path.resolve().as_posix().replace(':', '')

client = board_ssh.connect()
try:
    directories = sorted({str(Path(target(path)).parent).replace('\\', '/') for path in contents})
    rc, out, err = board_ssh.run(client, 'mkdir -p ' + ' '.join(map(shlex.quote, directories)))
    if rc:
        raise RuntimeError(out + err)
    with client.open_sftp() as stream:
        for path, data in contents.items():
            with stream.open(target(path), 'wb') as handle:
                handle.write(data)
    command = ('g++ -std=c++17 -O2 -fPIC -Wall -Wextra -Werror '
               + ' '.join('-I' + shlex.quote(target(folder)) for folder in search)
               + ' ' + shlex.quote(target(source)) + ' ' + shlex.quote(target(provider))
               + ' $(pkg-config --cflags --libs Qt5Core) -L/usr/lib -Wl,-rpath,/usr/lib -lrknnrt -ldl -pthread -o '
               + shlex.quote(remote + '/paired_preprocess'))
    rc, out, err = board_ssh.run(client, command, timeout=120)
    (root / 'fpga_host_compile.log').write_text(out + err, encoding='utf-8')
    result = {'return_code': rc, 'command': command,
              'scope': 'actual board compiler, Linux provider and Qt/RKNN runtime linked; no DMA or inference execution',
              'sources': {str(path): hashlib.sha256(data).hexdigest() for path, data in contents.items()}}
    if rc == 0:
        binary = root / 'paired_preprocess_aarch64'
        with client.open_sftp() as stream:
            stream.get(remote + '/paired_preprocess', str(binary))
        result['binary_sha256'] = hashlib.sha256(binary.read_bytes()).hexdigest()
    (root / 'fpga_host_compile.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'return_code': rc, 'files': len(contents), 'output': out + err}, indent=2))
    if rc:
        raise SystemExit(rc)
finally:
    client.close()
