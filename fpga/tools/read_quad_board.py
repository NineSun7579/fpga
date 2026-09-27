import sys, shlex, time
from pathlib import Path
import paramiko

from board_host import board_host

# [CAM4 2026-09-27] Host driver: run the 4-camera capture on the RK3568 and pull
# all evidence (registers, rgb565 frames, tags) plus fresh screenshots.
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tp' / 'quad_evidence'
OUT.mkdir(parents=True, exist_ok=True)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HOST = board_host()
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username='linaro', password='123456', allow_agent=False, look_for_keys=False, timeout=15)


def sh(cmd):
    i, o, e = c.exec_command('sudo -S -p "" bash -c ' + shlex.quote(cmd), timeout=600)
    i.write('123456\n'); i.flush()
    text = o.read().decode('utf-8', 'replace') + e.read().decode('utf-8', 'replace')
    rc = o.channel.recv_exit_status()
    print(text, flush=True)
    with (OUT / 'session.log').open('a', encoding='utf-8') as f:
        f.write(cmd + '\n' + text + '\n')
    if rc:
        raise RuntimeError('remote exit ' + str(rc))
    return text


sh('pkill -9 -x run_camview.sh || true')
sh('pkill -9 -x camview || true')
sh('rmmod pango_pci_driver; insmod /root/ov5640/pango_pci_driver.ko; test -L /sys/bus/pci/devices/0002:21:00.0/driver')
s = c.open_sftp()
for f in ('cam3_i2c_pt.py', 'verify_quad_board.py'):
    s.put(str(ROOT / 'tools' / f), '/tmp/' + f)
try:
    sh('python3 -u /tmp/verify_quad_board.py')
    for f in s.listdir('/tmp/quad_evidence'):
        s.get('/tmp/quad_evidence/' + f, str(OUT / f))
finally:
    for f in s.listdir('/tmp/quad_evidence'):
        try:
            s.get('/tmp/quad_evidence/' + f, str(OUT / f))
        except Exception:
            pass
    sh('rmmod pango_pci_driver; insmod /root/ov5640/pango_pci_driver.ko; sleep 2; test -L /sys/bus/pci/devices/0002:21:00.0/driver')
    sh('rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh > /tmp/camview.log 2>&1 < /dev/null &')
    sh('sleep 10; pgrep -a -x camview')

for k in range(3):
    sh('DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 /root/ov5640/qshot/qshot /tmp/quad_screen.png 1200')
    s.get('/tmp/quad_screen.png', str(OUT / ('screen%d.png' % k)))
    time.sleep(4)
s.close(); c.close()
print('PULLED to', OUT, flush=True)
