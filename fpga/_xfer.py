#!/usr/bin/env python3
import serial, sys, time, base64

PORT, BAUD = 'COM9', 1500000
src, dst = sys.argv[1], sys.argv[2]
data = open(src, 'rb').read()
b64 = base64.b64encode(data).decode()
CH = 800
chunks = [b64[i:i+CH] for i in range(0, len(b64), CH)]

s = serial.Serial(PORT, BAUD, timeout=0.2)
s.write(b'\x03\n'); time.sleep(0.4); s.reset_input_buffer()

def send_wait(cmd, want, tmo=6):
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

send_wait('rm -f /tmp/x.b64; echo GO', b'GO')
for i, ch in enumerate(chunks):
    if not send_wait("echo %s >> /tmp/x.b64; echo A%d" % (ch, i), ("A%d" % i).encode()):
        print('chunk %d failed' % i); s.close(); sys.exit(1)
ok = send_wait("base64 -d /tmp/x.b64 > %s && wc -c %s; echo DONE" % (dst, dst), b'DONE', 15)
print('wrote', dst, 'chunks', len(chunks), 'ok', ok)
s.close()
