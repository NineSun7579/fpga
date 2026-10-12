"""Authoritative recovery supervisor; completion yields tool notification."""
import argparse
from pathlib import Path
import json
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--placement-seed', type=int, default=1)
    args = parser.parse_args()
    assert args.placement_seed >= 0
    stamp = time.strftime('%Y%m%d_%H%M%S')
    receipt_path = HERE / ('recovery_launch_' + stamp + '.json')
    log_path = HERE / ('recovery_launch_' + stamp + '.log')
    receipt = dict(status='starting', stage='preflight_or_lock',
                   started=time.strftime('%Y-%m-%d %H:%M:%S'), log=str(log_path),
                   command=[sys.executable, '-u', '-B', str(HERE / 'build_later.py'), '--run', '--placement-seed', str(args.placement_seed)])
    def save():
        receipt_path.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
        (HERE / 'recovery_launch_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    save()
    code = 1
    try:
        with log_path.open('xb') as log:
            process = subprocess.Popen(receipt['command'], cwd=HERE, shell=False,
                                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            receipt.update(status='running', supervisor_child_pid=process.pid)
            save()
            for line in iter(process.stdout.readline, b''):
                log.write(line)
                log.flush()
                print(line.decode('gb18030', errors='replace').rstrip(), flush=True)
            code = process.wait()
        current = json.loads((HERE / 'current_run.json').read_text())
        if current.get('started', '') >= receipt['started']:
            receipt.update(build=current, stage=current.get('stage'), error=current.get('error'))
        elif code:
            receipt['error'] = 'Preflight or lock failed; see recovery launch log'
    except Exception as error:
        receipt['error'] = str(error)
        print('RECOVERY_SUPERVISOR_ERROR', str(error), flush=True)
    finally:
        receipt.update(status='finished' if code == 0 else 'failed', returncode=code,
                       finished=time.strftime('%Y-%m-%d %H:%M:%S'))
        save()
        print('AUTHORITATIVE_RECOVERY_FINISHED', receipt['status'], receipt['finished'], receipt_path, flush=True)
    sys.exit(code)

if __name__ == '__main__':
    main()
