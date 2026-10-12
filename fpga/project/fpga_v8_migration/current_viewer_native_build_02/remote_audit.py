"""Read-only board metadata + snapshots confined to the isolated evidence root."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile

ROOT = Path.cwd().resolve()
assert ROOT.name.startswith("fpga_v8_viewer_binding_20261005"), ROOT


def dump(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2) + "\n")


def info(path):
    p = Path(path)
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
    return {"path": str(p), "realpath": str(p.resolve()), "bytes": p.stat().st_size,
            "sha256": h.hexdigest(), "symlink": os.readlink(p) if p.is_symlink() else None}


def command(args):
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return {"argv": args, "rc": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def ldd_paths(text):
    return {Path(p) for p in re.findall(r'(?:=>\s+|^\s*)(/[^\s()]+)', text, re.M) if Path(p).is_file()}


def copy_snapshot(paths, directory):
    entries = []
    for p in sorted(set(Path(p) for p in paths)):
        if not p.is_file(): continue
        record = info(p)
        dest = ROOT / directory / str(p).lstrip('/')
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Preserve exact target bytes and record source symlink separately.
        shutil.copyfile(p, dest)
        entries.append(record)
    dump(directory + '_manifest.json', entries)
    return entries


def preflight():
    queries = {
        "qmake_version": ['/usr/lib/qt5/bin/qmake', '-v'],
        "qmake_query": ['/usr/lib/qt5/bin/qmake', '-query'],
        "gcc_version": ['gcc', '-v'], "gxx_version": ['g++', '-v'],
        "gxx_search_dirs": ['g++', '-print-search-dirs'],
        "gxx_specs": ['g++', '-dumpspecs'],
        "pkg_opencv_version": ['pkg-config', '--modversion', 'opencv4'],
        "pkg_opencv_flags": ['pkg-config', '--cflags', '--libs', 'opencv4'],
        "ld_version": ['ld', '--version'], "make_version": ['make', '--version'],
        "uname": ['uname', '-a'], "ldconfig": ['/sbin/ldconfig', '-p'],
    }
    versions = {key: command(args) for key, args in queries.items()}
    dump('toolchain_versions.json', versions)
    # Allow-list compilation-relevant environment only; never include auth secrets.
    keys = ['PATH', 'LANG', 'LC_ALL', 'LC_CTYPE', 'LD_LIBRARY_PATH', 'LIBRARY_PATH',
            'CPATH', 'CPLUS_INCLUDE_PATH', 'C_INCLUDE_PATH', 'QMAKESPEC', 'QMAKEPATH',
            'PKG_CONFIG_PATH', 'QT_SELECT', 'SOURCE_DATE_EPOCH', 'CFLAGS', 'CXXFLAGS', 'LDFLAGS']
    dump('build_environment.json', {k: os.environ.get(k) for k in keys})
    tools = {Path(shutil.which(name)) for name in
             ['gcc', 'g++', 'as', 'ld', 'make', 'pkg-config', 'readelf', 'objdump', 'objcopy', 'ar']}
    tools.update([Path('/usr/lib/qt5/bin/qmake'), Path('/usr/lib/qt5/bin/moc')])
    for name in ['cc1plus', 'collect2', 'lto-wrapper', 'as', 'ld']:
        value = command(['g++', '-print-prog-name=' + name])['stdout'].strip()
        resolved = Path(value) if '/' in value else Path(shutil.which(value))
        tools.add(resolved)
    tool_dependencies = {}
    for p in sorted(tools):
        out = command(['ldd', str(p)])
        tool_dependencies[str(p)] = out
        tools |= ldd_paths(out['stdout'])
    dump('toolchain_runtime_ldd.json', tool_dependencies)
    copy_snapshot(tools, 'toolchain_snapshot')
    # These actual direct linker inputs are hashed before compiling. Full actual
    # link trace and transitive loader set are separately snapshotted afterward.
    libs = {}
    for name in ['librknnrt.so', 'librga.so']:
        path = command(['g++', '-print-file-name=' + name])['stdout'].strip()
        if Path(path).is_file(): libs[name] = info(path)
    dump('direct_accelerator_libraries_before.json', libs)
    print(json.dumps({'preflight': 'complete', 'toolchain_files': len(tools), 'accelerator_libraries': libs}))


def collect():
    rc = int((ROOT / 'build_return_code.txt').read_text().strip())
    products = {p.name: info(p) for p in sorted(ROOT.glob('*.o'))}
    if (ROOT/'detview-native-current-candidate').is_file(): products['detview-native-current-candidate'] = info(ROOT/'detview-native-current-candidate')
    dump('product_manifest.json', products)
    # GCC -MD gives the headers actually read for every compilation, including
    # system/SDK headers; do not infer these from project includes alone.
    dependencies = set()
    by_unit = {}
    for d in ROOT.glob('*.d'):
        text = d.read_text().replace('\\\n', ' ')
        names = text.split(':', 1)[1].split()
        paths = [str((ROOT/Path(n)).resolve()) if not n.startswith('/') else n for n in names]
        by_unit[d.name] = paths
        dependencies |= set(paths)
    dump('compiler_dependencies_by_unit.json', by_unit)
    dependency_records = copy_snapshot(dependencies, 'compiler_dependency_snapshot')
    log = (ROOT/'compile_link.log').read_text(errors='replace')
    linker_inputs = {Path(line.strip()) for line in log.splitlines()
                     if line.startswith('/') and Path(line.strip()).is_file()}
    # Linker trace includes system crt objects, archives, .so/linker-script files.
    link_records = copy_snapshot(linker_inputs, 'linker_input_snapshot')
    runtime = command(['ldd', str(ROOT/'detview-native-current-candidate')]) if rc == 0 else {}
    dump('candidate_runtime_ldd.json', runtime)
    runtime_records = copy_snapshot(ldd_paths(runtime.get('stdout','')), 'runtime_library_snapshot')
    elf = {}
    if rc == 0:
        for key, args in {
            'header': ['readelf','-h','detview-native-current-candidate'], 'sections': ['readelf','-SW','detview-native-current-candidate'],
            'dynamic': ['readelf','-dW','detview-native-current-candidate'], 'notes': ['readelf','-nW','detview-native-current-candidate'],
            'comment': ['readelf','-p','.comment','detview-native-current-candidate'],
            'symbols': ['readelf','-sW','detview-native-current-candidate'], 'disassembly': ['objdump','-d','detview-native-current-candidate'],
        }.items():
            out = command(args)
            (ROOT/('elf_'+key+'.txt')).write_text(out['stdout'] + out['stderr'])
            elf[key] = {'rc': out['rc'], 'file': 'elf_'+key+'.txt'}
    dump('elf_evidence.json', elf)
    archive_dirs = ['toolchain_snapshot', 'compiler_dependency_snapshot', 'linker_input_snapshot',
                    'runtime_library_snapshot']
    with tarfile.open(ROOT/'dependency_snapshots.tar.gz','w:gz') as tar:
        for name in archive_dirs: tar.add(ROOT/name, arcname=name)
    dump('snapshot_archive_identity.json', info(ROOT/'dependency_snapshots.tar.gz'))
    (ROOT/'rebuilt').mkdir(exist_ok=True)
    for name in products: shutil.copyfile(ROOT/name, ROOT/'rebuilt'/name)
    files = sorted(p.name for p in ROOT.iterdir() if p.is_file() and
                   (p.suffix in {'.json','.log','.txt','.d'} or
                    p.name in {'Makefile','Makefile.fresh','.qmake.stash','main.moc','moc_predefs.h',
                               'moc_calibration_capture.cpp','moc_vision_pipeline.cpp','dependency_snapshots.tar.gz'}))
    files += ['rebuilt/'+name for name in products]
    print(json.dumps({'build_return_code': rc, 'products': products, 'download_files': files,
                      'compiler_dependency_files': len(dependency_records),
                      'linker_input_files': len(link_records), 'runtime_library_files': len(runtime_records)}))


if __name__ == '__main__':
    {'preflight': preflight, 'collect': collect}[sys.argv[1]]()
