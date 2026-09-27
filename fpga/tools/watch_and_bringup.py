#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""watch_and_bringup.py -- poll COM5 for the RK3568 console; when it comes
back (after a power cycle), run the full FIR-fix bring-up automatically:

  1. wait for console
  2. JTAG burn  bitstream_2026-09-26_firfix/top.sbit
  3. rescan + insmod + start camview
  4. detview selftest (TAG-SYNC + fps)
  5. 6 screenshots at 3-min intervals (pulled locally)
  6. DDR dual capture cam1/cam2 + stripe metrics if possible

All output -> firfix_bringup.log. Exits 0 on success, 1 on failure.
"""
import subprocess, serial, sys, time, os

PORT, BAUD = 'COM5', 1500000
ROOT = r'C:\Users\NineSun\Desktop\ov56401\project'
LOG = open(os.path.join(ROOT, 'firfix_bringup.log'), 'a', buffering=1)

def log(*a):
    msg = ' '.join(str(x) for x in a)
    LOG.write('[%s] %s\n' % (time.strftime('%H:%M:%S'), msg))
    print(msg, flush=True)

def sh(cmd, timeout=120):
    log('$', cmd)
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, timeout=timeout,
                       shell=True)
    out = (r.stdout + r.stderr).decode('utf-8', 'replace')
    log(out[-1500:] if len(out) > 1500 else out)
    return out

def console_alive():
    try:
        s = serial.Serial(PORT, BAUD, timeout=0.2)
    except Exception as e:
        log('serial open fail:', e)
        return False
    try:
        s.write(b'\r\n'); s.flush()
        time.sleep(0.8)
        s.reset_input_buffer()
        s.write(b'\x03'); time.sleep(0.5)
        s.write(b'\x15\r\necho WATCHER_PING\r\n'); s.flush()
        t0 = time.time(); buf = b''
        while time.time() - t0 < 6:
            c = s.read(1024)
            if c:
                buf += c
                if b'WATCHER_PING' in buf:
                    return True
        return False
    finally:
        s.close()

def main():
    log('=== watcher start, polling COM5 every 30s ===')
    hits = 0
    while True:
        if console_alive():
            hits += 1
            log('console ping ok (%d/2)' % hits)
            if hits >= 2:
                log('CONSOLE ALIVE -- starting bring-up')
                break
        else:
            hits = 0
        time.sleep(30)

    time.sleep(5)
    # 1) burn the FIR-fixed bitstream (JTAG; no serial needed)
    out = sh('python tools\\burn_now.py flash_firfix.tcl', 300)
    if 'BURN OK' not in out:
        log('BURN FAILED -- aborting'); sys.exit(1)
    time.sleep(3)

    # 2) link up: rescan + insmod + restart viewer
    sh('python tools\\_sh5.py "echo 1 > /sys/bus/pci/rescan; sleep 3; '
       'rmmod pango_pci_driver 2>/dev/null; sleep 1; '
       'insmod /root/ov5640/pango_pci_driver.ko && echo INSMOD_OK; sleep 2; '
       'rm -f /tmp/camview.lock; '
       'setsid nohup /root/ov5640/run_camview.sh >/dev/null 2>&1 & sleep 12; '
       'ps aux | grep -a ./camview | grep -v grep | wc -l" 180', 240)

    # 3) detview selftest (TAG-SYNC + fps)
    sh('python tools\\_sh5.py "pkill -f run_camview.sh; pkill -x camview; sleep 2; '
       'cd /root/ov5640 && QT_QPA_PLATFORM=offscreen timeout 30 ./detview/detview '
       '--selftest 15 --model 0 2>&1 | tail -8" 120', 180)

    # 4) restart viewer for visual check
    sh('python tools\\_sh5.py "rm -f /tmp/camview.lock; '
       'setsid nohup /root/ov5640/run_camview.sh >/dev/null 2>&1 & sleep 12; '
       'ps aux | grep -a ./camview | grep -v grep | wc -l" 120', 180)

    # 5) screenshots at intervals
    for i in range(6):
        tag = 'firfix_s%d' % i
        sh('python rk.py "rm -f /tmp/qk.png /tmp/qk.jpg; '
           'DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 '
           '/root/ov5640/qshot/qshot /tmp/qk.png 900 >/dev/null 2>&1; '
           'ffmpeg -y -loglevel error -i /tmp/qk.png -q:v 3 /tmp/qk.jpg 2>/dev/null; '
           'ls -la /tmp/qk.jpg" 90', 120)
        out = sh('python tools\\_pull5.py /tmp/qk.jpg %s.jpg 120' % tag, 180)
        if 'MATCH' not in out:
            log('pull failed for', tag)
        if i < 5:
            time.sleep(180 - 30)

    # 6) DDR capture of cam1/cam2 for stripe metrics
    sh('python rk.py "pkill -f run_camview.sh; pkill -x camview; sleep 2" 45', 60)
    sh('python serial_xfer.py tools\\board_dualcap.py /tmp/dualcap.py', 180)
    sh('python rk.py "python3 /tmp/dualcap.py > /tmp/dualcap.out 2>&1; '
       'echo RC=$?; tail -12 /tmp/dualcap.out" 100', 150)
    sh('python tools\\_pull5.py /tmp/cam1_kf.ppm firfix_cam1.ppm 180', 240)
    sh('python tools\\_pull5.py /tmp/cam2_raw.ppm firfix_cam2.ppm 180', 240)
    for tag in ('firfix_cam1.ppm', 'firfix_cam2.ppm'):
        p = os.path.join(ROOT, tag)
        if os.path.exists(p):
            sh('python tools\\stripe_check.py %s' % tag, 60)

    log('=== bring-up sequence complete ===')

if __name__ == '__main__':
    main()
