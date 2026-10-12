"""Authoritative foreground build supervisor, launched by the tool as background."""
from pathlib import Path
import json
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent

def save(row):
    (HERE / 'launch_receipt.json').write_text(json.dumps(row, indent=2) + '\n', encoding='utf-8')

def main():
    receipt = dict(status='starting', started=time.strftime('%Y-%m-%d %H:%M:%S'),
                   command=[sys.executable, '-u', '-B', str(HERE / 'build_later.py'), '--run'])
    save(receipt)
    with (HERE / 'launch.log').open('xb') as log:
        process = subprocess.Popen(receipt['command'], cwd=HERE, shell=False, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        receipt.update(status='running', supervisor_child_pid=process.pid)
        save(receipt)
        for line in iter(process.stdout.readline, b''):
            log.write(line)
            log.flush()
            print(line.decode('gb18030', errors='replace').rstrip(), flush=True)
        code = process.wait()
    receipt.update(status='finished' if code == 0 else 'failed', returncode=code,
                   finished=time.strftime('%Y-%m-%d %H:%M:%S'))
    current = HERE / 'current_run.json'
    if current.exists():
        receipt['build'] = json.loads(current.read_text())
    elif code:
        receipt['error_stage'] = 'preflight_or_lock'
        receipt['error'] = 'See launch.log for explicit guard/preflight failure'
    save(receipt)
    print('AUTHORITATIVE_BUILD_FINISHED', receipt['status'], receipt['finished'], HERE / 'launch_receipt.json', flush=True)
    sys.exit(code)

if __name__ == '__main__':
    main()
