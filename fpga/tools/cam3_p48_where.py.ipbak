# -*- coding: utf-8 -*-
"""Diagnose exactly WHERE the cam3 write-engine FSM wedges at 48 MHz.

Reads the debug registers (BASE+0x60 = {wd_cnt[7:0], dbg_state[7:0], cmd_cnt[15:0]},
plus BEAT_CNT 0xa0 / BEAT_LAST 0xf0 / AXI_NOW 0xd0 / AXI_STICKY 0x50) at 84 MHz,
then at 48 MHz (CAM_EN-gated PLL change), then after restoring 84 MHz.

FSM encodings: IDLE=1 ADDR=2 DATA=4 ADDR_TAG=3 DATA_TAG=5 WAIT_TAG_DONE=6
"""
import os
import subprocess
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.241", "linaro", "123456"
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project"
DEV = "/sys/bus/pci/devices/0002:21:00.0"
TCL = os.path.join(ROOT, "flash_verified_cam3.tcl")

BOARD = r'''
import sys, time
sys.path.insert(0, "/tmp")
import cam3_i2c_pt as m

def P(*a):
    print(*a); sys.stdout.flush()

BASE = 0x20000400
CAM_EN = BASE + 0x40
STATE = {1: "IDLE", 2: "ADDR", 4: "DATA", 3: "ADDR_TAG", 5: "DATA_TAG", 6: "WAIT_TAG_DONE"}

d = m.PciDriver()
cam = m.CamI2c(d, BASE, verbose=False)

def r(o):
    return d.read32(BASE + o) & 0xFFFFFFFF

def snap(tag):
    st = r(0x60)
    code = (st >> 16) & 7
    P("%s +0x60=0x%08X  stab=%d/%s  wd[7:0]=%d  +0xf0=0x%08X  +0xa0=0x%08X  +0xd0=0x%08X  +0x50=0x%08X"
      % (tag, st, code, STATE.get(code, "?"), (st >> 24) & 0xFF,
         r(0xf0), r(0xa0), r(0xd0), r(0x50)))

def rate(o):
    a = r(o); time.sleep(1.0); b = r(o)
    return (b - a) & 0xFFFFFFFF

def full(tag):
    P("%s  PCLK=%d  VSYNC/s=%d  FRAMES/s=%d  BEATCNT/s=%d"
      % (tag, rate(0x10), rate(0x20), rate(0xf0), rate(0xa0)))

P("=== 84 MHz baseline ===")
full("base")
snap("base")

P("=== CAM_EN=0, go 48 MHz, CAM_EN=1 ===")
d.write32(CAM_EN, 0); time.sleep(0.8)
cam.write(0x3035, 0x11); cam.write(0x3036, 0x30); cam.write(0x3037, 0x13)
time.sleep(1.5)
d.write32(CAM_EN, 1); time.sleep(2.0)
for k in range(3):
    snap("48 #%d" % k); time.sleep(0.3)
full("48M ")

P("=== restore 84 MHz ===")
d.write32(CAM_EN, 0); time.sleep(0.8)
cam.write(0x3035, 0x11); cam.write(0x3036, 0x54); cam.write(0x3037, 0x13)
time.sleep(1.5)
d.write32(CAM_EN, 1); time.sleep(2.0)
snap("rest")
full("rest")

d.close()
P("BOARD DONE")
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
            print("ERR:", err.rstrip()[:300], flush=True)
    return out


c = connect()
print("=== stop viewer + link down ===")
sh(c, "pkill -9 -x run_camview.sh 2>/dev/null; sleep 1; pkill -9 -x camview 2>/dev/null; sleep 3; "
      "ps -eo comm | grep -E '^camview$' && echo STILL-RUNNING || echo 'camview stopped'")
sh(c, "rmmod pango_pci_driver 2>/dev/null; sleep 2; "
      "test -e %s && echo 1 > %s/remove; sleep 2; "
      "(test -e %s && echo 'still present') || echo 'device removed'" % (DEV, DEV, DEV))

print("=== JTAG configure ===")
r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "burn_now.py"), TCL],
                   cwd=ROOT, capture_output=True, timeout=420)
out = (r.stdout + r.stderr).decode("utf-8", "replace")
print(out.strip()[-400:], flush=True)
if "BURN OK" not in out:
    print("!! BURN FAILED"); c.close(); sys.exit(2)

print("=== rescan + insmod ===")
sh(c, "echo 1 > /sys/bus/pci/rescan; sleep 3; rmmod pango_pci_driver 2>/dev/null; sleep 1; "
      "insmod /root/ov5640/pango_pci_driver.ko && echo INSMOD_OK; sleep 4")

print("=== FSM-wedge diagnostic ===")
sftp = c.open_sftp()
sftp.put(os.path.join(ROOT, "tools", "cam3_i2c_pt.py"), "/tmp/cam3_i2c_pt.py")
with sftp.open("/tmp/_where.py", "w") as f:
    f.write(BOARD)
sh(c, "python3 -u /tmp/_where.py 2>&1", t=400)
sftp.close()

print("=== restart camview ===")
sh(c, "rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh "
      "> /tmp/camview.log 2>&1 < /dev/null & sleep 10; "
      "ps -eo comm | grep -E '^camview$' && echo CAMVIEW-RUNNING || echo 'camview NOT running'")
c.close()
print("DONE")
