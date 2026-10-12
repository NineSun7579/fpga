"""Private RK3568 PCIe exporter build only; never loads or unloads a module."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess


def sha(path):
    with Path(path).open('rb') as stream:
        h = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--headers', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if platform.machine() != 'aarch64' or platform.system() != 'Linux':
        raise RuntimeError('Real aarch64 Linux target required')
    headers, source, out = args.headers.resolve(), args.source.resolve(), args.out.resolve()
    if platform.release() != '6.1.99' or (headers/'include/config/kernel.release').read_text().strip() != platform.release():
        raise RuntimeError('Kernel/header release does not match the inspected 6.1.99 target')
    if not (source/'Makefile').is_file() or not (source/'pango_dma_candidate.c').is_file():
        raise RuntimeError('Complete immutable driver candidate required')
    out.mkdir(parents=True, exist_ok=False)
    receipt_path = out/'build_receipt.json'
    receipt = dict(status='building', scope='private_compile_only_no_module_load',
                   machine=platform.machine(), kernel_release=platform.release(),
                   proc_version=Path('/proc/version').read_text().strip(), header_root=str(headers),
                   source_directory=str(source), source_sha256={}, header_binding_sha256={}, compiler_tools={}, commands=[])

    def save():
        receipt_path.write_text(json.dumps(receipt, indent=2)+'\n')

    def run(label, command, cwd=None, timeout=180):
        item = dict(label=label, command=command, cwd=str(cwd or out))
        receipt['commands'].append(item)
        save()
        with (out/(label+'.stdout')).open('wb') as stdout, (out/(label+'.stderr')).open('wb') as stderr:
            result = subprocess.run(command, cwd=cwd or out, stdout=stdout, stderr=stderr, timeout=timeout)
        item.update(exit_code=result.returncode, stdout_sha256=sha(out/(label+'.stdout')), stderr_sha256=sha(out/(label+'.stderr')))
        save()
        print(json.dumps(dict(event=label, exit_code=result.returncode)), flush=True)
        if result.returncode:
            raise RuntimeError(label+' failed; retained stdout/stderr required for diagnosis')
        return (out/(label+'.stdout')).read_text(errors='replace').strip()

    try:
        for name in ('Makefile','.config','Module.symvers','include/generated/utsrelease.h',
                     'include/generated/autoconf.h','include/config/kernel.release','scripts/mod/modpost','scripts/basic/fixdep'):
            path = headers/name
            if not path.is_file():
                raise RuntimeError('Missing generated kernel build input: '+name)
            receipt['header_binding_sha256'][str(path)] = sha(path)
        config = (headers/'.config').read_text()
        if 'CONFIG_DMA_SHARED_BUFFER=y\n' not in config or 'CONFIG_MODULES=y\n' not in config:
            raise RuntimeError('Kernel DMA-BUF/module support missing')
        receipt['module_versioning_enabled'] = 'CONFIG_MODVERSIONS=y\n' in config
        private_source = out/'src'
        private_source.mkdir()
        for path in sorted(source.rglob('*')):
            if path.is_symlink():
                raise RuntimeError('Candidate source contains a symlink')
            if path.is_file():
                relative = path.relative_to(source)
                if path.suffix not in {'.c','.h'} and relative.as_posix() not in {'Makefile','Kbuild'}:
                    continue
                receipt['source_sha256'][relative.as_posix()] = sha(path)
                target = private_source/relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
        for name in ('gcc','make','ld','as','readelf','nm','modinfo'):
            tool = shutil.which(name)
            if not tool:
                raise RuntimeError('Missing target build tool '+name)
            resolved = str(Path(tool).resolve())
            receipt['compiler_tools'][name] = dict(path=resolved, sha256=sha(resolved))
        for program in ('cc1','collect2'):
            value = run('path_'+program, ['gcc','-print-prog-name='+program])
            tool = value if Path(value).is_absolute() else shutil.which(value)
            if not tool or not Path(tool).is_file():
                raise RuntimeError('Cannot bind compiler program '+program)
            resolved = str(Path(tool).resolve())
            receipt['compiler_tools'][program] = dict(path=resolved, sha256=sha(resolved))
        receipt['compiler_version'] = run('compiler_version', ['gcc','--version'])
        run('make', ['make','-C',str(headers),'M='+str(private_source),'V=1','modules'], timeout=300)
        module = private_source/'pango_dma_candidate.ko'
        if not module.is_file():
            raise RuntimeError('Expected private module was not produced')
        receipt['module_path'] = str(module)
        receipt['module_sha256'] = sha(module)
        receipt['vermagic'] = run('vermagic', ['modinfo','-F','vermagic',str(module)])
        if receipt['vermagic'].split()[0] != platform.release():
            raise RuntimeError('Compiled module vermagic differs from running release')
        receipt['modinfo'] = run('modinfo', ['modinfo',str(module)])
        run('elf_notes', ['readelf','-n',str(module)])
        run('undefined_symbols', ['nm','-u',str(module)])
        receipt['kernel_dependency_sha256'] = {}
        command_files = sorted(private_source.glob('.*.cmd'))
        if not command_files:
            raise RuntimeError('Kernel command/dependency receipts missing')
        receipt['kernel_command_file_sha256'] = {str(path):sha(path) for path in command_files}
        for path in command_files:
            content = path.read_text()
            for token in re.findall(r'(?m)^\s+([^\s\\]+)\s*\\?$',content):
                value = Path(token)
                candidate = value if value.is_absolute() else headers/value
                if candidate.is_file():
                    receipt['kernel_dependency_sha256'][str(candidate.resolve())] = sha(candidate)
        if not any(name.endswith('/include/linux/dma-buf.h') for name in receipt['kernel_dependency_sha256']):
            raise RuntimeError('Compiler dependency receipt does not bind the DMA-BUF API')
        for name,digest in receipt['header_binding_sha256'].items():
            if sha(name) != digest:
                raise RuntimeError('Kernel build input changed during private compilation')
        for name,digest in receipt['source_sha256'].items():
            if sha(source/name) != digest:
                raise RuntimeError('Candidate source changed during private compilation')
        receipt['status'] = 'private_module_compiled_no_load_or_hardware_validation'
    except BaseException as exc:
        receipt.update(status='failed', error=type(exc).__name__+': '+str(exc))
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
