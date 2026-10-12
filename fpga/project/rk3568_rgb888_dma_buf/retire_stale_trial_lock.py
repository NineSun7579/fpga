"""Archive only the known pre-reboot trial lock with original owner verified."""
from pathlib import Path
import json,shlex,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh
root=Path(__file__).resolve().parent
old=json.loads((root/'deploy_1791567760719372300/receipt.json').read_text())
code=r'''
from pathlib import Path
import hashlib,subprocess,json
lock=Path('/userdata/linaro/ov56401-deploy.lock')
assert lock.read_text().strip()==OLD['remote'],'Unknown lock'
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert boot!=OLD['baseline']['boot_id'],'Old trial boot still active'
assert subprocess.check_output(['fuser','/dev/pango_pci_driver'],stderr=subprocess.DEVNULL,text=True).split()==['2141']
assert hashlib.sha256(Path('/proc/2141/exe').read_bytes()).hexdigest()==OLD['artifacts']['active_sha256']
dest=Path(str(lock)+'.before-'+boot)
assert not dest.exists()
lock.rename(dest)
print(json.dumps({'archived_lock':str(dest),'boot_id':boot,'verified_original_pid':2141}))
'''
client=board_ssh.connect()
try:
    rc,out,err=board_ssh.run(client,'python3 -c '+shlex.quote('OLD='+repr(old)+'\n'+code),timeout=25,sudo=True)
    (root/'stale_lock_retirement.json').write_text(out+err,encoding='utf-8')
    print(out+err)
    if rc:raise RuntimeError('Stale lock retirement rejected')
finally:client.close()
