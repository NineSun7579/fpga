#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_run_read.py -- run a shell command on the RK3568 and read output for a
fixed number of seconds (avoids the early-break on echoed markers).

Usage:
  python _run_read.py "<shell command>" [seconds]
"""
import base64
import sys
import time

import serial

PORT, BAUD = "COM5", 1500000


def run(cmd, secs=20.0):
    s = serial.Serial(PORT, BAUD, timeout=0.2)
    s.write(b"\x03"); time.sleep(0.5)
    s.write(b"\x15\r\nconsole\r\n"); time.sleep(0.8)
    s.reset_input_buffer()
    s.write(("echo %s | base64 -d | bash\n"
             % base64.b64encode(cmd.encode()).decode()).encode())
    t0 = time.time()
    buf = b""
    while time.time() - t0 < secs:
        c = s.read(65536)
        if c:
            buf += c
    s.close()
    txt = buf.decode("utf-8", "replace")
    # drop the echoed command line (contains the base64 blob)
    lines = [l for l in txt.splitlines() if "base64 -d | bash" not in l]
    return "\n".join(lines)


def main():
    cmd = sys.argv[1]
    secs = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
    print(run(cmd, secs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
