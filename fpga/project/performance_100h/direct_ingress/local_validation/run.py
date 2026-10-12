"""Local-only reproduction with complete logs and SHA-256 receipt."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import time

root = Path(__file__).resolve().parent
qt = Path('C:/Qt/6.11.1/mingw_64/bin')
gcc = Path('C:/Qt/Tools/mingw1310_64/bin')
env = dict(os.environ, PATH=str(qt) + os.pathsep + str(gcc) + os.pathsep + os.environ['PATH'])
build = root / 'build'
build.mkdir(exist_ok=True)
steps = [
    ('extract', [sys.executable, str(root / 'extract.py')], root, 15),
    ('qmake_version', [str(qt / 'qmake.exe'), '-v'], root, 15),
    ('gcc_version', [str(gcc / 'g++.exe'), '--version'], root, 15),
    ('qmake', [str(qt / 'qmake.exe'), str(root / 'gate_test.pro')], build, 30),
    ('make', [str(gcc / 'mingw32-make.exe'), '-j2'], build, 90),
    ('test', [str(build / 'release/gate_test.exe')], root, 45),
]
receipt = dict(started=time.strftime('%Y-%m-%dT%H:%M:%S%z'), steps=[])
for name, args, cwd, timeout in steps:
    result = subprocess.run(args, cwd=cwd, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=timeout)
    log = root / (name + '.log')
    log.write_bytes(result.stdout)
    receipt['steps'].append(dict(name=name, args=args, cwd=str(cwd),
                                exit_code=result.returncode,
                                log_sha256=hashlib.sha256(result.stdout).hexdigest()))
    print(name, 'exit=' + str(result.returncode), flush=True)
    if result.returncode:
        print(result.stdout.decode('utf-8', errors='replace'))
        break
receipt['files'] = {}
for path in sorted(root.iterdir()):
    if path.is_file() and path.name != 'receipt.json':
        receipt['files'][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
exe = build / 'release/gate_test.exe'
if exe.exists():
    receipt['files']['build/release/gate_test.exe'] = hashlib.sha256(exe.read_bytes()).hexdigest()
(root / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
sys.exit(result.returncode)
