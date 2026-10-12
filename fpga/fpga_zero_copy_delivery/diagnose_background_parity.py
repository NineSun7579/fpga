"""Bounded hardware alignment diagnostic with guarded RAW restoration."""
from pathlib import Path
import json
import re
import shlex
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_ssh

root=Path(__file__).resolve().parent
remote='/userdata/linaro/fpga-zero-copy-host-background/background_thumbnail_parity'
raw='/userdata/linaro/fpga-zero-copy-viewer-six-batch/detview_six_camera_candidate'
folder=root/('background_alignment_diagnostic_'+str(time.time_ns()))
folder.mkdir()
client=board_ssh.connect()
def run(command,timeout=20):
    return board_ssh.run(client,command,sudo=True,timeout=timeout)
def owners():
    rc,out,err=run('fuser /dev/pango_pci_driver 2>/dev/null || true')
    if rc or any(not p.isdigit() for p in out.split()):
        raise RuntimeError('Uncertain device ownership')
    return [int(p) for p in out.split()]
retired=False
try:
    for pid in owners():
        rc,out,err=run('readlink /proc/'+str(pid)+'/exe; cat /proc/'+str(pid)+'/stat')
        lines=out.splitlines()
        if rc or len(lines)!=2 or lines[0]!=raw or lines[1].rsplit(')',1)[1].split()[0] in ('T','t'):
            raise RuntimeError('Preserve unexpected/stopped owner '+str(pid))
        rc,out,err=run('kill -TERM '+str(pid))
        if rc: raise RuntimeError(out+err)
    for attempt in range(50):
        if not owners(): break
        time.sleep(.1)
    else: raise RuntimeError('RAW viewer did not release device')
    retired=True
    command=remote+' --cameras 1 --count 10 --attempts 16 --timeout 10 --diagnostics'
    rc,out,err=run(command+' >'+remote+'.diagnostic.jsonl 2>'+remote+'.diagnostic.stderr',timeout=180)
    with client.open_sftp() as sftp:
        for suffix in ('.jsonl','.stderr'):
            sftp.get(remote+'.diagnostic'+suffix,str(folder/('parity'+suffix)))
    (folder/'result.json').write_text(json.dumps({'return_code':rc,'command':command},indent=2))
    print('Diagnostic return_code',rc,'evidence',folder,flush=True)
finally:
    try:
        if retired:
            if owners():
                raise RuntimeError('Diagnostic owner retained; restoration blocked, preserve it')
            log='/userdata/linaro/display-latency-delivery/final_acceptance.log'
            command=('cd /userdata/detview-hdmifull; setsid nohup env DISPLAY=:0 '
                'XAUTHORITY=/var/run/lightdm/root/:0 QT_QPA_PLATFORM=xcb QT_XCB_GL_INTEGRATION=xcb_egl '
                'DET_BENCH=1 DETVIEW_FPGA_SIX_THUMBNAIL=0 '+shlex.quote(raw)+
                ' --model MVP_accuracy_round1 --fullscreen >'+shlex.quote(log)+' 2>&1 </dev/null & echo $!')
            rc,out,err=run(command)
            if rc: raise RuntimeError(out+err)
            (folder/'restored_pid.txt').write_text(out.strip())
            pid=int(out.strip())
            for attempt in range(20):
                time.sleep(1)
                rc,text,err=run('kill -0 '+str(pid)+' && tail -150 '+shlex.quote(log))
                if rc or any(marker in text.lower() for marker in ('quarantine','segmentation fault')):
                    raise RuntimeError('Restored RAW failed; preserve owner '+str(pid))
                healthy=[]
                for have,rates,errors in re.findall(r'have=([01]{6}) capture_fps=([0-9./]+) err=([0-9/]+)',text):
                    rate=rates.split('/'); error=errors.split('/')
                    if len(rate)==len(error)==6 and all(have[c]=='1' and float(rate[c])>1 and int(error[c])==0 for c in range(4)):
                        healthy.append((have,rates,errors))
                if healthy and '[tdm_bench]' in text:
                    (folder/'restored_health.log').write_text(text,encoding='utf-8')
                    (folder/'restored_health.json').write_text(json.dumps({'pid':pid,'healthy':True,'accepted_cameras':[1,2,3,4],'last_panes':healthy[-1]},indent=2))
                    print('Restored healthy RAW process',pid,flush=True)
                    break
            else:
                raise RuntimeError('RAW freshness/RKNN unverified; preserve owner '+str(pid))
    finally:
        client.close()
