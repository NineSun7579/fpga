# -*- coding: utf-8 -*-
"""Restore all three cameras to the last fully-live image (verified 84MHz)."""
import subprocess
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.241", "linaro", "123456"
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project"
TCL = ROOT + "\\flash_verified_cam3.tcl"
DEV = "/sys/bus/pci/devices/0002:21:00.0"


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, 22, USER, PW, timeout=15, allow_agent=False, look_for_keys=False)
    return c


def sh(c, cmd, t=120):
    full = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    _, o, e = c.exec_command(full, timeout=t)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    print("$ " + cmd, flush=True)
    if out.strip():
        print(out.rstrip(), flush=True)
    if err.strip() and "password for" not in err:
        print("ERR:", err.rstrip()[:300], flush=True)
    return out


c = connect()
sh(c, "pkill -9 -x run_camview.sh 2>/dev/null; sleep 1; pkill -9 -x camview 2>/dev/null; sleep 2; "
      "rmmod pango_pci_driver 2>/dev/null; sleep 1; "
      "test -e %s && echo 1 > %s/remove; sleep 2; echo linkdown" % (DEV, DEV))
r = subprocess.run([sys.executable, ROOT + "\\tools\\burn_now.py", TCL],
                   cwd=ROOT, capture_output=True, timeout=420)
out = (r.stdout + r.stderr).decode("utf-8", "replace")
print(out.strip()[-500:], flush=True)
if "BURN OK" not in out and "successfully" not in out:
    print("BURN FAILED", flush=True)
    c.close()
    sys.exit(2)
sh(c, "echo 1 > /sys/bus/pci/rescan; sleep 3; rmmod pango_pci_driver 2>/dev/null; sleep 1; "
      "insmod /root/ov5640/pango_pci_driver.ko && echo INSMOD_OK; sleep 3; "
      "ls -l %s/driver" % DEV)
sh(c, "rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh "
      "> /tmp/camview.log 2>&1 < /dev/null & sleep 12; pgrep -a -x camview")
for i in range(2):
    sh(c, "DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 /root/ov5640/qshot/qshot "
          "/tmp/restore_all3_%d.png 900 >/dev/null 2>&1; ls -la /tmp/restore_all3_%d.png" % (i, i))
    time.sleep(3)
sftp = c.open_sftp()
for i in range(2):
    try:
        sftp.get("/tmp/restore_all3_%d.png" % i, "%s/tp/restore_all3_%d.png" % (ROOT, i))
        print("pulled", i, flush=True)
    except Exception as e:
        print("pull failed", i, e, flush=True)
sftp.close()
c.close()
print("DONE", flush=True)
