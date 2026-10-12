"""Build/run pure background reader tests on ARM64 without opening the driver."""
from pathlib import Path
import hashlib
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_ssh

root = Path(__file__).resolve().parent
remote = '/userdata/linaro/fpga-background-reader-selftest'
sources = ['background_thumbnail_reader.hpp', 'background_thumbnail_reader_selftest.cpp']
client = board_ssh.connect()
try:
    rc, out, err = board_ssh.run(client, 'mkdir -p ' + remote)
    if rc:
        raise RuntimeError(out + err)
    hashes = {}
    with client.open_sftp() as sftp:
        for name in sources:
            local = root / 'host' / name
            hashes[name] = hashlib.sha256(local.read_bytes()).hexdigest()
            sftp.put(str(local), remote + '/' + name)
    command = ('cd ' + remote + ' && g++ -std=c++17 -Wall -Wextra -Werror '
               'background_thumbnail_reader_selftest.cpp -o reader_selftest '
               '&& ./reader_selftest')
    rc, out, err = board_ssh.run(client, command, timeout=90)
    (root / 'background_host_target_selftest.log').write_text(out + err, encoding='utf-8')
    evidence = {'return_code': rc, 'sources': hashes, 'remote': remote,
                'scope': 'pure ARM64 fake-transport tests; no device or viewer access',
                'passed': rc == 0 and 'PASS 128 meaningful adversarial tests' in out}
    (root / 'background_host_target_manifest.json').write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence, indent=2))
    print(out + err)
    if not evidence['passed']:
        raise RuntimeError('ARM64 background reader verification failed')
finally:
    client.close()
