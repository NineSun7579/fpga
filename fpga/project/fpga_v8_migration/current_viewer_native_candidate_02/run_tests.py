"""Local pure C++ tests only. Does not import remote/build/device workflows."""
from pathlib import Path
import json
import subprocess
HERE = Path(__file__).resolve().parent
def main():
    artifacts = HERE / 'artifacts'
    artifacts.mkdir(exist_ok=True)
    results = {}
    for name, command in [
        ('compile', ['cmd', '/c', 'build_native_guard_selftest.cmd']),
        ('selftest', [str(artifacts / 'native_guard_selftest.exe'), 'recorded_profile.txt']),
        ('audit', ['python', 'audit.py'])]:
        p = subprocess.run(command, cwd=HERE, capture_output=True)
        (artifacts / (name + '.txt')).write_bytes(p.stdout + p.stderr)
        results[name] = {'returncode': p.returncode}
        print(name, p.returncode)
        if p.returncode:
            print((p.stdout + p.stderr).decode(errors='replace'))
            break
    (artifacts / 'results.json').write_text(json.dumps(results, indent=2)+'\n')
    assert len(results) == 3 and all(x['returncode'] == 0 for x in results.values())
if __name__ == '__main__': main()
