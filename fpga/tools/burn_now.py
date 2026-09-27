#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""burn_now.py -- JTAG-burn the FPGA from the project dir (fixed paths).

Fix vs burn_frtag.py: that script used ROOT=.../ov56401 while the tcl/logs
now live in .../ov56401/project.

Usage:
  python tools/burn_now.py [tcl_path] [--port 65425] [--tries 3]
"""
import subprocess
import sys
import time
import os

PDS = r"C:\pango\PDS_2022.2-SP6.4\bin"
TK = r"C:\Windows\System32\taskkill.exe"
PROJ = r"C:\Users\NineSun\Desktop\ov56401\project"


def flash(tcl, port, log):
    subprocess.run([TK, "/F", "/IM", "cdt_cfg.exe"], capture_output=True)
    subprocess.run([TK, "/F", "/IM", "cdt_js.exe"], capture_output=True)
    time.sleep(2)
    open(log, "w").close()
    subprocess.Popen([PDS + r"\cdt_js.exe", "-port", str(port)],
                     stdout=open(os.path.join(PROJ, "cdt_js_burn.log"), "w"),
                     stderr=subprocess.STDOUT)
    time.sleep(5)
    subprocess.Popen([PDS + r"\cdt_cfg.exe", "-ip", "127.0.0.1",
                      "-port", str(port), "-file", tcl],
                     stdout=open(log, "w"), stderr=subprocess.STDOUT)
    t0 = time.time()
    done = False
    while time.time() - t0 < 240:
        time.sleep(3)
        try:
            txt = open(log, "r", errors="replace").read()
        except OSError:
            continue
        if "cfg_program -device_index 0 successfully" in txt:
            done = True
            break
    subprocess.run([TK, "/F", "/IM", "cdt_cfg.exe"], capture_output=True)
    subprocess.run([TK, "/F", "/IM", "cdt_js.exe"], capture_output=True)
    if done:
        print("\n".join(open(log, errors="replace").read().splitlines()[-8:]))
    return done


def main():
    args = sys.argv[1:]
    tcl = args[0] if args and not args[0].startswith("--") else os.path.join(PROJ, "flash_jtag.tcl")
    port = 65425
    tries = 3
    if "--port" in args:
        port = int(args[args.index("--port") + 1])
    if "--tries" in args:
        tries = int(args[args.index("--tries") + 1])
    log = os.path.join(PROJ, "cdt_cfg_burn.log")
    print("tcl =", tcl)
    for a in range(1, tries + 1):
        print("--- burn attempt %d (port %d) ---" % (a, port), flush=True)
        if flash(tcl, port, log):
            print("BURN OK", flush=True)
            sys.exit(0)
        time.sleep(4)
    print("BURN FAILED", flush=True)
    sys.exit(1)


if __name__ == "__main__":
    main()
