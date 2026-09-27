# -*- coding: utf-8 -*-
"""Compare cam1 (known-good) vs cam3 raw DVP edge counters.

Registers (per camera BASE = 0x20000000 / 0x20000200 / 0x20000400):
  +0x10 dbg_pclk_cnt     pclk edges seen in video_clk domain
  +0x20 dbg_vsyncs       filtered vsync rising edges
  +0x90 dbg_href_raw     RAW cam_href rising edges (cam_pclk domain)
  +0xE0 dbg_vsync_raw    RAW cam_vsync rising edges (cam_pclk domain)
  +0xF0 dbg_last_cnt     completed frames
"""
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.241", "linaro", "123456"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, 22, USER, PW, timeout=10, banner_timeout=15, auth_timeout=15,
          allow_agent=False, look_for_keys=False)


def sh(cmd, t=120):
    full = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    _, o, e = c.exec_command(full, timeout=t)
    return o.read().decode("utf-8", "replace"), e.read().decode("utf-8", "replace")


def peek(addrs):
    o, _ = sh("python3 /tmp/board_peek.py " + " ".join(addrs))
    out = {}
    for line in o.strip().splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0].startswith("0x"):
            out[int(parts[0], 16)] = int(parts[2], 16)
    return out


sh("killall -9 camview 2>/dev/null; pkill -9 -f '[r]un_camview' 2>/dev/null; sleep 2; echo stopped")

OFFS = {"pclk": 0x10, "vsyncs": 0x20, "href_raw": 0x90, "vsync_raw": 0xE0, "frames": 0xF0}
CAMS = {"cam1": 0x20000000, "cam2": 0x20000200, "cam3": 0x20000400}
samples = []
try:
    for i in range(3):
        s = {}
        for name, base in CAMS.items():
            addrs = [base + off for off in OFFS.values()]
            r = peek(["0x%08X" % a for a in addrs])
            s[name] = {k: r.get(base + off, -1) for k, off in OFFS.items()}
        samples.append(s)
        print("sample", i, s)
        time.sleep(2.0)
finally:
    sh("rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh "
       "> /tmp/camview.log 2>&1 < /dev/null & sleep 2; echo restarted")
c.close()

print()
print("%-6s %-10s %12s %12s %12s %12s" % ("cam", "metric", "ds0->1", "ds1->2", "avg/s", "ratio-ish"))
for name in CAMS:
    for k in ("pclk", "vsyncs", "vsync_raw", "href_raw", "frames"):
        d = [samples[j + 1][name][k] - samples[j][name][k] for j in range(len(samples) - 1)]
        avg = sum(d) / len(d) / 2.0
        print("%-6s %-10s %12d %12d %12.1f" % (name, k, d[0], d[1], avg))
    print()
