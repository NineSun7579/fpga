"""Upload isolated test sources and run temporary journal tests; no device I/O."""
import hashlib
import importlib.util
import json
from pathlib import Path
import posixpath
import shlex


def main():
    root = Path(__file__).resolve().parent
    evidence = root / 'artifacts'
    evidence.mkdir(exist_ok=False)
    helper_path = root.parents[1] / 'board_ssh.py'
    spec = importlib.util.spec_from_file_location('board_connection', helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    client = helper.connect()
    results = {'scope': 'Linux temporary test files only; no device opens/ioctls/resets/ARM',
               'sources': {name: hashlib.sha256((root/name).read_bytes()).hexdigest()
                           for name in ['allocate_epoch.py', 'selftest.py']}, 'status': 'incomplete'}
    try:
        code, output, error = helper.run(client, 'mktemp -d /userdata/linaro/fpga_v8_epoch_test_XXXXXX', timeout=20)
        if code:
            raise RuntimeError(error)
        remote = output.strip()
        if not remote.startswith('/userdata/linaro/fpga_v8_epoch_test_') or '\n' in remote:
            raise ValueError('unexpected isolated test directory')
        results['remote_directory'] = remote
        with client.open_sftp() as sftp:
            for name in results['sources']:
                sftp.put(str(root/name), posixpath.join(remote, name))
        command = 'cd ' + shlex.quote(remote) + ' && python3 selftest.py'
        code, output, error = helper.run(client, command, timeout=45)
        (evidence/'stdout.txt').write_text(output, encoding='utf-8')
        (evidence/'stderr.txt').write_text(error, encoding='utf-8')
        results.update(return_code=code, command=command,
                       status='pass' if code == 0 and 'Ran 8 tests' in error and '\nOK\n' in error else 'fail')
        print(results['status'], output, error)
        if results['status'] != 'pass':
            raise RuntimeError('Linux epoch allocator selftest failed')
    finally:
        (evidence/'results.json').write_text(json.dumps(results, indent=2)+'\n', encoding='utf-8')
        client.close()


if __name__ == '__main__':
    main()
