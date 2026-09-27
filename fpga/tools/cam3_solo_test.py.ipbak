# -*- coding: utf-8 -*-
"""Decisive cam3 interleaving bisect.

Hypothesis-under-test: cam3's per-frame +/-1-burst (+/-128 px) tearing is caused
by multi-master interleaving on the shared DDR write arbiter, OR by cam3's own
capture/DVP path.

Method (zero rebuild):
  1. stop camview, enable cam3 test pattern (static colour bars)
  2. BASELINE: all 3 engines on -> dump cam3 ping/pong twice each
  3. SOLO: disable cam1+cam2 write engines (cam_en=0) -> dump cam3 ping/pong
  4. restore cam1+cam2, test pattern off, restart camview
  5. download both sets

If SOLO is clean (shift==0 everywhere, back-to-back identical) the corruption is
interleaving/arbiter; if SOLO still tears, it is cam3's own capture path.
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
for f in ("cam_enable.py", "cam3_i2c_pt.py", "dump_cam3_frame.py", "board_peek.py"):
    sftp.put(os.path.join(ROOT, "tools", f), "/tmp/" + f)
sftp.close()
print("uploaded tools")

# stop viewer
sh("killall -9 camview 2>/dev/null; pkill -9 -f '[r]un_camview' 2>/dev/null; sleep 2; "
   "pgrep -af camview | head -3; echo STOPPED")

names = []
try:
    # enable test pattern
    sh("python3 /tmp/cam3_i2c_pt.py --quiet testpat on 2>&1")
    sh("python3 /tmp/cam3_i2c_pt.py --quiet rd 0x503d 2>&1")

    # ---- BASELINE: all engines on ----
    for tag, delay in (("a", 0), ("b", 0), ("c", 3)):
        if delay:
            time.sleep(delay)
        for buf, base in (("ping", 0x01000000), ("pong", 0x01200000)):
            nm = "solo_base_%s_%s" % (buf, tag)
            sh("python3 /tmp/dump_cam3_frame.py 0x%08X /tmp/%s.ppm 2>&1" % (base, nm), show=False)
            names.append(nm)
            print("dumped", nm)

    # ---- SOLO: cam3 is the only write master ----
    sh("python3 /tmp/cam_enable.py --cam1 0 --cam2 0 2>&1")
    time.sleep(2)
    sh("python3 /tmp/board_peek.py 0x20000410 0x20000420 0x200004A0 0x200004F0 2>&1 || true")
    for tag, delay in (("a", 0), ("b", 0), ("c", 3)):
        if delay:
            time.sleep(delay)
        for buf, base in (("ping", 0x01000000), ("pong", 0x01200000)):
            nm = "solo_only_%s_%s" % (buf, tag)
            sh("python3 /tmp/dump_cam3_frame.py 0x%08X /tmp/%s.ppm 2>&1" % (base, nm), show=False)
            names.append(nm)
            print("dumped", nm)
finally:
    # ---- restore ----
    sh("python3 /tmp/cam_enable.py --cam1 1 --cam2 1 2>&1")
    sh("python3 /tmp/cam3_i2c_pt.py --quiet testpat off 2>&1")
    sh("python3 /tmp/cam3_i2c_pt.py --quiet rd 0x503d 2>&1")
    sh("rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh > /tmp/camview.log 2>&1 < /dev/null & "
       "sleep 2; echo RESTARTED")

sftp = c.open_sftp()
for nm in names:
    rp = "/tmp/%s.ppm" % nm
    lp = os.path.join(LOCAL_OUT, "%s.ppm" % nm)
    try:
        sftp.get(rp, lp)
        print("downloaded", lp, os.path.getsize(lp))
    except Exception as e:  # noqa: BLE001
        print("download FAIL", nm, e)
sftp.close()
c.close()
print("DONE")
