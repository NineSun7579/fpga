"""Build a frozen native-I/O viewer on RK3568 and retain real compiler bindings."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import time


def sha(path):
    with Path(path).open('rb') as stream:
        h = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
        return h.hexdigest()


def save(path, data):
    Path(path).write_text(json.dumps(data, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--lib', type=Path, required=True)
    args = parser.parse_args()
    if platform.machine() != 'aarch64' or not (args.source / 'detview.pro').is_file():
        raise RuntimeError('Complete source and real aarch64 target required')
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    source = args.source.resolve()
    pinned = {p.relative_to(source).as_posix(): sha(p) for p in source.rglob('*') if p.is_file()}
    receipt = dict(status='building', source_sha256=pinned, runtime=str(args.lib.resolve()),
                   runtime_sha256=sha(args.lib), commands=[], hardware_test=False)
    def run(label, command):
        begin = time.monotonic()
        with (out / (label + '.stdout')).open('xb', buffering=0) as stdout, (out / (label + '.stderr')).open('xb', buffering=0) as stderr:
            result = subprocess.run([str(v) for v in command], cwd=out, stdout=stdout, stderr=stderr,
                                    check=False, timeout=900)
        receipt['commands'].append(dict(label=label, argv=[str(v) for v in command],
                                        returncode=result.returncode, elapsed_seconds=time.monotonic()-begin,
                                        stdout_sha256=sha(out/(label+'.stdout')), stderr_sha256=sha(out/(label+'.stderr'))))
        print(json.dumps(dict(event=label, returncode=result.returncode)), flush=True)
        if result.returncode:
            raise RuntimeError(label + ' failed; retained compiler log')
    try:
        for tool in ('qmake', 'g++', 'make'):
            found = shutil.which(tool)
            if not found:
                raise RuntimeError('Missing target compiler tool: ' + tool)
            receipt[tool] = dict(path=str(Path(found).resolve()), sha256=sha(Path(found).resolve()))
        for tool, query in [('qmake', '-v'), ('g++', '--version'), ('make', '--version')]:
            run('version_' + tool.replace('+', 'p'), [tool, query])
        for program in ('cc1plus', 'as', 'ld', 'collect2'):
            label = 'path_' + program
            run(label, ['g++', '-print-prog-name=' + program])
            found = (out/(label+'.stdout')).read_text().strip()
            path = Path(found) if Path(found).is_absolute() else Path(shutil.which(found) or found)
            if not path.is_file():
                raise RuntimeError('Compiler program cannot be bound: ' + program)
            receipt[program] = dict(path=str(path.resolve()), sha256=sha(path))
        run('qmake', ['qmake', str(source/'detview.pro'), 'QMAKE_CXXFLAGS+=-MD'])
        run('make', ['make', '-j2'])
        for name, digest in pinned.items():
            if sha(source/name) != digest:
                raise RuntimeError('Frozen source changed during build: ' + name)
        binary = out/'detview'
        receipt.update(binary=str(binary), executable_sha256=sha(binary), makefile_sha256=sha(out/'Makefile'),
                       object_sha256={p.name: sha(p) for p in out.glob('*.o')})
        dependencies = {}
        for dep in out.glob('*.d'):
            text = dep.read_text().replace('\\\n', ' ')
            for name in shlex.split(text.split(':', 1)[1]):
                path = Path(name)
                if not path.is_absolute():
                    path = out/path
                if path.is_file():
                    dependencies[str(path.resolve())] = sha(path)
        for path in [source/'hardware_inference.h', source/'native_adapter.h', source.parent/'sdk/rknn_api.h']:
            if dependencies.get(str(path.resolve())) != sha(path):
                raise RuntimeError('Compiler dependency files do not bind frozen ' + path.name)
        receipt['compiler_dependency_sha256'] = dependencies
        run('ldd', ['ldd', binary])
        libraries = {}
        for line in (out/'ldd.stdout').read_text().splitlines():
            for name in line.split():
                path = Path(name)
                if name.startswith('/') and path.is_file():
                    libraries[str(path.resolve())] = sha(path)
        if libraries.get(str(args.lib.resolve())) != receipt['runtime_sha256']:
            raise RuntimeError('Viewer links a different RKNN runtime')
        receipt['linked_library_sha256'] = libraries
        tests = []
        for option in ('--vision-selftest', '--camera-dma-selftest', '--dfl-selftest'):
            label = option[2:]
            run(label, [binary, option])
            tests.append(dict(option=option, exit_code=0, stdout_sha256=sha(out/(label+'.stdout')),
                              stderr_sha256=sha(out/(label+'.stderr'))))
        receipt.update(status='target_build_selftests_passed', tests=tests)
    except BaseException as exc:
        receipt.update(status='failed', error=type(exc).__name__+': '+str(exc))
        raise
    finally:
        save(out/'build_receipt.json', receipt)
    print(json.dumps(dict(event='build', executable_sha256=receipt['executable_sha256'],
                          status=receipt['status'], full_viewer_fps_claim=False)), flush=True)


if __name__ == '__main__':
    main()
