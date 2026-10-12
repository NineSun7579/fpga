"""Alternating thumbnail comparison; same candidate binary and RKNN model."""
from pathlib import Path
import argparse
import json
import re
import shlex
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh

parser=argparse.ArgumentParser()
parser.add_argument('--arms',default='ABBA')
parser.add_argument('--seconds',type=int,default=60)
parser.add_argument('--six-camera',action='store_true')
parser.add_argument('--batch',action='store_true')
parser.add_argument('--accept-cameras',default='1,2,3,4')
parser.add_argument('--trace',action='store_true')
parser.add_argument('--async-candidate',action='store_true')
parser.add_argument('--background-candidate',action='store_true')
parser.add_argument('--restore-candidate',action='store_true',help='Restore tested batch viewer in RAW mode with graceful SIGTERM')
args=parser.parse_args()
args.batch=args.batch or args.async_candidate or args.background_candidate
camera_values=args.accept_cameras.split(',')
if not camera_values or any(value not in ('1','2','3','4','5','6') for value in camera_values) or len(set(camera_values))!=len(camera_values):
    parser.error('Acceptance cameras must be unique physical numbers 1..6')
accepted_cameras={int(value) for value in camera_values}
args.six_camera=args.six_camera or args.batch
if not args.arms or set(args.arms)-set('AB') or args.seconds<10:
    raise ValueError('Invalid arms or duration')
root=Path(__file__).resolve().parent
measurement=root/('six_batch_display_measurement' if args.batch else 'six_display_measurement' if args.six_camera else 'display_measurement')
if args.async_candidate: measurement=root/'six_async_display_measurement'
if args.background_candidate: measurement=root/'six_background_display_measurement'
if args.trace: measurement=root/(measurement.name+'_trace_'+str(time.time_ns()))
measurement.mkdir(exist_ok=True)
client=board_ssh.connect()
logroot='/userdata/linaro/fpga-zero-copy-viewer'+('-six-background' if args.background_candidate else '-six-async' if args.async_candidate else '-six-batch' if args.batch else '-six' if args.six_camera else '')
binary=logroot+('/detview_six_camera_background_candidate' if args.background_candidate else '/detview_six_camera_async_candidate' if args.async_candidate else '/detview_six_camera_candidate' if args.six_camera else '/detview_thumbnail_candidate')
safe_raw='/userdata/linaro/fpga-zero-copy-viewer-six-batch/detview_six_camera_candidate'
def run(command,timeout=30):
    rc,out,err=board_ssh.run(client,command,sudo=True,timeout=timeout)
    if rc:
        raise RuntimeError(out+err)
    return out
def stop_viewer():
    # Inspect ownership rather than opening the global driver to probe it.
    out=run('fuser /dev/pango_pci_driver 2>/dev/null || true')
    for word in out.split():
        if not word.isdigit():
            raise RuntimeError('Unrecognized owner '+out)
        pid=int(word)
        exe=run('readlink /proc/'+str(pid)+'/exe').strip()
        stat=run('cat /proc/'+str(pid)+'/stat')
        state=stat.rsplit(')',1)[1].split()[0]
        if state in ('T','t') or exe not in (binary,safe_raw,'/userdata/detview-hdmifull/detview-hdmifull'):
            raise RuntimeError('Uncertain/stopped/unexpected device owner; preserve it: '+str(pid)+' '+exe)
        run('kill -TERM '+str(pid))
    for attempt in range(50):
        if not run('fuser /dev/pango_pci_driver 2>/dev/null || true').strip():
            break
        time.sleep(0.1)
    else:
        raise RuntimeError('Viewer did not retire DMA owner')
def start_viewer(executable,log,extra):
    env='DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 QT_QPA_PLATFORM=xcb QT_XCB_GL_INTEGRATION=xcb_egl DET_BENCH=1 '
    cmd=('cd /userdata/detview-hdmifull; setsid nohup env '+env+extra+' '+shlex.quote(executable)+
         ' --model MVP_accuracy_round1 --fullscreen >'+shlex.quote(log)+' 2>&1 </dev/null & echo $!')
    pid=int(run(cmd).strip())
    return pid
def restore_viewer():
    stop_viewer()
    executable=safe_raw if args.restore_candidate else '/userdata/detview-hdmifull/detview-hdmifull'
    log='/userdata/linaro/display-latency-delivery/final_acceptance.log'
    pid=start_viewer(executable,log,
                     'DETVIEW_FPGA_SIX_THUMBNAIL=0' if args.restore_candidate else '')
    (measurement/'restored_pid.txt').write_text(str(pid))
    for attempt in range(20):
        time.sleep(1)
        run('kill -0 '+str(pid))
        text=run('tail -150 '+shlex.quote(log))
        if any(marker in text.lower() for marker in ('quarantine','segmentation fault')):
            raise RuntimeError('Restored viewer failed; preserve device owner '+str(pid))
        panes=re.findall(r'have=([01]{6}) capture_fps=([0-9./]+) err=([0-9/]+)',text)
        healthy=[]
        for have,rates,errors in panes:
            rate=rates.split('/'); error=errors.split('/')
            if len(rate)==len(error)==6 and all(have[c-1]=='1' and float(rate[c-1])>1 and int(error[c-1])==0 for c in accepted_cameras):
                healthy.append((have,rates,errors))
        if healthy and '[tdm_bench]' in text:
            (measurement/'restored_health.log').write_text(text,encoding='utf-8')
            (measurement/'restored_health.json').write_text(json.dumps({'pid':pid,'binary':executable,
                'accepted_cameras':sorted(accepted_cameras),'healthy':True,'last_panes':healthy[-1]},indent=2))
            break
    else:
        raise RuntimeError('Restored viewer has no verified fresh capture/RKNN; preserve owner '+str(pid))
    print('Restored healthy RAW viewer PID',pid,'binary',executable,flush=True)
    return pid
measurement_started=False
try:
    run('test -x '+binary)
    if run('pgrep -x make; pgrep -x cc1plus; true').strip():
        raise RuntimeError('Target compilation still active')
    with client.open_sftp() as sftp:
        sftp.put(str(root/'sample_host.py'),'/tmp/fpga_offload_sample_host.py')
    records=[]
    (measurement/'scope.json').write_text(json.dumps({'accepted_cameras':sorted(accepted_cameras),
        'traffic_cameras':[1,2,3,4,5,6],'deferred_image_issues':[5,6],
        'requested_arms':args.arms,'seconds_per_arm':args.seconds,'stage_trace':args.trace,
        'background_candidate':args.background_candidate},indent=2))
    for index,arm in enumerate(args.arms):
        stop_viewer()
        measurement_started=True
        label=str(index+1)+arm
        log=logroot+'/display_'+label+('_trace' if args.trace else '')+'.log'
        setting='DETVIEW_FPGA_SIX_THUMBNAIL' if args.six_camera else 'DETVIEW_FPGA_THUMBNAIL'
        pid=start_viewer(binary,log,setting+'='+str(int(arm=='B'))+
                         (' DETVIEW_FPGA_BACKGROUND_THUMBNAIL='+str(int(arm=='B')) if args.background_candidate else '')+
                         (' DETVIEW_THUMBNAIL_TRACE=1' if args.trace else ''))
        time.sleep(5)
        sample=run('python3 /tmp/fpga_offload_sample_host.py --pid '+str(pid)+' --seconds '+str(args.seconds),args.seconds+20)
        (measurement/(label+'_host.json')).write_text(sample,encoding='utf-8')
        with client.open_sftp() as sftp:
            sftp.get(log,str(measurement/(label+'.log')))
        text=(measurement/(label+'.log')).read_text(errors='replace')
        import re
        availability=re.findall(r'have=([01]{6})',text)
        if not any(all(row[camera-1]=='1' for camera in accepted_cameras) for row in availability) or any(marker in text.lower() for marker in ('quarantine','segmentation fault')):
            raise RuntimeError('Display acceptance failed; inspect '+label)
        errors=re.findall(r'err=([0-9/]+)',text)
        unstable=re.findall(r'\[capture\] camera=(\d+)[^\n]*unstable=(\d+)',text)
        if not errors or any(len(row.split('/'))!=6 or any(int(row.split('/')[camera-1]) for camera in accepted_cameras) for row in errors) or any(int(value) for camera,value in unstable if int(camera) in accepted_cameras):
            raise RuntimeError('Capture errors or instability; inspect '+label)
        active={int(camera) for camera,rate in re.findall(r'\[capture\] camera=(\d+) delivered_fps=([\d.]+)',text) if float(rate)>1}
        uploaded={camera:0 for camera in range(1,7)}
        for camera,count in re.findall(r'\[display-upload\] camera=(\d+) count=(\d+)',text):
            uploaded[int(camera)]+=int(count)
        if not accepted_cameras.issubset(active) or any(uploaded[camera]<10 for camera in accepted_cameras):
            raise RuntimeError('A camera is frozen or not delivering fresh frames; inspect '+label)
        data=json.loads(sample)
        records.append({'arm':arm,'pid':pid,'cpu_percent_one_core':data['cpu_percent_one_core'],
                        'peak_rss_kib':data['peak_rss_kib'],'seconds':data['wall_seconds']})
        (measurement/'arms.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
        print(label,records[-1],flush=True)
    restore_viewer()
except Exception as failure:
    (measurement/'failure.txt').write_text(repr(failure),encoding='utf-8')
    if measurement_started:
        try:
            restore_viewer()
        except Exception as recovery:
            (measurement/'recovery_failure.txt').write_text(repr(recovery),encoding='utf-8')
            print('Recovery blocked; preserve device owner:',recovery,flush=True)
    raise
finally:
    client.close()
