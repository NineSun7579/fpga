import hashlib
import json
from pathlib import Path
import shlex
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'project/tools'))
from board_host import ssh_connect

REMOTE = r'''
import hashlib, json, pathlib, re, subprocess
module = pathlib.Path('/sys/module/pango_pci_driver')
notes = {}
if (module/'notes').exists():
    for path in (module/'notes').iterdir():
        try: notes[path.name] = path.read_bytes().hex()
        except OSError as error: notes[path.name] = str(error)
files = []
for name in ('/root/ov5640/pango_pci_driver.ko',
             '/userdata/linaro/projects/fpga/RK3568/driver/pango_pci_driver_fixed_20260926.ko'):
    path = pathlib.Path(name)
    if not path.is_file(): continue
    result = subprocess.run(['readelf','-n',name],capture_output=True,text=True,timeout=10)
    value = {'path':name, 'sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'readelf_notes':result.stdout,
             'readelf_error':result.stderr, 'readelf_exit':result.returncode}
    match = re.search(r'Build ID:\s*([0-9a-f]+)',result.stdout)
    value['build_id'] = match.group(1) if match else None
    files.append(value)
print(json.dumps({'loaded_notes':notes, 'files':files, 'module_present':module.exists()}))
'''


def main():
    client = ssh_connect()
    try:
        _, stdout, stderr = client.exec_command('sudo -n python3 -c ' + shlex.quote(REMOTE), timeout=30)
        data = json.loads(stdout.read())
        code = stdout.channel.recv_exit_status()
        data['stderr'] = stderr.read().decode(errors='replace')
        data['exit_code'] = code
        data['captured_unix_s'] = time.time()
        note = bytes.fromhex(data['loaded_notes'].get('.note.gnu.build-id', ''))
        if note:
            byteorder = 'little'
            namesize = int.from_bytes(note[0:4], byteorder)
            descsize = int.from_bytes(note[4:8], byteorder)
            offset = 12 + (namesize + 3)//4*4
            data['loaded_build_id'] = note[offset:offset+descsize].hex()
        else:
            data['loaded_build_id'] = None
        data['matched_files'] = [item['path'] for item in data['files']
                                 if data['loaded_build_id'] and item['build_id'] == data['loaded_build_id']]
        path = ROOT / 'log/100h_motion' / ('loaded_driver_' + time.strftime('%Y%m%d_%H%M%S') + '.json')
        path.write_text(json.dumps(data,indent=2), encoding='utf-8')
        print(json.dumps({'record':str(path), 'loaded_build_id':data['loaded_build_id'],
                          'matched_files':data['matched_files'], 'stderr':data['stderr']},indent=2))
    finally:
        client.close()


if __name__ == '__main__':
    main()
