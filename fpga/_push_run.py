#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_push_run.py -- push a local file to the RK3568 (/tmp) and run it, over serial.

Usage:
  python _push_run.py <local_file> [remote_path] [interp]

Example:
  python _push_run.py pipe_status.py /tmp/pipe_status.py python3

Reuses rk.py's serial transport so quoting is handled by base64 end-to-end.
"""
import base64
import os
import sys

import rk


def main():
    local = sys.argv[1]
    remote = sys.argv[2] if len(sys.argv) > 2 else "/tmp/" + os.path.basename(local)
    interp = sys.argv[3] if len(sys.argv) > 3 else "python3"
    tmo = int(sys.argv[4]) if len(sys.argv) > 4 else 90

    data = open(local, "rb").read()
    b64 = base64.b64encode(data).decode()
    snippet = "echo %s | base64 -d > %s; sync; %s %s; echo __RC__$?" % (
        b64, remote, interp, remote)
    out = rk.run(snippet, tmo)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
