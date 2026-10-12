"""Read-only check for compiler or extra RKNN jobs before a performance run."""
import json
from pathlib import Path
import shlex
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'project/tools'))
from board_host import ssh_connect

REMOTE = r'''
import json
from pathlib import Path
busy = []
for entry in Path('/proc').iterdir():
    if not entry.name.isdigit():
        continue
    try:
        name = (entry / 'comm').read_text().strip()
        args = (entry / 'cmdline').read_bytes().split(b'\0')
        compiler = name in {'make', 'cc1plus', 'cc1', 'clang', 'clang++', 'ld', 'ld.bfd', 'qmake'}
        harness = any(value in {b'--parity-selftest', b'--rotate-selftest'} for value in args)
        if compiler or harness:
            busy.append({'pid': int(entry.name), 'name': name, 'kind': 'compile' if compiler else 'extra_inference'})
    except (FileNotFoundError, ProcessLookupError):
        pass
print(json.dumps({'quiescent': not busy, 'busy': busy}))
'''
client = ssh_connect()
try:
    command = 'sudo -S -p \'\' python3 -c ' + shlex.quote(REMOTE)
    inp, out, err = client.exec_command(command, timeout=20)
    inp.write('123456\n'); inp.flush(); inp.channel.shutdown_write()
    text = out.read().decode('utf-8')
    if out.channel.recv_exit_status():
        raise RuntimeError(err.read().decode('utf-8', errors='replace'))
    result = json.loads(text)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result['quiescent'] else 2)
finally:
    client.close()
