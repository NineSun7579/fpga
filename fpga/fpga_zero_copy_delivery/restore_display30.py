"""Restore the archived, measured production image and viewer; SRAM only."""
from pathlib import Path
import json
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh
root=Path(__file__).resolve().parent
folder=root/('restore_display30_'+str(time.time_ns()))
folder.mkdir()
backup='/userdata/detview-hdmifull/detview-hdmifull.before-latency-fix-20261008'
expected='73613d525541939ea493a9bb87eeeae10879c4a08eede36a7ee298777fb32100'
client=board_ssh.connect()
post_reboot=False
def run(cmd):
    rc,out,err=board_ssh.run(client,cmd,sudo=True,timeout=20)
    if rc: raise RuntimeError(out+err)
    return out
try:
    assert run('sha256sum '+backup).split()[0]==expected
    post_reboot=run('if [ -e /sys/bus/pci/devices/0002:21:00.0 ]; then echo present; else echo absent; fi').strip()=='absent'
    out=run('fuser /dev/pango_pci_driver 2>/dev/null || true')
    for word in out.split():
        if not word.isdigit(): raise RuntimeError('Uncertain owner')
        text=run('readlink /proc/'+word+'/exe; cat /proc/'+word+'/stat').splitlines()
        if len(text)!=2 or text[0]!='/userdata/linaro/fpga-zero-copy-viewer-six-batch/detview_six_camera_candidate' or text[1].rsplit(')',1)[1].split()[0] in ('T','t'):
            raise RuntimeError('Preserve unexpected owner '+word)
        run('kill -TERM '+word)
    for attempt in range(50):
        if not run('fuser /dev/pango_pci_driver 2>/dev/null || true').strip(): break
        time.sleep(.1)
    else: raise RuntimeError('Device still owned')
finally:
    client.close()
with (folder/'program.log').open('w',encoding='utf-8') as log:
    rc=subprocess.call([sys.executable,'program_fpga.py','--restore-display30']+(['--post-reboot'] if post_reboot else []),cwd=root,stdout=log,stderr=subprocess.STDOUT)
if rc: raise RuntimeError('Programming failed; inspect '+str(folder))
client=board_ssh.connect()
try:
    active='/userdata/detview-hdmifull/detview-hdmifull'
    run('cp -p '+active+' '+active+'.before-display30-restore-'+folder.name)
    run('cp -p '+backup+' '+active)
    assert run('sha256sum '+active).split()[0]==expected
    remote='/userdata/linaro/display-latency-delivery/restored_display30.log'
    pid=int(run('cd /userdata/detview-hdmifull; setsid nohup env DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 QT_QPA_PLATFORM=xcb QT_XCB_GL_INTEGRATION=xcb_egl DET_BENCH=1 '+active+' --model MVP_accuracy_round1 --fullscreen >'+remote+' 2>&1 </dev/null & echo $!').strip())
    (folder/'runtime.json').write_text(json.dumps({'pid':pid,'binary':active,'sha256':expected,'remote_log':remote},indent=2))
    print('Original image/viewer restored; PID',pid,'evidence',folder,flush=True)
    for attempt in range(19):
        time.sleep(5)
        run('kill -0 '+str(pid))
    with client.open_sftp() as sftp:
        sftp.get(remote,str(folder/'acceptance.log'))
    print('95-second runtime evidence collected',folder,flush=True)
finally:
    client.close()
