#!/usr/bin/env python3
import serial, sys, time, base64, re

PORT, BAUD = 'COM9', 1500000
remote, local = sys.argv[1], sys.argv[2]
s = serial.Serial(PORT, BAUD, timeout=0.2)
s.write(b'\x15\r\nconsole\r\n'); time.sleep(0.8)
s.write(b'\x15\r\nstty -echo\r\n'); time.sleep(0.4)
s.reset_input_buffer()
s.write(b'echo B64BEGIN; base64 -w0 ' + remote.encode() + b'; echo; echo B64END\n')
s.flush()
buf = b''
t0 = time.time()
while time.time() - t0 < 25:
    c = s.read(8192)
    if c:
        buf += c
        if b'B64END' in buf:
            break
text = buf.decode('utf-8', 'replace')
payload = text.split('B64BEGIN', 1)[1].split('B64END', 1)[0]
candidates = re.findall(r'[A-Za-z0-9+/=]{40,}', payload)
b64 = max(candidates, key=len)
data = base64.b64decode(b64)
open(local, 'wb').write(data)
print('pulled', remote, '->', local, len(data), 'bytes')
s.close()
