#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_push5.py <localfile> <remote> : chunked HEX push over the COM5 debug console.

Uppercase-HEX alphabet keeps the literal 'fiq' out of the stream; each chunk is
followed by its own marker so a dropped byte is detected immediately, and the
final md5 pins the whole file.  (Playbook: the 1.5M CH340 link cannot be trusted
for raw multi-KB bursts.)
"""
import hashlib
import os
import sys
import time

import serial

PORT = os.environ.get('BRD_PORT', 'COM5')
BAUD = 1500000
CHUNK = 900          # hex chars per command (~450 bytes of payload)

src, dst = sys.argv[1], sys.argv[2]
data = open(src, 'rb').read()
md5 = hashlib.md5(data).hexdigest()
hx = data.hex().upper()
chunks = [hx[i:i + CHUNK] for i in range(0, len(hx), CHUNK)]

s = serial.Serial(PORT, BAUD, timeout=0.2)
s.write(b'\x15\r\nstty -echo\r\n')
time.sleep(0.6)
s.reset_input_buffer()


def cmd(c, want, tmo=10, tries=4):
    w = want.encode() if isinstance(want, str) else want
    for _ in range(tries):
        s.reset_input_buffer()
        s.write(c.encode() + b'\n')
        s.flush()
        t0 = time.time()
        buf = b''
        while time.time() - t0 < tmo:
            x = s.read(16384)
            if x:
                buf += x
                if w in buf:
                    return True
        time.sleep(0.2)
    return False


if not cmd('echo RY4DY', 'RY4DY', 6):
    print('board not ready')
    sys.exit(2)

print('push %s -> %s : %d bytes, %d chunks, md5=%s'
      % (src, dst, len(data), len(chunks), md5), flush=True)

if not cmd('rm -f /tmp/xh', 'RY4DY', 6, tries=1):
    pass
cmd('rm -f /tmp/xh; echo G9GO', 'G9GO', 6, tries=3)

for i, ch in enumerate(chunks):
    if not cmd('echo %s >> /tmp/xh; echo ZK%dKZ' % (ch, i), 'ZK%dKZ' % i, 12):
        print('chunk %d failed' % i)
        sys.exit(1)
    if i % 4 == 0:
        print('  %d/%d' % (i, len(chunks)), flush=True)

dec = ("python3 -c \"import binascii;d=open('/tmp/xh').read();"
       "d=''.join(c for c in d if c in '0123456789ABCDEFabcdef');"
       "open('%s','wb').write(binascii.unhexlify(d))\"; rm -f /tmp/xh; echo DN12DNE"
       % dst)
cmd(dec, 'DN12DNE', 40, tries=2)

s.reset_input_buffer()
s.write(("md5sum %s; ls -l %s; echo MH7MH\n" % (dst, dst)).encode())
s.flush()
t0 = time.time()
buf = b''
while time.time() - t0 < 25:
    x = s.read(16384)
    if x:
        buf += x
        if b'MH7MH' in buf:
            break
out = buf.decode('utf-8', 'replace')
print('\n'.join(l for l in out.splitlines() if 'MH7MH' not in l))
print('MATCH' if md5 in out else 'MISMATCH')
s.close()
sys.exit(0 if md5 in out else 1)
