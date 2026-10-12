#!/usr/bin/env python3
"""pull2.py <remote> <local> : 分块拉取板端文件并校验"""
import serial, sys, time, base64, hashlib

PORT, BAUD = 'COM9', 1500000
remote, local = sys.argv[1], sys.argv[2]
CH = 600   # bytes of binary per chunk (base64 ~800 chars)

s = serial.Serial(PORT, BAUD, timeout=0.2)
s.write(b'\x15\r\nconsole\r\n'); time.sleep(0.8)
s.write(b'\x15\r\nstty -echo\r\n'); time.sleep(0.4)
s.reset_input_buffer()

def cmd_out(cmd, want, tmo=10):
    s.reset_input_buffer()
    s.write(cmd.encode() + b'\n'); s.flush()
    t0 = time.time(); buf = b''
    while time.time() - t0 < tmo:
        c = s.read(16384)
        if c:
            buf += c
            if (want.encode() if isinstance(want,str) else want) in buf:
                break
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
for i in range(n_chunks):
    skip = i * CH
    cnt = min(CH, total - skip)
    want = 'C$((%d))XD' % i
    expect = 'C%dxD' % i
    out = cmd_out("tail -c +%d %s | head -c %d | base64 -w0; echo %s" % (skip + 1, remote, cnt, want),
                  expect, 15)
    # 提取 base64 部分: expect 标记之前的一行
    body = out.split(expect)[0]
    lines = [l.strip() for l in body.splitlines() if len(l.strip()) > 20]
    line = lines[-1] if lines else ''
    try:
        b64_all.append(base64.b64decode(line))
    except Exception as e:
        print('chunk %d decode fail: %r' % (i, line[:60])); sys.exit(1)
    if i % 10 == 0:
        print('  %d/%d' % (i, n_chunks), flush=True)

data = b''.join(b64_all)
md5_local = hashlib.md5(data).hexdigest()
open(local, 'wb').write(data)
print('local size', len(data), 'md5', md5_local)
print('MATCH' if md5_local == md5_remote else 'MISMATCH')
s.close()
sys.exit(0 if md5_local == md5_remote else 1)
