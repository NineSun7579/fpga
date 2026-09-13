#!/usr/bin/env python3
import serial, sys, time, base64, re

PORT, BAUD = 'COM9', 1500000
remote, local = sys.argv[1], sys.argv[2]
s = serial.Serial(PORT, BAUD, timeout=0.2)
s.reset_input_buffer()
s.write(b'base64 -w0 ' + remote.encode() + b' ; echo __END__\n')
s.flush()
buf = b''
t0 = time.time()
while time.time() - t0 < 25:
    c = s.read(8192)
    if c:
        buf += c
        if b'__END__' in buf:
            break
text = buf.decode('utf-8', 'replace')
# remove echo line and command markers
lines = text.splitlines()
b64 = ''.join(l for l in lines if re.fullmatch(r'[A-Za-z0-9+/=]+', l.strip()))
data = base64.b64decode(b64)
open(local, 'wb').write(data)
print('pulled', remote, '->', local, len(data), 'bytes')
s.close()
