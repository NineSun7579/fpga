# -*- coding: utf-8 -*-
"""cam3 static-vs-live isolation.

Stop the viewer, dump cam3 live scene (ping+pong) from DDR, switch the OV5640 to
its static colour-bar test pattern (identical DVP pclk/vsync/href timing but
frame-invariant pixel data), dump again, restore live mode and the viewer.

Interpretation:
  live scrambled + static bars clean  -> the DDR buffer mixes several live frames
                                         (write-path drops/desync under backpressure)
  both scrambled                      -> capture/address path is broken regardless
                                         of content
  both clean                          -> only the live sensor data is bad (physical)
"""
import os
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.241", "linaro", "123456"
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, 22, USER, PW, timeout=10, banner_timeout=15, auth_timeout=15,
          allow_agent=False, look_for_keys=False)


def run(cmd, t=180):
    full = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    _, o, e = c.exec_command(full, timeout=t)
    return o.read().decode("utf-8", "replace"), e.read().decode("utf-8", "replace")


def dump(tag, base):
    out, err = run("python3 /tmp/dump_cam3_frame.py %s /tmp/%s.ppm 2>&1" % (base, tag))
    print(tag, base, out.strip()[-120:], err.strip()[:200])


sftp = c.open_sftp()
sftp.put(os.path.join(ROOT, "tools", "cam3_i2c_pt.py"), "/tmp/cam3_i2c_pt.py")
sftp.put(os.path.join(ROOT, "tools", "dump_cam3_frame.py"), "/tmp/dump_cam3_frame.py")
sftp.close()

print("== ensure viewers stopped ==")
out, err = run("killall -9 camview 2>/dev/null; pkill -9 -f '[r]un_camview' 2>/dev/null; sleep 3; "
               "pgrep -a camview; echo done")
print(out.strip(), err.strip()[:200])

print("== live dumps ==")
dump("c3live", "0x01000000")
dump("c3live_p", "0x01200000")

print("== testpat on ==")
out, err = run("python3 /tmp/cam3_i2c_pt.py testpat on 2>&1")
print(out.strip(), err.strip()[:300])
time.sleep(1.5)

print("== readback 0x503d (expect 0x80) ==")
out, err = run("python3 /tmp/cam3_i2c_pt.py rd 0x503d 2>&1")
print(out.strip(), err.strip()[:300])

print("== testpat dumps ==")
dump("c3tp", "0x01000000")
dump("c3tp_p", "0x01200000")

print("== testpat off ==")
out, err = run("python3 /tmp/cam3_i2c_pt.py testpat off 2>&1")
print(out.strip(), err.strip()[:300])

print("== restart viewer ==")
out, err = run("rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh > /tmp/camview.log 2>&1 < /dev/null & sleep 3; echo restarted")
print(out.strip())

sftp = c.open_sftp()
for name in ("c3live", "c3live_p", "c3tp", "c3tp_p"):
    try:
        sftp.get("/tmp/%s.ppm" % name, os.path.join(ROOT, "%s_raw.ppm" % name))
        print("fetched", name, os.path.getsize(os.path.join(ROOT, "%s_raw.ppm" % name)))
    except Exception as e:  # noqa: BLE001
        print("fetch fail", name, e)
sftp.close()
c.close()
