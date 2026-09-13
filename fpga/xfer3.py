#!/usr/bin/env python3
"""xfer3.py : resumable serial transfer. Re-run after FIQ console recovery; continues where it left off."""
import serial, sys, time, base64, hashlib

PORT, BAUD = 'COM9', 1500000
src, dst, tmp = sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else '/root/x.b64'
CHUNK = 1200
data = open(src, 'rb').read()
md5_local = hashlib.md5(data).hexdigest()
b64 = base64.b64encode(data).decode()
chunks = [b64[i:i+CHUNK] for i in range(0, len(b64), CHUNK)]
N = len(chunks)
print('total chunks:', N, 'local md5:', md5_local, flush=True)

s = serial.Serial(PORT, BAUD, timeout=0.2)

def send_wait(cmd, want, tmo=8):
    s.reset_input_buffer()
    s.write(cmd.encode() + b'\n'); s.flush()
    t0 = time.time(); buf = b''
    while time.time() - t0 < tmo:
        c = s.read(8192)
        if c:
            buf += c
            if want in buf:
                return True
    return False

if not send_wait('stty -echo; echo READY', b'READY', 5):
    print('FATAL: board not responding (FIQ? run: python -c "ser..console first")'); sys.exit(2)

# 已完整块数 = floor(size / (CHUNK+1))，并截掉尾部残块
if not send_wait('wc -c < ' + tmp + ' 2>/dev/null; echo SZ', b'SZ', 5):
    print('FATAL: size query failed'); sys.exit(2)
time.sleep(0.2)
s.reset_input_buffer()
s.write(b'wc -c < ' + tmp.encode() + b' 2>/dev/null | tr -d \\\\n; echo SZEND\n')
t0 = time.time(); buf = b''
while time.time() - t0 < 5:
    c = s.read(4096)
    if c: buf += c
    if b'SZEND' in buf: break
try:
    line = buf.split(b'SZEND')[0]
    digits = b''.join(ch for ch in line if 48 <= ch <= 57)
    size = int(digits) if digits else 0
except Exception:
    size = 0
done = size // (CHUNK + 1)
print('existing bytes:', size, '-> complete chunks:', done, flush=True)
if done > 0:
    send_wait('truncate -s %d %s; echo TR' % (done * (CHUNK + 1), tmp), b'TR', 5)

t0 = time.time()
for i in range(done, N):
    ok = False
    for attempt in range(2):
        if send_wait("echo %s >> %s; echo A%d" % (chunks[i], tmp, i), ("A%d" % i).encode()):
            ok = True; break
        # 尝试失败：可能已写入但应答丢失 -> 检查并修正
        if send_wait('wc -c < %s; echo Q' % tmp, b'Q', 4):
            time.sleep(0.15); s.reset_input_buffer()
            s.write(b'wc -c < ' + tmp.encode() + b' | tr -d \\\\n; echo QEND\n')
            tb = b''; t1 = time.time()
            while time.time() - t1 < 4:
                c = s.read(4096)
                if c: tb += c
                if b'QEND' in tb: break
            try:
                sz2 = int(b''.join(ch for ch in tb.split(b'QEND')[0] if 48 <= ch <= 57) or 0)
            except Exception:
                sz2 = 0
            want = (i + 1) * (CHUNK + 1)
            if sz2 >= want:
                ok = True; break
            if sz2 > i * (CHUNK + 1):
                send_wait('truncate -s %d %s; echo TR' % (i * (CHUNK + 1), tmp), b'TR', 5)
    if not ok:
        print('chunk %d failed - rerun after console recovery' % i); s.close(); sys.exit(1)
    if i % 400 == 0:
        print('  %d/%d %.0fs' % (i, N, time.time()-t0), flush=True)

send_wait('base64 -d %s > %s && md5sum %s; echo FIN' % (tmp, dst, dst), b'FIN', 40)
print('DONE local md5:', md5_local)
s.close()
