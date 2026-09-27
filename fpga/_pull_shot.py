#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_pull_shot.py -- screenshot the RK3568 X display and pull it back over serial.

Usage:
  python _pull_shot.py [local_out.png] [max_width]
"""
import base64
import re
import sys

import rk


def main():
    out_png = sys.argv[1] if len(sys.argv) > 1 else "rk_screen.png"
    width = sys.argv[2] if len(sys.argv) > 2 else "900"
    cmd = ("DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 "
           "/root/ov5640/qshot/qshot /tmp/rk_shot.png %s "
           ">/tmp/qshot.log 2>&1; stat -c %%s /tmp/rk_shot.png; "
           "echo B64S; base64 -w0 /tmp/rk_shot.png; echo; echo B64E") % width
    txt = rk.run(cmd, 120)
    m = re.search(r"B64S(.*?)B64E", txt, re.S)
    if not m:
        print("no base64 payload; raw tail:")
        print(txt[-800:])
        return 1
    payload = "".join(m.group(1).split())
    data = base64.b64decode(payload)
    with open(out_png, "wb") as f:
        f.write(data)
    print("wrote %s (%d bytes)" % (out_png, len(data)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
