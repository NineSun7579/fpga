#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deploy_quad_camview.py -- bring up RK3568 for the 4-camera bitstream + run quad camview.

Assumes the FPGA has already been JTAG-programmed with the quad bitstream.
  1. stop camview / unload driver / remove PCI device
  2. rescan PCIe + insmod driver  (fresh enumeration after FPGA reconfig)
  3. push repo host/camview/main.cpp + camview.pro, rebuild on board
  4. launch run_camview.sh (single instance), verify process
  5. screenshot the X display and pull it back
"""
import os
import shlex
import sys
import time

import paramiko

REPO = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(REPO, "host", "camview")
HOST = "192.168.10.203"
USER, PW = "linaro", "123456"
OUT = os.path.join(REPO, "tp", "quad_repo_run")
os.makedirs(OUT, exist_ok=True)

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PW,
          allow_agent=False, look_for_keys=False, timeout=15)


def sh(cmd, tmo=300, echo=True):
    i, o, e = c.exec_command('sudo -S -p "" bash -c ' + shlex.quote(cmd), timeout=tmo)
    i.write(PW + '\n')
    i.flush()
    out = o.read().decode('utf-8', 'replace') + e.read().decode('utf-8', 'replace')
    rc = o.channel.recv_exit_status()
    if echo:
        print(out, end='' if out.endswith('\n') or not out else '\n')
    return rc, out


def push(local, remote):
    tmp = '/tmp/' + os.path.basename(local)
    s = c.open_sftp()
    s.put(local, tmp)
    s.close()
    sh('cp %s %s && md5sum %s' % (tmp, remote, remote))


print('== 1. stop viewers / unbind PCI device / unload driver ==')
sh('pkill -9 -x run_camview.sh 2>/dev/null; pkill -9 -x camview 2>/dev/null; '
   'pkill -9 -x detview 2>/dev/null; sleep 2; '
   'echo 1 > /sys/bus/pci/devices/0002:21:00.0/remove 2>/dev/null; sleep 2; '
   'rmmod pango_pci_driver 2>/dev/null; sleep 1; '
   'echo "proc: $(pgrep -c -x camview || true)"; lsmod | grep pango || echo "driver unloaded"')

print('== 2. rescan PCIe + insmod driver ==')
rc, out = sh('echo 1 > /sys/bus/pci/rescan; sleep 3; '
             'insmod /root/ov5640/pango_pci_driver.ko; sleep 3; '
             'ls -l /sys/bus/pci/devices/0002:21:00.0/driver; ls /dev/pango_pci_driver')
if rc != 0 or '/dev/pango_pci_driver' not in out:
    print('!! driver bring-up failed'); c.close(); sys.exit(2)

print('== 3. push + rebuild camview (quad) ==')
s = c.open_sftp()
s.put(os.path.join(SRC, 'main.cpp'), '/tmp/main.cpp')
s.put(os.path.join(SRC, 'camview.pro'), '/tmp/camview.pro')
s.close()
sh('cp /tmp/main.cpp /root/ov5640/camview/main.cpp; cp /tmp/camview.pro /root/ov5640/camview/camview.pro; '
   'cd /root/ov5640/camview && rm -f camview Makefile *.o moc_* .qmake.stash && '
   '/usr/lib/qt5/bin/qmake > /tmp/qm.log 2>&1 && make -j4 > /tmp/mk.log 2>&1; echo RC=$?; '
   'grep -aiE "error" /tmp/mk.log | head -8; ls -la camview 2>/dev/null | tail -1')

print('== 4. launch run_camview.sh ==')
sh('rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh > /tmp/camview.log 2>&1 < /dev/null & sleep 12; '
   'echo "camview procs: $(pgrep -c -x camview || true)"; tail -6 /tmp/camview.log 2>/dev/null')

print('== 5. screenshot ==')
rc, out = sh('DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 /root/ov5640/qshot/qshot /tmp/quad_repo.png 900; '
             'ls -l /tmp/quad_repo.png', tmo=60)
try:
    s = c.open_sftp()
    s.get('/tmp/quad_repo.png', os.path.join(OUT, 'screen.png'))
    s.close()
    print('saved', os.path.join(OUT, 'screen.png'))
except Exception as ex:
    print('screenshot pull failed:', ex)

c.close()
print('DONE')
