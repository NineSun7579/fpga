# -*- coding: utf-8 -*-
"""Recover a GOOD board state and characterise the per-config variability.

For up to 3 attempts: JTAG configure -> rescan/insmod -> measure each camera's
frame rate (minimal register reads) and cam3's sensor rate (VSYNC).  Stop as
soon as the frame rates look healthy.  Finally restart camview and take two
screenshots to confirm the display is live.
"""
import os
import re
import subprocess
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.203", "linaro", "123456"
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project"
OUT = os.path.join(ROOT, "tp", "recover3")
DEV = "/sys/bus/pci/devices/0002:21:00.0"
TCL = os.path.join(ROOT, "flash_verified_cam3.tcl")

MEASURE = r'''
import sys, time
sys.path.insert(0, "/tmp")
import cam3_i2c_pt as m
B = {"cam1": 0x20000000, "cam2": 0x20000200, "cam3": 0x20000400}
d = m.PciDriver()
def rd(a): return d.read32(a) & 0xFFFFFFFF
def rate(a, win=4):
    x = rd(a); time.sleep(win); y = rd(a)
    return ((y - x) & 0xFFFFFFFF) / float(win)
out = {}
for k, b in B.items():
    out[k] = rate(b + 0xf0)
print("FRAMES/s: cam1=%.1f cam2=%.1f cam3=%.1f" % (out["cam1"], out["cam2"], out["cam3"]))
print("cam3 sensor: PCLK=%.2fMHz VSYNC/s=%.1f" % (rate(B["cam3"] + 0x10) / 1e6, rate(B["cam3"] + 0x20)))
st = rd(B["cam3"] + 0x60); print("cam3 state=%d +0xd0=0x%08X" % ((st >> 16) & 7, rd(B["cam3"] + 0xd0)))
d.close()
'''


def connect(timeout=15):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, 22, USER, PW, timeout=timeout, allow_agent=False, look_for_keys=False)
    return c


def sh(c, cmd, t=200, show=True):
    full_cmd = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    _, o, e = c.exec_command(full_cmd, timeout=t)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    if show:
        print("$ " + cmd, flush=True)
        if out.strip():
            print(out.rstrip(), flush=True)
        if err.strip() and "password for" not in err:
            print("ERR:", err.rstrip()[:250], flush=True)
    return out


os.makedirs(OUT, exist_ok=True)
c = connect()
good = False
for attempt in range(1, 4):
    print("=== attempt %d ===" % attempt, flush=True)
    sh(c, "pkill -9 -x run_camview.sh 2>/dev/null; sleep 1; pkill -9 -x camview 2>/dev/null; sleep 3; "
          "rmmod pango_pci_driver 2>/dev/null; sleep 2; "
          "test -e %s && echo 1 > %s/remove; sleep 2; echo linkdown" % (DEV, DEV), t=120)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "burn_now.py"), TCL],
                       cwd=ROOT, capture_output=True, timeout=420)
    out = (r.stdout + r.stderr).decode("utf-8", "replace")
    ok = "BURN OK" in out
    print("  burn:", "OK" if ok else "FAILED", flush=True)
    if not ok:
        continue
    sh(c, "echo 1 > /sys/bus/pci/rescan; sleep 3; rmmod pango_pci_driver 2>/dev/null; sleep 1; "
          "insmod /root/ov5640/pango_pci_driver.ko && echo INSMOD_OK; sleep 4", t=120)
    sftp = c.open_sftp()
    sftp.put(os.path.join(ROOT, "tools", "cam3_i2c_pt.py"), "/tmp/cam3_i2c_pt.py")
    with sftp.open("/tmp/_meas.py", "w") as f:
        f.write(MEASURE)
    txt = sh(c, "python3 -u /tmp/_meas.py 2>&1", t=200)
    m = re.search(r"cam1=([0-9.]+) cam2=([0-9.]+) cam3=([0-9.]+)", txt)
    if m:
        vals = [float(m.group(i)) for i in (1, 2, 3)]
        print("  -> %.1f / %.1f / %.1f fps" % tuple(vals), flush=True)
        if min(vals) >= 25:
            good = True
            sftp.close()
            break
    sftp.close()

print("=== good=%s ===" % good, flush=True)
print("=== restart camview + screenshots ===", flush=True)
sh(c, "rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh "
      "> /tmp/camview.log 2>&1 < /dev/null & sleep 12; "
      "ps -eo comm | grep -E '^camview$' && echo CAMVIEW-RUNNING || echo 'camview NOT running'")
sh(c, "rm -f /tmp/r3a.png /tmp/r3b.png; "
      "DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 /root/ov5640/qshot/qshot /tmp/r3a.png 900 >/dev/null 2>&1; "
      "sleep 3; "
      "DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 /root/ov5640/qshot/qshot /tmp/r3b.png 900 >/dev/null 2>&1; "
      "ls -la /tmp/r3a.png /tmp/r3b.png")
sftp = c.open_sftp()
for n in ("r3a", "r3b"):
    try:
        sftp.get("/tmp/%s.png" % n, os.path.join(OUT, "%s.png" % n))
        print("pulled", n)
    except Exception as e:
        print("pull failed", n, e)
sftp.close()
c.close()
print("DONE")
