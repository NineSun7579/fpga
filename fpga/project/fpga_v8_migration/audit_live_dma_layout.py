"""Read-only process/module identity and existing DMA mapping inventory.

Never opens /dev/pango_pci_driver or issues ioctls. A mapping is not an
exclusive reservation, and an on-disk module hash is not a loaded-code hash.
"""
import argparse
import importlib.util
import json
from pathlib import Path

REMOTE_PROBE = r'''python3 - <<'PY'
import glob, hashlib, json, os
from pathlib import Path

def text(path):
    try:
        return Path(path).read_text().strip()
    except (OSError, UnicodeError):
        return None

viewers, owners = [], []
for root in glob.glob('/proc/[0-9]*'):
    try:
        exe = os.readlink(root + '/exe')
        fds = []
        for fd in glob.glob(root + '/fd/*'):
            try:
                target = os.readlink(fd)
                if target.startswith('/dev/pango'):
                    fds.append({'fd': int(fd.rsplit('/', 1)[1]), 'target': target})
            except OSError:
                pass
        if not fds and 'detview' not in exe and 'camview' not in exe:
            continue
        stat = Path(root + '/stat').read_text()
        start = stat[stat.rfind(')')+2:].split()[19]
        maps = []
        libraries = []
        for line in Path(root + '/maps').read_text().splitlines():
            fields = line.split(None, 5)
            if len(fields) != 6:
                continue
            if fields[5].startswith('/dev/pango'):
                lo, hi = (int(v, 16) for v in fields[0].split('-'))
                maps.append({'address_range': fields[0], 'bytes': hi-lo,
                    'permissions': fields[1], 'file_offset': int(fields[2], 16),
                    'device': fields[3], 'inode': fields[4], 'path': fields[5]})
            elif 'librknnrt' in fields[5]:
                libraries.append(fields[5])
        row = {'pid': int(root.rsplit('/', 1)[1]), 'starttime': start,
            'exe': exe, 'exe_sha256': hashlib.sha256(Path(root+'/exe').read_bytes()).hexdigest(),
            'argv': [v.decode(errors='replace') for v in Path(root+'/cmdline').read_bytes().split(b'\0') if v],
            'driver_fds': fds, 'dma_mappings': maps,
            'rknn_library_paths': sorted(set(libraries))}
        if fds:
            owners.append(row)
        if 'detview' in exe or 'camview' in exe:
            viewers.append(row)
    except (OSError, ProcessLookupError, IndexError):
        continue

module_root = '/sys/module/pango_pci_driver/'
modules = {'name': 'pango_pci_driver',
    'sysfs_version': text(module_root+'version'),
    'sysfs_srcversion': text(module_root+'srcversion'),
    'sysfs_refcount': text(module_root+'refcnt'),
    'proc_modules_line': next((line for line in (text('/proc/modules') or '').splitlines()
        if line.startswith('pango_pci_driver ')), None)}
print(json.dumps({'read_only': True, 'boot_id': text('/proc/sys/kernel/random/boot_id'),
    'viewers': viewers, 'driver_owners': owners, 'module': modules,
    'limits': ['Mappings do not establish exclusive ownership or kernel allocation identity',
               'No endpoint control register or device file was accessed',
               'No conclusion about loaded FPGA bitstream identity']}, indent=2))
PY'''


def main(destination):
    if destination.exists():
        raise FileExistsError("Refusing to overwrite retained board evidence")
    helper_path = Path(__file__).resolve().parents[1] / "board_ssh.py"
    spec = importlib.util.spec_from_file_location("board_connection", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    client = helper.connect()
    try:
        code, output, error = helper.run(client, REMOTE_PROBE, timeout=30, sudo=True)
        if code:
            raise RuntimeError("read-only board probe failed: " + error)
        report = json.loads(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({'status': 'read_only_inventory_saved',
            'owners': len(report['driver_owners']), 'viewers': len(report['viewers']),
            'mapping_bytes': [m['bytes'] for row in report['driver_owners'] for m in row['dma_mappings']]}, indent=2))
    finally:
        client.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    main(parser.parse_args().destination)
