# -*- coding: utf-8 -*-
"""Check board + FPGA state and read the three camera debug blocks."""
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.241", "linaro", "123456"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    c.connect(HOST, 22, USER, PW, timeout=8, banner_timeout=15, auth_timeout=15,
              allow_agent=False, look_for_keys=False)
except Exception as e:
    print("CONNECT FAIL", e)
    sys.exit(1)


def run(cmd, t=40):
    _, o, e = c.exec_command(cmd, timeout=t)
    return (o.read() + e.read()).decode("utf-8", "replace")


print("=== uptime ===")
print(run("uptime").strip())
print("=== camview running? ===")
print(run("pgrep -af camview 2>&1 | head -5").strip() or "(none)")
print("=== pango driver ===")
print(run("lsmod 2>&1 | grep pango").strip() or "(not loaded)")
print("=== pci ===")
print(run("lspci -s 0002:21:00.0 2>&1").strip() or "(absent)")
print("=== /root/ov5640 ===")
print(run("ls -l /root/ov5640/ 2>&1 | head -20").strip())
print("=== df /tmp ===")
print(run("ls -l /tmp/*.log 2>&1 | head").strip())
c.close()
