"""Restart unchanged original only on the recorded boot with no device owner."""
from pathlib import Path
import json
import shlex
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh
root=Path(__file__).resolve().parent
remote='/userdata/linaro/ov56401-original-resume-'+str(time.time_ns())
code=r'''
import os,hashlib,subprocess,json
exe='/userdata/detview-hdmifull/detview-hdmifull'
assert open('/proc/sys/kernel/random/boot_id').read().strip()=='644568c5-2252-4240-87b0-d0810cbc4131','Boot changed; SRAM recovery required'
assert hashlib.sha256(open(exe,'rb').read()).hexdigest()=='73613d525541939ea493a9bb87eeeae10879c4a08eede36a7ee298777fb32100'
owners=subprocess.run(['fuser','/dev/pango_pci_driver'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
assert owners.returncode==1 and not owners.stdout.strip(), 'Device owner exists'
assert open('/sys/module/pango_zc/refcnt').read().strip()=='0'
os.makedirs(REMOTE+'/tmp')
env=dict(os.environ,DISPLAY=':0',XAUTHORITY='/home/linaro/.Xauthority',TMPDIR=REMOTE+'/tmp',XDG_RUNTIME_DIR='/run/user/1000')
for key in ('DETVIEW_FPGA_INFER_RGB','DETVIEW_FPGA_INFER_VERIFY'):env.pop(key,None)
log=open(REMOTE+'/original.log','wb')
process=subprocess.Popen([exe,'--model','MVP_accuracy_round1','--fullscreen'],cwd='/userdata/detview-hdmifull',env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print(json.dumps({'pid':process.pid,'remote':REMOTE,'scope':'unchanged original runtime restart; no programming or module swap'}))
'''
client=board_ssh.connect()
try:
    rc,out,err=board_ssh.run(client,'python3 -c '+shlex.quote('REMOTE='+repr(remote)+'\n'+code),timeout=30,sudo=True)
    (root/'original_resume.json').write_text(out if rc==0 else json.dumps({'error':out+err}),encoding='utf-8')
    print(out+err)
    if rc:raise RuntimeError('Original restart gate failed')
finally:
    client.close()
