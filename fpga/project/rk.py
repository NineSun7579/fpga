#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rk.py -- minimal RK3568 console helper over COM5 (1500000 8N1).
Reads command from argv[1], runs it on the board via base64 to avoid
quoting/echo issues, prints output.
"""
import serial, time, base64, sys

PORT, BAUD = 'COM5', 1500000

def run(snippet, tmo=90):
    last = ''
    for attempt in range(3):
        try:
            s = serial.Serial(PORT, BAUD, timeout=0.2)
        except Exception as e:
            print('[open err]', e); time.sleep(2); continue
        try:
            s.write(b'\x03'); time.sleep(0.6)
            s.write(b'\x15\r\nconsole\r\n'); time.sleep(0.8)
            s.reset_input_buffer()
            b64 = base64.b64encode(snippet.encode()).decode()
            s.write(('echo %s | base64 -d | bash; echo __E__' % b64).encode() + b'\n')
            t0 = time.time(); buf = b''
            while time.time() - t0 < tmo:
                c = s.read(16384)
                if c:
                    buf += c
                    if b'__E__' in buf:
                        break
        finally:
            s.close()
        last = buf.decode('utf-8', 'replace')
        if '__E__' in last:
            return last
    return last or '[no response]'

if __name__ == '__main__':
    cmd = sys.argv[1]
    tmo = int(sys.argv[2]) if len(sys.argv) > 2 else 90
    out = run(cmd, tmo)
    # strip echoed command and markers
    print(out)
