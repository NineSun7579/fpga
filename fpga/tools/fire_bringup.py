#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fire_bringup.py -- PC-side one-shot: burn firfix (link-down first), push the
board bring-up kit, launch it detached, then pull artifacts. Built for the
RK3568's ~15-min post-boot stability window: minimal, ordered serial traffic.
"""
import subprocess
import sys
import time

ROOT = r'C:\Users\NineSun\Desktop\ov56401\project'


def sh(cmd, timeout=180):
    print('$ ' + cmd, flush=True)
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, timeout=timeout, shell=True)
        out = (r.stdout + r.stderr).decode('utf-8', 'replace')
    except subprocess.TimeoutExpired as e:
        out = '(TIMEOUT after %ds) %s' % (timeout, (e.stdout or b'')[-500:].decode('utf-8', 'replace'))
    print(out[-800:], flush=True)
    return out


def retries(cmd, timeout, marker, n=3, pause=6):
    for i in range(n):
        out = sh(cmd, timeout)
        if marker in out:
            return out
        print(f'  retry {i+1}/{n} ({marker} missing)', flush=True)
        time.sleep(pause)
    return ''


def main():
    # 1. link down (in case driver loaded), burn, link up
    sh('python tools\\_sh5.py "@tools/_trec.sh" 90', 150)
    out = sh('python tools\\burn_now.py flash_firfix.tcl', 300)
    if 'BURN OK' not in out:
        print('BURN FAILED'); return 1
    out = sh('python tools\\_sh5.py "echo 1 > /sys/bus/pci/rescan; sleep 3; '
             'rmmod pango_pci_driver 2>/dev/null; sleep 1; '
             'insmod /root/ov5640/pango_pci_driver.ko && echo INSMOD_OK" 120', 180)
    if 'INSMOD_OK' not in out:
        print('INSMOD FAILED'); return 1

    # 2. push the kit (chunked transfers)
    retries('python serial_xfer.py tools\\board_dualcap.py /tmp/dualcap2.py', 180, 'VERIFY OK')
    retries('python serial_xfer.py _dbg_probe.py /tmp/dbg_probe2.py', 180, 'VERIFY OK')
    retries('python serial_xfer.py tools\\board_bringup.sh /tmp/bringup.sh', 180, 'VERIFY OK')

    # 3. launch detached
    out = retries('python rk.py "chmod +x /tmp/bringup.sh; '
                  'setsid nohup bash /tmp/bringup.sh >/dev/null 2>&1 < /dev/null & '
                  'echo LAUNCHED" 60', 90, 'LAUNCHED')
    if 'LAUNCHED' not in out:
        print('LAUNCH FAILED'); return 1
    print('bring-up launched on board; artifacts at /root/ov5640/', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
