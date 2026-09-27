# -*- coding: utf-8 -*-
"""Verify cam3 on the rebuilt (port-mode IODELAY) bitstream.

  A. liveness: frames/vsyncs/pclk/words counters advance
  B. colour-bar structure + frame-to-frame stability (5 dumps)
  C. read-path identity under freeze (freeze cam3, dump 3x)
  D. restore: normal mode, camview restarted
"""
import os
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.203", "linaro", "123456"
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project"
OUT = os.path.join(ROOT, "tp", "vrfy")
os.makedirs(OUT, exist_ok=True)

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


def peek(addrs):
    o = sh("python3 /tmp/board_peek.py " + " ".join(addrs), show=True)
    r = {}
    for line in o.strip().splitlines():
        p = line.split()
        if len(p) >= 3 and p[0].startswith("0x"):
            r[int(p[0], 16)] = int(p[2], 16)
    return r


sftp = c.open_sftp()
for f in ("board_peek.py", "cam3_i2c_pt.py", "dump_cam3_frame.py", "cam_enable.py",
          "cam3_seten.py"):
    sftp.put(os.path.join(ROOT, "tools", f), "/tmp/" + f)
sftp.close()

sh("killall -9 camview 2>/dev/null; pkill -9 -f '[r]un_camview' 2>/dev/null; sleep 2; echo stopped")

names = []
try:
    print("== A. liveness (cam3 BASE 0x20000400) ==")
    a = peek(["0x20000410", "0x20000420", "0x20000430", "0x200004F0"])
    time.sleep(3.0)
    b = peek(["0x20000410", "0x20000420", "0x20000430", "0x200004F0"])
    for k in ("0x20000410", "0x20000420", "0x20000430", "0x200004F0"):
        print("   %s delta over 3s = %d" % (k, b.get(k, 0) - a.get(k, 0)))

    print("== B. colour bars: 5 dumps of ping/pong ==")
    sh("python3 /tmp/cam3_i2c_pt.py --quiet testpat on 2>&1", show=True)
    time.sleep(0.5)
    for nm, base in (("bar_ping_1", "0x01000000"), ("bar_ping_2", "0x01000000"),
                     ("bar_ping_3", "0x01000000"), ("bar_pong_1", "0x01200000"),
                     ("bar_pong_2", "0x01200000")):
        sh("python3 /tmp/dump_cam3_frame.py %s /tmp/%s.ppm >/dev/null 2>&1" % (base, nm))
        names.append(nm)
        print("   dumped", nm)

    print("== C. read-path identity under freeze ==")
    sh("python3 /tmp/cam3_seten.py 0 2>&1", show=True)
    time.sleep(1.0)
    for nm in ("frz2_a", "frz2_b", "frz2_c"):
        sh("python3 /tmp/dump_cam3_frame.py 0x01000000 /tmp/%s.ppm >/dev/null 2>&1" % nm)
        names.append(nm)
        print("   dumped", nm)
finally:
    sh("python3 /tmp/cam3_seten.py 1 2>&1")
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
print("DONE")
