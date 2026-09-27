#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_sh5.py <bash-snippet> [timeout_s]

Run a bash snippet on the RK3568 board over the debug console (COM5 @1500000).

The snippet is base64-encoded before being sent, so PowerShell quoting, `$`,
backticks and loops are all safe.  Ctrl-C is sent first to clear any pending
or continuation (PS2) input left over from a previous mangled command.

Reads until the __EOC__ marker, so the snippet must not itself print __EOC__.
"""
import base64
import os
import sys
import time

import serial

PORT = os.environ.get('BRD_PORT', 'COM5')
BAUD = 1500000

arg = sys.argv[1]
if arg.startswith('@'):
    snippet = open(arg[1:], 'rb').read().decode('utf-8').replace('\r\n', '\n')
else:
    snippet = arg
tmo = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
b64 = base64.b64encode(snippet.encode()).decode()

s = serial.Serial(PORT, BAUD, timeout=0.2)
s.write(b'\x03\r\n'); time.sleep(0.5)
s.write(b'stty sane 2>/dev/null\r\n'); time.sleep(0.3)
s.reset_input_buffer()
s.write(("echo %s | base64 -d | bash; echo __E''OC__\n" % b64).encode())
s.flush()

t0 = time.time()
buf = b''
while time.time() - t0 < tmo:
    c = s.read(65536)
    if c:
        buf += c
        if b'__EOC__' in buf:
            break
s.close()

text = buf.decode('utf-8', 'replace')
lines = [l for l in text.splitlines()
         if '__EOC__' not in l and 'base64 -d | bash' not in l]
print('\n'.join(lines))
