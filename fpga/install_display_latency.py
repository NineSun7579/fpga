"""Install validated default-enabled candidate with identity checks and original backup."""
import json
from pathlib import Path
import shlex

import board_ssh

root = Path(__file__).resolve().parent / 'display_latency_delivery'
manifest = json.loads((root / 'build_manifest.json').read_text())
if manifest['return_code'] != 0:
    raise RuntimeError('Build failed')
expected = manifest['binary_sha256']
original = '73613d525541939ea493a9bb87eeeae10879c4a08eede36a7ee298777fb32100'
installed = '/userdata/detview-hdmifull/detview-hdmifull'
candidate = '/userdata/linaro/display-latency-delivery/detview'
backup = installed + '.before-latency-fix-20261008'
client = board_ssh.connect()
try:
    for path, digest in [(installed, original), (candidate, expected)]:
        rc, out, err = board_ssh.run(client, 'sha256sum ' + shlex.quote(path), sudo=True)
        if rc or out.split()[0] != digest:
            raise RuntimeError('Unexpected file identity: ' + path)
    command = ('cd /userdata/linaro/display-latency-delivery; '
               'QT_QPA_PLATFORM=offscreen ./detview --display-latency-selftest && '
               'QT_QPA_PLATFORM=offscreen ./detview --vision-selftest && '
               'QT_QPA_PLATFORM=offscreen ./detview --mvp-round1-selftest')
    rc, out, err = board_ssh.run(client, command, sudo=True, timeout=60)
    (root / 'final_selftest.log').write_text(out + err, encoding='utf-8')
    if rc:
        raise RuntimeError('Final selftests failed: ' + out + err)
    rc, out, err = board_ssh.run(client,
        'pkill -x detview; pkill -x detview-hdmiful; sleep 1; fuser /dev/pango_pci_driver', sudo=True)
    if out.strip() or 'pango_pci_driver:' in err:
        raise RuntimeError('DMA still owned')
    command = ('test ! -e ' + backup + ' && cp -p ' + installed + ' ' + backup
               + ' && cp ' + candidate + ' ' + installed + '.latency-new'
               + ' && chmod 755 ' + installed + '.latency-new'
               + ' && mv ' + installed + '.latency-new ' + installed)
    rc, out, err = board_ssh.run(client, command, sudo=True)
    if rc:
        raise RuntimeError('Install failed: ' + out + err)
    command = ('cd /userdata/detview-hdmifull; setsid nohup env DISPLAY=:0 '
               'XAUTHORITY=/var/run/lightdm/root/:0 QT_QPA_PLATFORM=xcb QT_XCB_GL_INTEGRATION=xcb_egl '
               'DET_BENCH=1 ./detview-hdmifull --model MVP_accuracy_round1 --fullscreen '
               '>/userdata/linaro/display-latency-delivery/final_acceptance.log 2>&1 </dev/null & echo $!')
    rc, out, err = board_ssh.run(client, command, sudo=True)
    if rc:
        raise RuntimeError('Launch failed: ' + out + err)
    result = {'installed_sha256': expected, 'backup': backup, 'backup_sha256': original,
              'launch_pid': out.strip(), 'default_late_latch': True,
              'acceptance_pending': True}
    (root / 'installation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
finally:
    client.close()
