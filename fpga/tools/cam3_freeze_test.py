# -*- coding: utf-8 -*-
"""Decisive cam3 read-vs-write discriminator (zero rebuild).

The F2H frame dump is non-atomic and takes longer than one frame interval, so
"back-to-back dumps differ" alone does NOT prove the DDR content is corrupt.

Method:
  1. stop camview, enable cam3 test pattern (static colour bars)
  2. dump cam3 ping 3x while RUNNING   -> instability baseline
  3. write REG_CAM_EN=0 for cam3 (0x20000440) to FREEZE the frame in DDR
  4. dump cam3 ping 3x while FROZEN    -> repeated reads of identical memory
  5. restore cam3, test pattern off, restart camview

Interpretation:
  * frozen dumps identical  -> READ path clean; instability is real WRITTEN
    content (write-path corruption).
  * frozen dumps differ     -> the read/dump path itself is corrupting frames.
"""
import os
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.241", "linaro", "123456"
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project"
LOCAL_OUT = os.path.join(ROOT, "tp")
os.makedirs(LOCAL_OUT, exist_ok=True)

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, 22, USER, PW, timeout=10, banner_timeout=15, auth_timeout=15,
          allow_agent=False, look_for_keys=False)


def sh(cmd, t=240, show=True):
    full = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    try:
        _, o, e = c.exec_command(full, timeout=t)
        out = o.read().decode("utf-8", "replace")
        err = e.read().decode("utf-8", "replace")
    except Exception as ex:  # noqa: BLE001
        print("$", cmd)
        print("TIMEOUT/ERR:", ex)
        return ""
    if show:
        print("$", cmd)
        if out.strip():
            print(out.rstrip())
        if err.strip() and "password for" not in err:
            print("ERR:", err.rstrip()[:400])
    return out


sftp = c.open_sftp()
for f in ("cam3_i2c_pt.py", "dump_cam3_frame.py", "board_peek.py", "cam_enable.py",
          "cam3_seten.py"):
    sftp.put(os.path.join(ROOT, "tools", f), "/tmp/" + f)
sftp.close()
print("uploaded tools")

sh("killall -9 camview 2>/dev/null; pkill -9 -f '[r]un_camview' 2>/dev/null; sleep 2; echo STOPPED")

names = []
try:
    sh("python3 /tmp/cam3_i2c_pt.py --quiet testpat on 2>&1")
    time.sleep(0.5)

    # --- running: 3 dumps ---
    for tag in ("a", "b", "c"):
        nm = "frz_run_%s" % tag
        sh("python3 /tmp/dump_cam3_frame.py 0x01000000 /tmp/%s.ppm 2>&1" % nm, show=False)
        names.append(nm)
        print("dumped", nm)

    # --- freeze cam3 ---
    sh("python3 /tmp/cam3_seten.py 0 2>&1")
    time.sleep(1.0)
    sh("python3 /tmp/board_peek.py 0x20000410 0x20000420 0x200004F0 2>&1 || true")

    # --- frozen: 3 dumps ---
    for tag in ("a", "b", "c"):
        nm = "frz_frozen_%s" % tag
        sh("python3 /tmp/dump_cam3_frame.py 0x01000000 /tmp/%s.ppm 2>&1" % nm, show=False)
        names.append(nm)
        print("dumped", nm)
finally:
    sh("python3 /tmp/cam3_seten.py 1 2>&1")
    sh("python3 /tmp/cam_enable.py --cam1 1 --cam2 1 2>&1")
    sh("python3 /tmp/cam3_i2c_pt.py --quiet testpat off 2>&1")
    sh("rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh > /tmp/camview.log 2>&1 < /dev/null & "
       "sleep 2; echo RESTARTED")

sftp = c.open_sftp()
for nm in names:
    try:
        sftp.get("/tmp/%s.ppm" % nm, os.path.join(LOCAL_OUT, "%s.ppm" % nm))
        print("downloaded", nm)
    except Exception as e:  # noqa: BLE001
        print("download FAIL", nm, e)
sftp.close()
c.close()
print("DONE")
