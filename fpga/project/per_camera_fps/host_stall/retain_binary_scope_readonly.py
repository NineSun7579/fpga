"""Retain disassembly from the pinned original binary; never executes it."""
import json
import pathlib
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'tools'))
from board_host import ssh_connect

PIN = '0d717a430e46e13d61553bf74c5ea7f13aff5c69db8587136aa227b5705ad153'
EXE = '/userdata/linaro/detview-calibration-work/build/detview'

def main():
    client = ssh_connect()
    def run(command):
        _, out, err = client.exec_command(command, timeout=20)
        text, error = out.read().decode(), err.read().decode()
        if error: raise RuntimeError(error)
        return text
    try:
        before = run('sudo -n sha256sum ' + EXE).split()[0]
        if before != PIN: raise RuntimeError('Original binary hash changed')
        result = {'exe': EXE, 'sha256_before': before, 'scopes': {}}
        for name, start, end in [('ioctl_and_camera', '0x1e710', '0x1ed00'),
                                 ('worker', '0x256a0', '0x26d00')]:
            result['scopes'][name] = run('sudo -n objdump -d -C --start-address=' + start +
                ' --stop-address=' + end + ' ' + EXE)
        result['sha256_after'] = run('sudo -n sha256sum ' + EXE).split()[0]
        if result['sha256_after'] != PIN: raise RuntimeError('Original binary changed during read')
        pathlib.Path(__file__).with_name('original_binary_scopes.json').write_text(
            json.dumps(result, indent=2), encoding='utf-8')
        print('Pinned original disassembly retained; SHA256 stable', flush=True)
    finally:
        client.close()

if __name__ == '__main__':
    main()
