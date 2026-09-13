#!/usr/bin/env python3
"""xfer_hex.py <localfile> <dstpath> : 大写HEX编码传输, 字母表0-9A-F 不含fiq/FIQ, 免疫FIQ调试器触发。"""
import serial, sys, time, hashlib

PORT, BAUD = 'COM9', 1500000
src, dst = sys.argv[1], sys.argv[2]
CHUNK = 2000   # hex chars per command (~1000 bytes data)
data = open(src, 'rb').read()
md5_local = hashlib.md5(data).hexdigest()
hx = data.hex().upper()
chunks = [hx[i:i+CHUNK] for i in range(0, len(hx), CHUNK)]

s = serial.Serial(PORT, BAUD, timeout=0.2)

def send_wait(cmd, want, tmo=8):
    w = want.encode() if isinstance(want, str) else want
    for _ in range(3):
        s.reset_input_buffer()
        s.write(cmd.encode() + b'\n'); s.flush()
        t0 = time.time(); buf = b''
        while time.time() - t0 < tmo:
            c = s.read(8192)
            if c:
                buf += c
                if w in buf:
                    return True
    return False

ready = False
for attempt in range(8):
    s.write(b'\x15\x15\r\n'); time.sleep(0.3)
    s.write(b'console\r\n'); time.sleep(0.8)
    s.write(b'\x15\r\n'); time.sleep(0.4)
    if send_wait('stty -echo; rm -f /tmp/xh; echo G$((4+4))O', 'G8O', 4):
        ready = True
        break
if not ready:
    print('BOARD_NOT_READY'); s.close(); sys.exit(2)

bad = False
for i, ch in enumerate(chunks):
    if not send_wait('echo %s >> /tmp/xh; echo A$((%d))xD' % (ch, i), 'A%dxD' % i):
        print('chunk %d failed' % i); bad = True; break

if not bad:
    dec = ("python3 -c \"import binascii;open('%s','wb').write(binascii.unhexlify(open('/tmp/xh').read().replace(chr(10),'').replace(chr(13),'')))\" && rm -f /tmp/xh && md5sum %s; echo F$((7-7))INX" % (dst, dst))
    send_wait(dec, 'F0INX', 40)

time.sleep(0.3); s.reset_input_buffer()
s.write(b'stty echo; md5sum ' + dst.encode() + b'\n'); time.sleep(1.5)
resp = s.read(4096).decode('utf-8', 'replace')
s.close()
print('local ', md5_local, src)
for line in resp.splitlines():
    t = line.strip()
    if len(t) >= 32 and all(c in '0123456789abcdef' for c in t[:32]):
        print('remote', t[:32], dst)
        sys.exit(0 if t[:32] == md5_local else 1)
print('no md5 line:', resp[-150:])
sys.exit(1)
