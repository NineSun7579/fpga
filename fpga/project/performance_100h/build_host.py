"""Build an immutable source snapshot in a private RK3568 directory."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'project/tools'))
from board_host import ssh_connect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).parent / 'candidate/detview/src')
    args = parser.parse_args()
    source = args.source.resolve()
    files = sorted(path for path in source.rglob('*') if path.is_file())
    if not files or not (source / 'detview.pro').is_file():
        raise ValueError('Complete detview source required')
    blobs = {path.relative_to(source).as_posix(): path.read_bytes() for path in files}
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in blobs.items()}
    digest = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    remote = '/userdata/linaro/100h_performance/build_' + digest[:16]
    local = Path(__file__).parent / 'builds' / digest[:16]
    local.mkdir(parents=True, exist_ok=True)
    receipt = {'source': str(source), 'source_sha256': manifest, 'snapshot_sha256': digest,
               'remote_directory': remote, 'binary': remote + '/build/detview', 'status': 'pending'}
    for name, data in blobs.items():
        saved = local / 'source' / name
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_bytes(data)
    client = ssh_connect()
    try:
        command = ('test ! -e ' + shlex.quote(remote) + ' && mkdir -p ' + shlex.quote(remote + '/src') +
                   ' ' + shlex.quote(remote + '/build'))
        _, out, err = client.exec_command(command, timeout=20)
        if out.channel.recv_exit_status():
            raise RuntimeError('Private build directory already exists or cannot be created: ' + err.read().decode(errors='replace'))
        with client.open_sftp() as transfer:
            made = {remote + '/src'}
            for name, data in blobs.items():
                target = remote + '/src/' + name
                parent = str(Path(target).parent).replace('\\', '/')
                components = parent[len(remote + '/src'):].strip('/').split('/')
                current = remote + '/src'
                for component in components:
                    if component:
                        current += '/' + component
                        if current not in made:
                            transfer.mkdir(current)
                            made.add(current)
                with transfer.open(target, 'wb') as stream:
                    stream.write(data)
        command = ('cd ' + shlex.quote(remote + '/build') +
                   ' && qmake ../src/detview.pro INCLUDEPATH+=/userdata/linaro/detview-todo-work/sdk && make -j2')
        receipt['command'] = command
        _, out, err = client.exec_command(command + ' 2>&1', timeout=20)
        channel = out.channel
        channel.settimeout(20)
        deadline = time.monotonic() + 900
        with (local / 'build.log').open('wb') as logfile:
            while True:
                if time.monotonic() > deadline:
                    raise TimeoutError('Build deadline exceeded; remote process left for inspection')
                if channel.recv_ready():
                    logfile.write(channel.recv(65536))
                    logfile.flush()
                if channel.exit_status_ready() and not channel.recv_ready():
                    code = channel.recv_exit_status()
                    break
                time.sleep(.05)
        if code:
            raise RuntimeError('Build failed; inspect ' + str(local / 'build.log'))
        _, out, err = client.exec_command('sha256sum ' + shlex.quote(receipt['binary']), timeout=20)
        output = out.read().decode()
        if out.channel.recv_exit_status():
            raise RuntimeError('Built executable hash failed')
        receipt['binary_sha256'] = output.split()[0]
        receipt['status'] = 'built'
        receipt['build_log_sha256'] = hashlib.sha256((local / 'build.log').read_bytes()).hexdigest()
    except Exception as error:
        receipt.update(status='failed', error=str(error))
        raise
    finally:
        client.close()
        (local / 'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
