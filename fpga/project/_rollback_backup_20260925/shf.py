#!/usr/bin/env python3
"""shf.py : run the shell script in a LOCAL file on the board via serial."""
import serial, sys, time, base64

PORT, BAUD = 'COM5', 1500000
path = sys.argv[1]
snippet = open(path, 'r', encoding='utf-8').read()
b64 = base64.b64encode(snippet.encode()).decode()
s = serial.Serial(PORT, BAUD, timeout=0.2)
s.write(b'\x03'); time.sleep(0.4); s.reset_input_buffer()
cmd = "echo " + b64 + " | base64 -d | bash; echo __EOC__"
s.write(cmd.encode() + b'\n'); s.flush()
t0 = time.time(); buf = b''
while time.time() - t0 < 60:
    c = s.read(8192)
    if c:
        buf += c
        if b'__EOC__' in buf:
            break
time.sleep(0.3)
text = buf.decode('utf-8', 'replace')
lines = [l for l in text.splitlines() if 'base64 -d | bash' not in l and '__EOC__' not in l]
print('\n'.join(lines))
s.close()
