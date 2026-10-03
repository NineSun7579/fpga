#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""flash_repo_latest.py -- JTAG-burn the repo's latest bitstream (quad-cam frame recovery).

Standalone (no ov56401 dependency): paths are resolved relative to this repo.
"""
import os
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.abspath(__file__))
PDS = r"C:\pango\PDS_2022.2-SP6.4\bin"
TK = r"C:\Windows\System32\taskkill.exe"
PORT = 65425
TCL = os.path.join(REPO, "flash_repo_latest.tcl")
LOG = os.path.join(REPO, "flash_repo_latest.out.log")
JSLOG = os.path.join(REPO, "flash_repo_latest.js.log")


def kill(name):
    subprocess.run([TK, "/F", "/IM", name], capture_output=True)


def main():
    for n in ("cdt_cfg.exe", "cdt_js.exe"):
        kill(n)
    time.sleep(2)
    open(LOG, "w").close()
    open(JSLOG, "w").close()

    js = subprocess.Popen([PDS + r"\cdt_js.exe", "-port", str(PORT)],
                          stdout=open(JSLOG, "w"), stderr=subprocess.STDOUT)
    time.sleep(5)
    subprocess.Popen([PDS + r"\cdt_cfg.exe", "-ip", "127.0.0.1",
                      "-port", str(PORT), "-file", TCL],
                     stdout=open(LOG, "w"), stderr=subprocess.STDOUT)

    done = False
    t0 = time.time()
    while time.time() - t0 < 240:
        time.sleep(3)
        try:
            txt = open(LOG, "r", errors="replace").read()
        except OSError:
            continue
        if "The done bit is 1" in txt and "COMMAND[Program] execute successfully" in txt:
            done = True
            break

    kill("cdt_cfg.exe")
    kill("cdt_js.exe")
    if js.poll() is None:
        js.terminate()
    txt = open(LOG, "r", errors="replace").read()
    print(txt[-1200:])
    print("FLASH_RESULT:", "SUCCESS" if done else "FAILED")
    return 0 if done else 1


if __name__ == "__main__":
    sys.exit(main())
