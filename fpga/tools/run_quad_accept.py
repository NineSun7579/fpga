#!/usr/bin/env python3
"""run_quad_accept.py -- end-to-end quad-camera board acceptance.

Sequence (all automatic):
  1. quiesce the PCIe link (kill camview, rmmod, remove the RC endpoint);
  2. JTAG-burn the cam4 bitstream (tools/burn_now.py flash_quad_cam.tcl);
  3. PCI rescan + insmod, verify the driver symlink;
  4. upload cam3_i2c_pt.py + quad_accept_board.py and run the on-board capture
     (live + cam4-only colour bars + cam3-only colour bars, both DDR banks);
  5. pull all evidence, restart camview, grab screenshots;
  6. run tools/analyze_quad_evidence.py locally and print the verdicts.

Usage:
    python tools/run_quad_accept.py [--tcl <path>] [--skip-burn]
"""
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

import paramiko

from board_host import board_host

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tp' / 'quad_accept'
OUT.mkdir(parents=True, exist_ok=True)
PY = sys.executable
HOST = board_host()
TCL = ROOT / 'flash_quad_cam.tcl'
if '--tcl' in sys.argv:
    TCL = Path(sys.argv[sys.argv.index('--tcl') + 1])
SKIP_BURN = '--skip-burn' in sys.argv
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username='linaro', password='123456', allow_agent=False, look_for_keys=False, timeout=15)


def sh(cmd, timeout=900, check=True):
    i, o, e = c.exec_command('sudo -S -p "" bash -c ' + shlex.quote(cmd), timeout=timeout)
    i.write('123456\n'); i.flush()
    text = o.read().decode('utf-8', 'replace') + e.read().decode('utf-8', 'replace')
    rc = o.channel.recv_exit_status()
    print('$ ' + cmd + '\n' + text, flush=True)
    with (OUT / 'session.log').open('a', encoding='utf-8') as f:
        f.write('$ ' + cmd + '\n' + text + '\n')
    if check and rc:
        raise RuntimeError('remote exit %d: %s' % (rc, cmd))
    return text


try:
    # 1) quiesce PCIe
    sh('pkill -9 -x run_camview.sh || true; pkill -9 -x camview || true')
    sh('rmmod pango_pci_driver 2>/dev/null || true; sleep 1; '
       'echo 1 > /sys/bus/pci/devices/0002:21:00.0/remove 2>/dev/null || true; sleep 2')

    # 2) JTAG burn (Windows side)
    if not SKIP_BURN:
        assert TCL.exists(), 'missing tcl ' + str(TCL)
        print('--- burning', TCL, '---', flush=True)
        r = subprocess.run([PY, str(ROOT / 'tools' / 'burn_now.py'), str(TCL)])
        if r.returncode != 0:
            raise RuntimeError('burn failed')

    # 3) rescan + insmod
    sh('echo 1 > /sys/bus/pci/rescan; sleep 4; '
       'insmod /root/ov5640/pango_pci_driver.ko; sleep 2; '
       'test -L /sys/bus/pci/devices/0002:21:00.0/driver && echo DRIVER_OK')

    # 4) upload + on-board capture
    s = c.open_sftp()
    for f in ('cam3_i2c_pt.py', 'quad_accept_board.py'):
        s.put(str(ROOT / 'tools' / f), '/tmp/' + f)
    sh('rm -rf /tmp/quad_accept'); sh('python3 -u /tmp/quad_accept_board.py')

    # 5) pull evidence + restart camview + screenshots
    for f in s.listdir('/tmp/quad_accept'):
        try:
            s.get('/tmp/quad_accept/' + f, str(OUT / f))
        except Exception as ex:
            print('pull skip', f, ex)
    sh('rmmod pango_pci_driver; insmod /root/ov5640/pango_pci_driver.ko; sleep 2; '
       'test -L /sys/bus/pci/devices/0002:21:00.0/driver && echo DRIVER_OK')
    sh('rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh > /tmp/camview.log 2>&1 < /dev/null &')
    sh('sleep 12; pgrep -a -x camview || true')
    for k in range(3):
        sh('DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 /root/ov5640/qshot/qshot '
           '/tmp/quad_screen.png 1200', check=False)
        try:
            s.get('/tmp/quad_screen.png', str(OUT / ('screen%d.png' % k)))
        except Exception as ex:
            print('screenshot skip', ex)
        time.sleep(4)
    s.close()

    # 6) local analysis
    print('\n--- local analysis ---', flush=True)
    subprocess.run([PY, str(ROOT / 'tools' / 'analyze_quad_evidence.py'), str(OUT)])
finally:
    c.close()
print('QUAD_ACCEPT_COMPLETE ->', OUT)
