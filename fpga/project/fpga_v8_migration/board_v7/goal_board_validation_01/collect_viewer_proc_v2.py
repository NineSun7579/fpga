"""Run manually on RK only after authorized programming/viewer start.

Read-only /proc/files collector, no SSH, no device open, no process control.
This file was prepared offline; its existence is not actual board evidence.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--host', required=True, help='RK address used by screenshot collector')
    parser.add_argument('--model', action='append', required=True, help='Actual absolute loaded model path; repeat')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    proc = Path('/proc') / str(args.pid)
    stat = (proc / 'stat').read_text()
    exe = os.readlink(proc / 'exe')
    doc = {'contract': 'viewerProcSnapshot/v1', 'pid': args.pid, 'exe': exe,
           'exe_sha256': digest(proc / 'exe'), 'cmdline_hex': (proc / 'cmdline').read_bytes().hex(),
           'proc_stat': stat, 'clk_tck': os.sysconf('SC_CLK_TCK'),
           'boot_unix': int(next(line.split()[1] for line in Path('/proc/stat').read_text().splitlines()
                                 if line.startswith('btime '))),
           'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
           'board_id': Path('/etc/machine-id').read_text().strip(), 'host': args.host,
           'models': {str(Path(p).resolve(strict=True)): digest(p) for p in args.model},
           'captured_utc': datetime.now(timezone.utc).isoformat()}
    if (proc / 'stat').read_text().rsplit(')', 1)[1].split()[19] != stat.rsplit(')', 1)[1].split()[19]:
        raise ValueError('Viewer replaced during capture')
    args.output.write_text(json.dumps(doc, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
