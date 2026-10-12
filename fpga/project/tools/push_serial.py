# -*- coding: utf-8 -*-
"""push_serial.py -- push a local file to the board over the debug UART.

Robust against the systematic byte drops seen on the board->PC direction:
each chunk is written to a temp file on the board and verified by md5 (only a
32-char line travels back), then decoded/appended.  The upstream direction is
reliable, so this converges even when a whole-file transfer would not.

Usage: python tools/push_serial.py <local> <remote> [port] [chunk_bytes]
"""
import base64
import hashlib
import os
import re
import sys
import time

import serial

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

local, remote = sys.argv[1], sys.argv[2]
port = sys.argv[3] if len(sys.argv) > 3 else "COM5"
CHUNK = int(sys.argv[4]) if len(sys.argv) > 4 else 2048

PROMPT = b"root@linaro-alip:/#"
ANSI = re.compile(rb"\x1b\[[0-9;?]*[a-zA-Z]")
TMP = "/tmp/_push.b64"
BIN = "/tmp/_push.bin"


class Uart:
    def __init__(self):
        self.s = serial.Serial(port, 1500000, timeout=0.3)
        self.s.reset_input_buffer()
        self.s.write(b"\r")
        time.sleep(0.8)
        self.s.reset_input_buffer()

    def run(self, cmd, tmo=40):
        self.s.write((cmd + "\r").encode())
        self.s.flush()
        buf = b""
        t0 = time.time()
        while time.time() - t0 < tmo:
            d = self.s.read(65536)
            if d:
                buf += d
                if buf.rstrip().endswith(PROMPT) or PROMPT in buf.split(b"\r\n")[-1]:
                    break
            else:
                if buf.rstrip().endswith(PROMPT):
                    break
        return ANSI.sub(b"", buf).decode("utf-8", "replace")

    def close(self):
        self.s.close()


def md5(s):
    return hashlib.md5(s).hexdigest()


data = open(local, "rb").read()
want = hashlib.md5(data).hexdigest()
n = (len(data) + CHUNK - 1) // CHUNK
print("push %s -> %s  %d bytes, %d chunks, md5=%s" % (local, remote, len(data), n, want))

u = Uart()
try:
    u.run("rm -f %s %s" % (TMP, BIN))
    t0 = time.time()
    for i in range(n):
        chunk = data[i * CHUNK:(i + 1) * CHUNK]
        b64 = base64.b64encode(chunk).decode()
        exp = md5(b64.encode())
        for attempt in range(1, 6):
            out = u.run("printf %%s '%s' > %s; md5sum %s" % (b64, TMP, TMP))
            m = re.search(r"([0-9a-f]{32})\s+%s" % re.escape(TMP), out)
            if m and m.group(1) == exp:
                break
            print("   chunk %d/%d attempt %d md5 mismatch, retry" % (i + 1, n, attempt), flush=True)
            time.sleep(0.3)
        else:
            print("!! chunk %d failed after retries" % i)
            sys.exit(1)
        u.run("base64 -d %s >> %s" % (TMP, BIN))
        if (i + 1) % 4 == 0 or i + 1 == n:
            print("   %d/%d chunks (%.0f%%) %.0fs" % (i + 1, n, 100.0 * (i + 1) / n, time.time() - t0), flush=True)

    out = u.run("md5sum %s; wc -c < %s" % (BIN, BIN), tmo=30)
    print(out.strip())
    if want not in out:
        print("RESULT: MD5 MISMATCH -- target NOT replaced")
        sys.exit(2)
    u.run("cp -f %s %s && echo INSTALLED" % (BIN, remote))
    print("RESULT: OK --", remote, "installed")
finally:
    u.close()
