#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_pull5.py <remote> <local> : chunked, md5-verified pull over the COM5 debug
console (1500000). Same protocol as pull2.py (600 B/chunk, per-chunk marker),
just retargeted to the CH340 debug port and with a couple of retries.
"""
import base64, hashlib, os, sys, time
import serial

PORT = os.environ.get('PULL_PORT', 'COM5')
BAUD = 1500000
CH = 384  # binary bytes per chunk (512 base64 chars) -- fewer round trips, still robust

remote, local = sys.argv[1], sys.argv[2]

s = serial.Serial(PORT, BAUD, timeout=0.2)
s.write(b'\x15\r\nconsole\r\n'); time.sleep(0.8)
s.write(b'\x15\r\nstty -echo\r\n'); time.sleep(0.4)
s.reset_input_buffer()


def cmd_out(cmd, want, tmo=15, tries=3):
    w = want.encode() if isinstance(want, str) else want
    buf = b''
    for _ in range(tries):
        s.reset_input_buffer()
        s.write(cmd.encode() + b'\n'); s.flush()
        t0 = time.time(); buf = b''
        while time.time() - t0 < tmo:
            c = s.read(16384)
            if c:
                buf += c
                if w in buf:
                    return buf.decode('utf-8', 'replace')
        time.sleep(0.2)
    return buf.decode('utf-8', 'replace')


out = cmd_out("md5sum %s; stat -c %%s %s; echo M$((5+5))ETA" % (remote, remote), 'M10ETA', 15)
md5_remote = None
for line in out.splitlines():
    t = line.strip()
    if len(t) >= 32 and all(c in '0123456789abcdef' for c in t[:32]):
        md5_remote = t[:32]; break
try:
    total = int(out.split('M10ETA')[0].strip().splitlines()[-1])
except Exception:
    print('size parse fail:', repr(out[:200])); sys.exit(1)
print('remote size', total, 'md5', md5_remote, flush=True)

b64_all = []
n_chunks = (total + CH - 1) // CH
B64CHARS = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=')
for i in range(n_chunks):
    skip = i * CH
    cnt = min(CH, total - skip)
    exp_len = 4 * ((cnt + 2) // 3)
    marker = 'ZK%dKZ' % i        # literal marker; command echo is off (stty -echo)
    got = None
    for attempt in range(6):
        out = cmd_out("tail -c +%d %s | head -c %d | base64 -w0; echo %s"
                      % (skip + 1, remote, cnt, marker), marker, 20)
        body = out.split(marker)[0]
        cand = ''.join(c for c in body if c in B64CHARS)
        if len(cand) >= exp_len:
            try:
                chunk = base64.b64decode(cand[-exp_len:])
                if len(chunk) == cnt:
                    got = chunk
                    break
            except Exception:
                pass
        time.sleep(0.15)
    if got is None:
        print('chunk %d FAILED after retries' % i); sys.exit(1)
    b64_all.append(got)
    if i % 20 == 0:
        print('  %d/%d' % (i, n_chunks), flush=True)

data = b''.join(b64_all)
md5_local = hashlib.md5(data).hexdigest()
open(local, 'wb').write(data)
print('local size', len(data), 'md5', md5_local)
ok = md5_local == md5_remote
print('MATCH' if ok else 'MISMATCH')
try:
    s.write(b'stty echo\n')
except Exception:
    pass
s.close()
sys.exit(0 if ok else 1)
