#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_pull_file.py -- pull a remote file from the RK3568 over serial (base64).

Usage:
  python _pull_file.py <remote_path> <local_path> [read_seconds]
"""
import base64
import sys
import time

import serial

PORT, BAUD = "COM5", 1500000
_B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="


def pull(remote, read_s=25.0):
    s = serial.Serial(PORT, BAUD, timeout=0.2)
    s.write(b"\x03"); time.sleep(0.5)
    s.write(b"\x15\r\nconsole\r\n"); time.sleep(0.8)
    s.reset_input_buffer()
    cmd = "echo B64S; base64 -w0 %s; echo; echo B64E" % remote
    s.write(("echo %s | base64 -d | bash\n"
             % base64.b64encode(cmd.encode()).decode()).encode())
    t0 = time.time()
    buf = b""
    while time.time() - t0 < read_s:
        c = s.read(65536)
        if c:
            buf += c
    s.close()
    txt = buf.decode("utf-8", "replace")
    i = txt.rfind("B64S")
    j = txt.rfind("B64E")
    if i < 0 or j < 0 or j <= i:
        return None
    payload = "".join(ch for ch in txt[i + 4:j] if ch in _B64)
    payload = payload[:len(payload) // 4 * 4]
    return base64.b64decode(payload)


def main():
    remote = sys.argv[1]
    local = sys.argv[2]
    read_s = float(sys.argv[3]) if len(sys.argv) > 3 else 25.0
    data = pull(remote, read_s)
    if data is None:
        print("PULL FAILED")
        return 1
    with open(local, "wb") as f:
        f.write(data)
    print("wrote %s (%d bytes)" % (local, len(data)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
