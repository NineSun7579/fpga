"""Read board sources into an isolated local snapshot without altering runtime."""
from pathlib import Path
import hashlib
import json
import stat
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh

root=Path(__file__).resolve().parent/('baseline_'+str(time.time_ns()))
root.mkdir()
client=board_ssh.connect()
receipt={'files':{}}
try:
    rc,out,err=board_ssh.run(client,'sha256sum /userdata/detview-hdmifull/detview-hdmifull /userdata/linaro/detview-display-fix-20261008/detview; cat /proc/sys/kernel/random/boot_id; fuser /dev/pango_pci_driver',sudo=True)
    (root/'runtime.txt').write_text(out+err,encoding='utf-8')
    with client.open_sftp() as sftp:
        def pull(remote,local):
            local.mkdir(exist_ok=True,parents=True)
            for entry in sftp.listdir_attr(remote):
                path=remote+'/'+entry.filename
                dest=local/entry.filename
                if stat.S_ISDIR(entry.st_mode):
                    if entry.filename in ('stereo_demo','cooperative_linux_transport'):
                        pull(path,dest)
                elif entry.filename.endswith(('.cpp','.h','.hpp','.pro','.c','.md')) or entry.filename=='candidate_sha256.txt':
                    sftp.get(path,str(dest))
                    receipt['files'][str(dest.relative_to(root))]={'remote':path,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()}
        pull('/userdata/linaro/detview-display-fix-20261008',root/'viewer')
        pull('/userdata/linaro/fpga-zero-copy-driver-stage',root/'driver')
        pull('/userdata/linaro/fpga-zero-copy-host',root/'host')
    (root/'manifest.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(root)
finally:
    client.close()
