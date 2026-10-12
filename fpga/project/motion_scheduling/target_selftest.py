"""Run receipt-pinned device-free target self-tests; never open camera DMA."""
import argparse
import json
from pathlib import Path
import shlex
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from board_host import ssh_connect

p = argparse.ArgumentParser()
p.add_argument('--build-receipt', required=True, type=Path)
a = p.parse_args()
r = json.loads(a.build_receipt.read_text())
assert r['status'] == 'built'
binary = r['binary']
tests = ['--motion-policy-selftest', '--vision-selftest', '--dfl-selftest',
         '--camera-dma-selftest', '--frame-metrics-selftest', '--lane-selftest']
client = ssh_connect()
results = []
try:
    _, out, err = client.exec_command('sha256sum ' + shlex.quote(binary), timeout=20)
    assert out.channel.recv_exit_status() == 0
    assert out.read().decode().split()[0] == r['binary_sha256']
    for test in tests:
        _, out, err = client.exec_command('QT_QPA_PLATFORM=offscreen ' + shlex.quote(binary) + ' ' + test + ' 2>&1', timeout=60)
        text = out.read().decode(errors='replace')
        code = out.channel.recv_exit_status()
        results.append(dict(test=test, exit_code=code, output=text))
        print(test, 'exit', code, text[-1200:], flush=True)
        if code:
            raise RuntimeError(test + ' failed')
finally:
    client.close()
    Path(__file__).with_name('target_selftest_result.json').write_text(json.dumps(dict(binary=binary,
        binary_sha256=r['binary_sha256'], results=results), indent=2), encoding='utf-8')
