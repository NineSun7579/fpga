import sys,subprocess,shlex,time
from pathlib import Path
import paramiko
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'tp/frame_recovery_evidence';OUT.mkdir(parents=True,exist_ok=True)
sys.stdout.reconfigure(encoding='utf-8',errors='replace')
c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.10.241',username='linaro',password='123456',allow_agent=False,look_for_keys=False,timeout=15)
def sh(cmd):
    i,o,e=c.exec_command('sudo -S -p "" bash -c '+shlex.quote(cmd),timeout=90)
    i.write('123456\n');i.flush()
    text=o.read().decode('utf-8','replace')+e.read().decode('utf-8','replace');rc=o.channel.recv_exit_status()
    print(text,flush=True)
    with (OUT/'session.log').open('a',encoding='utf-8') as f:f.write(cmd+'\n'+text+'\n')
    if rc:raise RuntimeError('remote exit '+str(rc))
sh('pkill -9 -x run_camview.sh || true')
sh('pkill -9 -x camview || true')
sh('sleep 2; rmmod pango_pci_driver; echo 1 > /sys/bus/pci/devices/0002:21:00.0/remove')
r=subprocess.run([sys.executable,str(ROOT/'tools/burn_now.py'),str(ROOT/'flash_frame_recovery.tcl')],cwd=ROOT,capture_output=True,timeout=420)
text=(r.stdout+r.stderr).decode('utf-8','replace');print(text,flush=True)
assert r.returncode==0 and 'BURN OK' in text
sh('echo 1 > /sys/bus/pci/rescan; sleep 3; insmod /root/ov5640/pango_pci_driver.ko; sleep 3; test -L /sys/bus/pci/devices/0002:21:00.0/driver')
s=c.open_sftp()
for f in ['cam3_i2c_pt.py','verify_recovery_board.py']:s.put(str(ROOT/'tools'/f),'/tmp/'+f)
try:
    sh('python3 -u /tmp/verify_recovery_board.py')
    for f in s.listdir('/tmp/frame_recovery_evidence'):s.get('/tmp/frame_recovery_evidence/'+f,str(OUT/f))
finally:
    sh('rmmod pango_pci_driver; insmod /root/ov5640/pango_pci_driver.ko; sleep 2; test -L /sys/bus/pci/devices/0002:21:00.0/driver')
    sh('rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh > /tmp/camview.log 2>&1 < /dev/null &')
    sh('sleep 10; pgrep -a -x camview')
for k in range(2):
    sh('DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 /root/ov5640/qshot/qshot /tmp/init48_screen.png 900')
    s.get('/tmp/init48_screen.png',str(OUT/('screen%d.png'%k)))
    time.sleep(3)
s.close();c.close()
