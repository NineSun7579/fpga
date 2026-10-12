# -*- coding: utf-8 -*-
"""dl_serial.py -- download a file from the board over the debug UART.

Runs `base64 -w 0 <remote>` on the board and decodes the stream locally.

Usage: python tools/dl_serial.py <remote_path> <local_path> [port] [timeout_s]
"""
import base64
import re
import sys
import time

import serial

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

remote = sys.argv[1]
local = sys.argv[2]
port = sys.argv[3] if len(sys.argv) > 3 else "COM5"
tmo = int(sys.argv[4]) if len(sys.argv) > 4 else 240

PROMPT = b"root@linaro-alip:/#"
cmd = "base64 -w 0 " + remote

s = serial.Serial(port, 1500000, timeout=0.3)
s.reset_input_buffer()
s.write(b"\r")
time.sleep(0.8)
s.reset_input_buffer()

s.write((cmd + "\r").encode())
s.flush()

buf = bytearray()
t0 = time.time()
last = time.time()
got_prompt = False
while time.time() - t0 < tmo:
    d = s.read(65536)
    if d:
        buf += d
        last = time.time()
        if PROMPT in buf:
            got_prompt = True
            break
    else:
        # stop early if stalled for a while after some data
        if len(buf) > 1000 and time.time() - last > 10:
            break
s.close()

text = bytes(buf).decode("utf-8", "replace")
# strip echoed command
idx = text.find(cmd)
if idx >= 0:
    text = text[idx + len(cmd):]
# strip prompt tail
p = text.find("root@linaro-alip")
if p >= 0:
    text = text[:p]
b64 = re.sub(r"[^A-Za-z0-9+/=]", "", text)
print("captured %d raw bytes, %d b64 chars, got_prompt=%s" % (len(buf), len(b64), got_prompt))
try:
    data = base64.b64decode(b64, validate=False)
except Exception as e:
    print("decode error:", e)
    data = base64.b64decode(b64 + "=" * (-len(b64) % 4))
open(local, "wb").write(data)
print("wrote", local, len(data), "bytes")
