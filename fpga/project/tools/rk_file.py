# -*- coding: utf-8 -*-
"""rk_file.py -- run board commands read from a local file (separated by a
line containing only `===`), avoiding Windows shell quoting entirely.

Usage: python tools/rk_file.py <cmdfile> [port]
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from rk_console import Console

path = sys.argv[1]
port = sys.argv[2] if len(sys.argv) > 2 else "COM5"
raw = open(path, encoding="utf-8").read()
cmds = [c.strip() for c in re.split(r"^===\s*$", raw, flags=re.M) if c.strip()]

c = Console(port)
try:
    for cmd in cmds:
        print("$ " + cmd.replace("\n", " ")[:160])
        print(c.sh(cmd, timeout=120))
        print("-" * 60, flush=True)
finally:
    c.close()
print("DONE")
