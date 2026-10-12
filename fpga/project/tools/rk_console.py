# -*- coding: utf-8 -*-
"""rk_console.py -- robust serial console helper for the RK3568 debug port.

The kernel floods the console with `PCI_DMA_WRITE Error: Timeout ...` while the
FPGA/DMA state is stale, so every command is sent base64-encoded (avoids the
literal `fiq` trap) and terminated with an explicit __EOC__ marker.
"""
import base64
import re
import sys
import time

import serial

KERNEL_RE = re.compile(r"^\[\s*\d+\.\d+\]")
PROMPT_RE = re.compile(r"root@linaro-alip:[^#]*#\s*$")

DEFAULT_PORT = "COM5"
DEFAULT_BAUD = 1500000


class Console:
    def __init__(self, port=DEFAULT_PORT, baud=DEFAULT_BAUD, verbose=False):
        self.port = port
        self.verbose = verbose
        self.s = serial.Serial(port, baud, timeout=0.2)
        self._sync()

    def _sync(self):
        self.s.reset_input_buffer()
        self.s.write(b"\r\nconsole\r\n")
        time.sleep(1.0)
        self.s.reset_input_buffer()

    def sh(self, cmd, timeout=60, quiet=True):
        b64 = base64.b64encode(cmd.encode()).decode()
        full = "echo %s | base64 -d | bash; echo __EOC__" % b64
        self.s.reset_input_buffer()
        self.s.write(full.encode() + b"\n")
        self.s.flush()
        t0 = time.time()
        buf = b""
        while time.time() - t0 < timeout:
            chunk = self.s.read(8192)
            if chunk:
                buf += chunk
                if b"__EOC__" in buf:
                    break
        text = buf.decode("utf-8", "replace")
        lines = []
        for ln in text.splitlines():
            if "base64 -d | bash" in ln or "__EOC__" in ln:
                continue
            # the board echoes our b64 blob first; drop it
            if ln.strip().startswith("echo ") and len(ln.strip()) > 60 and " " not in ln.strip()[5:40]:
                continue
            if quiet and KERNEL_RE.match(ln.strip()):
                continue
            lines.append(ln.rstrip())
        while lines and not lines[-1].strip():
            lines.pop()
        out = "\n".join(lines)
        if self.verbose:
            print("$ " + cmd)
            print(out)
            print("-" * 60)
        return out

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:]
    port = DEFAULT_PORT
    if args and re.match(r"^COM\d+$", args[0], re.I):
        port = args[0]
        args = args[1:]
    cmds = [a for a in args if not a.startswith("-")]
    if not cmds:
        cmds = ["uname -a", "uptime"]
    c = Console(port)
    try:
        for cmd in cmds:
            print("$ " + cmd)
            print(c.sh(cmd))
            print("-" * 60)
    finally:
        c.close()


if __name__ == "__main__":
    main()
