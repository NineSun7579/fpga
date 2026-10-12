"""Preserve current logs, gracefully retire known RAW owner, rollback SRAM, measure RAW."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh

root=Path(__file__).resolve().parent
evidence=root/('cam2_rollback_'+str(time.time_ns()))
evidence.mkdir()
image=root/'integrated_six_batch/project/generate_bitstream/top.sbit'
assert hashlib.sha256(image.read_bytes()).hexdigest()=='81eb0c05b40eff2887f1b81770fece6beafedc25f77fd1bbfbebe487e9dbb192'
client=board_ssh.connect()
def run(command):
    rc,out,err=board_ssh.run(client,command,sudo=True,timeout=20)
    if rc: raise RuntimeError(out+err)
    return out
def owners():
    out=run('fuser /dev/pango_pci_driver 2>/dev/null || true')
    if any(not s.isdigit() for s in out.split()): raise RuntimeError('Uncertain ownership')
    return [int(s) for s in out.split()]
try:
    with client.open_sftp() as sftp:
        sftp.get('/userdata/linaro/display-latency-delivery/final_acceptance.log',str(evidence/'background_raw.log'))
    (evidence/'preflight.txt').write_text(run('cat /proc/sys/kernel/random/boot_id; dmesg | tail -40'),encoding='utf-8')
    for pid in owners():
        text=run('readlink /proc/'+str(pid)+'/exe; cat /proc/'+str(pid)+'/stat').splitlines()
        if len(text)!=2 or text[0]!='/userdata/linaro/fpga-zero-copy-viewer-six-batch/detview_six_camera_candidate' or text[1].rsplit(')',1)[1].split()[0] in ('T','t'):
            raise RuntimeError('Preserve unexpected/stopped owner '+str(pid))
        run('kill -TERM '+str(pid))
    for attempt in range(50):
        if not owners(): break
        time.sleep(.1)
    else: raise RuntimeError('Viewer did not retire; preserve owner')
finally:
    client.close()
for command,name in ((['program_fpga.py','--batch'],'program'),
                     (['run_display_compare.py','--batch','--trace','--arms','A','--seconds','30','--restore-candidate','--accept-cameras','1,2,3,4'],'raw_smoke')):
    with (evidence/(name+'.log')).open('w',encoding='utf-8') as log:
        rc=subprocess.call([sys.executable]+command,cwd=root,stdout=log,stderr=subprocess.STDOUT)
    print(name,'return_code',rc,'evidence',evidence,flush=True)
    if rc: raise RuntimeError('Failed '+name+'; inspect evidence and preserve uncertain owner')
print('Rollback and RAW smoke completed',evidence,flush=True)
