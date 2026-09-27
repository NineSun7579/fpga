# -*- coding: utf-8 -*-
"""Sweep cam3's runtime DVP sampling delay (REG_DLY_STEP @ 0x20000430) and
score each value by back-to-back frame stability with the static colour bar.

Requires the CAM3DLY bitstream (port-mode GTP_IODELAY_E2 + REG_DLY_STEP).
"""
import itertools
import os
import sys
import time

import numpy as np
import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.203", "linaro", "123456"
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project"
OUT = os.path.join(ROOT, "tp", "dly")
os.makedirs(OUT, exist_ok=True)
W, H = 640, 480
PING = "0x01000000"
DLYREG = "0x20000430"

VALUES = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 255]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, 22, USER, PW, timeout=10, banner_timeout=15, auth_timeout=15,
          allow_agent=False, look_for_keys=False)


def sh(cmd, t=240, show=False):
    full = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    try:
        _, o, e = c.exec_command(full, timeout=t)
        out = o.read().decode("utf-8", "replace")
    except Exception as ex:  # noqa: BLE001
        print("TIMEOUT", cmd, ex)
        return ""
    if show:
        print("$", cmd)
        print(out.rstrip())
    return out


sftp = c.open_sftp()
for f in ("board_poke.py", "cam3_i2c_pt.py", "dump_cam3_frame.py", "cam_enable.py"):
    sftp.put(os.path.join(ROOT, "tools", f), "/tmp/" + f)
sftp.close()

sh("killall -9 camview 2>/dev/null; pkill -9 -f '[r]un_camview' 2>/dev/null; sleep 2; echo stopped")

names = []
try:
    sh("python3 /tmp/cam3_i2c_pt.py --quiet testpat on 2>&1", show=True)
    time.sleep(0.5)
    for v in VALUES:
        sh("python3 /tmp/board_poke.py w %s %d >/dev/null 2>&1" % (DLYREG, v))
        time.sleep(0.15)
        a, b = "dly_%03d_a" % v, "dly_%03d_b" % v
        sh("python3 /tmp/dump_cam3_frame.py %s /tmp/%s.ppm >/dev/null 2>&1" % (PING, a))
        sh("python3 /tmp/dump_cam3_frame.py %s /tmp/%s.ppm >/dev/null 2>&1" % (PING, b))
        names += [a, b]
        print("swept delay =", v)
finally:
    sh("python3 /tmp/board_poke.py w %s 40 >/dev/null 2>&1" % DLYREG)
    sh("python3 /tmp/cam3_i2c_pt.py --quiet testpat off 2>&1", show=True)
    sh("rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh "
       "> /tmp/camview.log 2>&1 < /dev/null & sleep 2; echo restarted", show=True)

sftp = c.open_sftp()
for nm in names:
    try:
        sftp.get("/tmp/%s.ppm" % nm, os.path.join(OUT, nm + ".ppm"))
    except Exception as e:  # noqa: BLE001
        print("dl fail", nm, e)
sftp.close()
c.close()


def load(p):
    d = open(p, "rb").read()
    i, toks = 0, []
    while len(toks) < 4:
        while d[i:i + 1].isspace():
            i += 1
        j = i
        while not d[j:j + 1].isspace():
            j += 1
        toks.append(d[i:j])
        i = j
    i += 1
    return np.frombuffer(d[i:i + W * H * 3], dtype=np.uint8).reshape(H, W, 3).astype(np.int32)


print()
print("%-6s %8s %8s %8s" % ("delay", "mean|d|", "frac>8", "corr"))
best = None
for v in VALUES:
    try:
        a = load(os.path.join(OUT, "dly_%03d_a.ppm" % v)).astype(np.float64)
        b = load(os.path.join(OUT, "dly_%03d_b.ppm" % v)).astype(np.float64)
    except Exception as e:  # noqa: BLE001
        print("%-6d  MISSING %s" % (v, e))
        continue
    d = np.abs(a - b).mean(axis=2)
    ca, cb = a.ravel() - a.mean(), b.ravel() - b.mean()
    corr = float(ca @ cb / (np.linalg.norm(ca) * np.linalg.norm(cb) + 1e-9))
    print("%-6d %8.2f %8.4f %8.4f" % (v, d.mean(), (d > 8).mean(), corr))
    score = d.mean()
    if best is None or score < best[1]:
        best = (v, score)
print("BEST delay by mean|diff| =", best)
