#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""poll_and_fire.py -- wait for the RK3568 console (post power-cycle), then
immediately fire the one-shot bring-up sequence. Polls every 45s until the
console answers twice in a row, then runs tools/fire_bringup.py.
"""
import subprocess
import sys
import time

sys.path.insert(0, r'C:\Users\NineSun\Desktop\ov56401\project')
sys.path.insert(0, r'C:\Users\NineSun\Desktop\ov56401\project\tools')
from watch_and_bringup import console_alive, log  # noqa: E402

log('=== poll_and_fire start ===')
hits = 0
deadline = time.time() + 2.2 * 3600
while time.time() < deadline:
    try:
        ok = console_alive()
    except Exception as e:
        log('ping error:', e)
        ok = False
    if ok:
        hits += 1
        log('ping ok %d/2' % hits)
        if hits >= 2:
            log('CONSOLE UP -- firing bring-up')
            r = subprocess.run([sys.executable,
                                r'C:\Users\NineSun\Desktop\ov56401\project\tools\fire_bringup.py'],
                               capture_output=True, timeout=1200)
            out = (r.stdout + r.stderr).decode('utf-8', 'replace')
            log(out[-3000:])
            log('=== fire_bringup exit=%d ===' % r.returncode)
            sys.exit(r.returncode)
    else:
        hits = 0
    time.sleep(45)
log('deadline exceeded without console')
sys.exit(2)
