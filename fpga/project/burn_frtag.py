#!/usr/bin/env python3
"""burn_frtag.py v2 -- JTAG flash via cdt_js+cdt_cfg with log polling.
cdt_cfg executes the tcl then stays interactive, so we poll the log file
instead of waiting for process exit."""
import subprocess, time, sys, os

PDS = r'C:\pango\PDS_2022.2-SP6.4\bin'
TK = r'C:\Windows\System32\taskkill.exe'
ROOT = r'C:\Users\NineSun\Desktop\ov56401'
TCL = os.path.join(ROOT, 'flash_jtag.tcl')

def flash():
    subprocess.run([TK, '/F', '/IM', 'cdt_cfg.exe'], capture_output=True)
    subprocess.run([TK, '/F', '/IM', 'cdt_js.exe'], capture_output=True)
    time.sleep(2)
    log = os.path.join(ROOT, 'cdt_cfg_burn.log')
    open(log, 'w').close()
    subprocess.Popen([PDS + r'\cdt_js.exe', '-port', '65425'],
                     stdout=open(os.path.join(ROOT, 'cdt_js_burn.log'), 'w'),
                     stderr=subprocess.STDOUT)
    time.sleep(5)
    subprocess.Popen([PDS + r'\cdt_cfg.exe', '-ip', '127.0.0.1', '-port', '65425',
                      '-file', TCL],
                     stdout=open(log, 'w'), stderr=subprocess.STDOUT)
    # poll for completion markers
    t0 = time.time()
    saw_scan = saw_assign = saw_program = done = False
    while time.time() - t0 < 240:
        time.sleep(3)
        try:
            txt = open(log, 'r', errors='replace').read()
        except OSError:
            continue
        saw_scan = saw_scan or 'cfg_scan_chain successfully' in txt
        saw_assign = saw_assign or ('cfg_assign_file' in txt and 'successfully' in txt.split('cfg_assign_file')[-1].split('cfg_program')[0])
        saw_program = saw_program or 'Executing : cfg_program' in txt
        # real success line: "Executing : cfg_program -device_index 0 successfully."
        if 'cfg_program -device_index 0 successfully' in txt:
            done = True
            break
        if 'Error' in txt and ('cfg_program' in txt) and not saw_program:
            print(txt[-600:])
            break
    subprocess.run([TK, '/F', '/IM', 'cdt_cfg.exe'], capture_output=True)
    subprocess.run([TK, '/F', '/IM', 'cdt_js.exe'], capture_output=True)
    if done:
        print('\n'.join(open(log, errors='replace').read().splitlines()[-8:]))
    return done

for attempt in (1, 2, 3):
    print(f'--- burn attempt {attempt} ---', flush=True)
    if flash():
        print('BURN OK', flush=True)
        sys.exit(0)
    time.sleep(4)
print('BURN FAILED', flush=True)
sys.exit(1)
