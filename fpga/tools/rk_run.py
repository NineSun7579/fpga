# -*- coding: utf-8 -*-
"""rk_run.py -- run board commands from a local file over the debug UART.

Uses the proven prompt-synchronised protocol (same idea as tools/serial_exec.py)
instead of the base64/EOC scheme, which lost output when the console was busy.

Command file: one command per line; blank lines and lines starting with '#'
are ignored.  Commands are joined verbatim (use ';' for several statements).

Usage: python tools/rk_run.py <cmdfile> [port] [timeout_seconds]
"""
import re
import sys
import time

import serial

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROMPT = b"root@linaro-alip:/#"
ANSI = re.compile(rb"\x1b\[[0-9;?]*[a-zA-Z]")
KERNEL_RE = re.compile(r"^\[\s*\d+\.\d+\]")
SPAM = "Timeout waiting for DMA engine idle"

port = sys.argv[2] if len(sys.argv) > 2 else "COM5"
timeout = int(sys.argv[3]) if len(sys.argv) > 3 else 90

cmds = []
for ln in open(sys.argv[1], encoding="utf-8").read().splitlines():
    ln = ln.strip()
    if ln and not ln.startswith("#"):
        cmds.append(ln)


def open_port():
    s = serial.Serial(port, 1500000, timeout=0.3)
    s.reset_input_buffer()
    s.write(b"\r")
    s.flush()
    buf = b""
    t0 = time.time()
    while time.time() - t0 < 10:
        d = s.read(4096)
        if d:
            buf += d
            if PROMPT in buf:
                break
    return s


def clean(buf):
    txt = ANSI.sub(b"", buf).decode("utf-8", "replace")
    lines = []
    for ln in txt.splitlines():
        ln = ln.rstrip()
        if KERNEL_RE.match(ln.strip()) and SPAM in ln:
            continue
        if ln.strip() == "":
            continue
        lines.append(ln)
    return "\n".join(lines)


def run(s, cmd, tmo):
    s.write((cmd + "\r").encode())
    s.flush()
    buf = b""
    t0 = time.time()
    while time.time() - t0 < tmo:
        d = s.read(4096)
        if d:
            buf += d
            if buf.rstrip().endswith(PROMPT) or PROMPT in buf.split(b"\r\n")[-1]:
                break
        else:
            if buf.rstrip().endswith(PROMPT):
                break
    return clean(buf)


s = open_port()
try:
    for cmd in cmds:
        print("$ " + cmd[:150], flush=True)
        out = run(s, cmd, timeout)
        # drop the echoed command line
        lines = [l for l in out.splitlines() if l.strip() != cmd.strip()]
        print("\n".join(lines) if lines else "(no output)")
        print("-" * 60, flush=True)
finally:
    s.close()
print("DONE")
