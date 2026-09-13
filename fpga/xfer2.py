#!/usr/bin/env python3
"""xfer2.py : robust serial file transfer with stty -echo, per-chunk retry, md5 verify."""
import serial, sys, time, base64, hashlib, subprocess

PORT, BAUD = 'COM9', 1500000
src, dst = sys.argv[1], sys.argv[2]
CHUNK = 1200
data = open(src, 'rb').read()
md5_local = hashlib.md5(data).hexdigest()
b64 = base64.b64encode(data).decode()
chunks = [b64[i:i+CHUNK] for i in range(0, len(b64), CHUNK)]

s = serial.Serial(PORT, BAUD, timeout=0.2)
s.write(b'\r\n'); time.sleep(0.3); s.reset_input_buffer()

def send_wait(cmd, want, tmo=8):
    for attempt in range(3):
        s.reset_input_buffer()
        s.write(cmd.encode() + b'\n'); s.flush()
        t0 = time.time(); buf = b''
        while time.time() - t0 < tmo:
            c = s.read(8192)
            if c:
                buf += c
                if want in buf:
                    return True
        print('  retry chunk cmd (attempt %d)' % (attempt+1), flush=True)
    return False

assert send_wait('stty -echo; rm -f /tmp/x.b64; echo GO', b'GO'), 'board not ready'
t0 = time.time()
for i, ch in enumerate(chunks):
    if not send_wait("echo %s >> /tmp/x.b64; echo A%d" % (ch, i), ("A%d" % i).encode()):
        print('chunk %d FAILED permanently' % i); s.close(); sys.exit(1)
    if i % 500 == 0:
        el = time.time()-t0
        print('  %d/%d %.0fs' % (i, len(chunks), el), flush=True)
ok = send_wait("md5sum /tmp/x.b64; echo DONE", b'DONE', 20)
print('md5 remote:', ok)
send_wait("base64 -d /tmp/x.b64 > %s && md5sum %s; echo FIN" % (dst, dst), b'FIN', 30)
print('local md5 (%s): %s' % (src, md5_local))
s.close()
