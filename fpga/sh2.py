#!/usr/bin/env python3
"""sh2.py : run a shell snippet on the board via serial. 先发 console 恢复 FIQ，不发 Ctrl-C。"""
import serial, sys, time, base64

PORT, BAUD = 'COM9', 1500000
snippet = sys.argv[1]
b64 = base64.b64encode(snippet.encode()).decode()
s = serial.Serial(PORT, BAUD, timeout=0.2)
s.write(b'console\r\n'); time.sleep(1.0); s.reset_input_buffer()
cmd = "echo %s | base64 -d | bash; echo __EOC__" % b64
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
