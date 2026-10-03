# -*- coding: utf-8 -*-
"""rp.py -- raw serial probe: dump exactly what the console emits."""
import sys
import time

import serial

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PORT = "COM5"
s = serial.Serial(PORT, 1500000, timeout=0.3)


def drain(sec, tag):
    t0 = time.time()
    buf = b""
    while time.time() - t0 < sec:
        c = s.read(8192)
        if c:
            buf += c
    print("### %s (%d bytes) ###" % (tag, len(buf)))
    print(buf.decode("utf-8", "replace")[-1500:])
    print("### end ###")


drain(2, "idle")
for tag, data in (("CR", b"\r\n"), ("Ctrl-C", b"\x03"), ("console+CR", b"console\r\n"),
                  ("Z probe", b"echo Z$((7*3))Q\r\n")):
    s.reset_input_buffer()
    s.write(data)
    s.flush()
    drain(3, tag)
s.close()
