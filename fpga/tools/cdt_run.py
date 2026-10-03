# -*- coding: utf-8 -*-
"""cdt_run.py -- run an arbitrary Pango cdt .tcl and dump its log.

Usage: python tools/cdt_run.py <tcl_path> [--port 65431] [--secs 60]
"""
import os
import subprocess
import sys
import time

PDS = r"C:\pango\PDS_2022.2-SP6.4\bin"
TK = r"C:\Windows\System32\taskkill.exe"
PROJ = r"C:\Users\NineSun\Desktop\ov56401\project"


def main():
    args = sys.argv[1:]
    tcl = os.path.abspath(args[0])
    port = 65431
    secs = 60
    if "--port" in args:
        port = int(args[args.index("--port") + 1])
    if "--secs" in args:
        secs = int(args[args.index("--secs") + 1])

    subprocess.run([TK, "/F", "/IM", "cdt_cfg.exe"], capture_output=True)
    subprocess.run([TK, "/F", "/IM", "cdt_js.exe"], capture_output=True)
    time.sleep(2)
    log = os.path.join(PROJ, "cdt_cfg_run.log")
    open(log, "w").close()
    subprocess.Popen([PDS + r"\cdt_js.exe", "-port", str(port)],
                     stdout=open(os.path.join(PROJ, "cdt_js_run.log"), "w"),
                     stderr=subprocess.STDOUT)
    time.sleep(5)
    subprocess.Popen([PDS + r"\cdt_cfg.exe", "-ip", "127.0.0.1", "-port", str(port),
                      "-file", tcl],
                     stdout=open(log, "w"), stderr=subprocess.STDOUT)
    t0 = time.time()
    while time.time() - t0 < secs:
        time.sleep(2)
        txt = open(log, errors="replace").read()
        # cdt prints the first marker at start; completion shows as
        # "... successfully." after the last typed command.
        if "Executing : cfg_scan_chain successfully" in txt:
            break
        if "cfg_program -device_index 0 successfully" in txt:
            break
        if "ERROR" in txt or "error" in txt.lower().split("executing")[-1]:
            pass
    time.sleep(2)
    subprocess.run([TK, "/F", "/IM", "cdt_cfg.exe"], capture_output=True)
    subprocess.run([TK, "/F", "/IM", "cdt_js.exe"], capture_output=True)
    print(open(log, errors="replace").read())


if __name__ == "__main__":
    main()
