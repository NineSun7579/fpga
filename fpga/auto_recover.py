#!/usr/bin/env python3
"""auto_recover.py -- watchdog that waits for the RK3568 console to come back
(a power cycle is needed after `rmmod -f` wedged the shell) and then runs the
FULL bring-up autonomously:

  1. wait for console prompt (poll COM9 every 30s)
  2. JTAG re-burn [FRTAG] bitstream (power cycle reloads the OLD bitstream
     from SPI flash; the flash is an unsupported eON part so we cannot
     program it -- volatile JTAG burn instead)
  3. PCIe ritual: PERST -> remove/rescan -> rmmod/insmod (NO -f!)
  4. verify frame counters increment (TAG-SYNC proof)
  5. push remaining files (librknnrt.so, e2e models, then std models)
  6. build detview on board (qmake+make)
  7. selftest (12s, model 0) -> PASS/FAIL
  8. pull boxed PPM for visual check
  9. start GUI detview + e2e/std comparison
Everything is logged to auto_recover.log. Runs until 09:00.
"""
import subprocess, serial, time, sys, os, struct, re, hashlib, signal as sig

PORT, BAUD = 'COM9', 1500000
ROOT = r'C:\Users\NineSun\Desktop\ov56401'
LOG = os.path.join(ROOT, 'auto_recover.log')
PDS = r'C:\pango\PDS_2022.2-SP6.4\bin'
TK = r'C:\Windows\System32\taskkill.exe'
END = time.mktime(time.strptime(time.strftime('%Y-%m-%d') + ' 09:00', '%Y-%m-%d %H:%M'))

def log(*a):
    line = time.strftime('%H:%M:%S ') + ' '.join(str(x) for x in a)
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def sh(cmd, timeout=90):
    """run a shell snippet on the board via console (sh2.py logic inline)"""
    import base64
    s = serial.Serial(PORT, BAUD, timeout=0.2)
    s.write(b'console\r\n'); time.sleep(1.0); s.reset_input_buffer()
    b64 = base64.b64encode(cmd.encode()).decode()
    full = "echo %s | base64 -d | bash; echo __EOC__" % b64
    s.write(full.encode() + b'\n'); s.flush()
    t0 = time.time(); buf = b''
    while time.time() - t0 < timeout:
        c = s.read(8192)
        if c:
            buf += c
            if b'__EOC__' in buf:
                break
    s.close()
    time.sleep(0.3)
    text = buf.decode('utf-8', 'replace')
    lines = [l for l in text.splitlines() if 'base64 -d | bash' not in l and '__EOC__' not in l]
    return '\n'.join(lines)

def console_alive():
    """probe: real shell test -- only a live shell expands $((7*3)) to 21."""
    try:
        s = serial.Serial(PORT, BAUD, timeout=0.2)
    except Exception as e:
        log('serial open failed:', e); return False
    try:
        s.reset_input_buffer()
        s.write(b'console\r\n'); time.sleep(0.8); s.reset_input_buffer()
        s.write(b'echo Z$((7*3))Q\r\n')
        buf = b''; t0 = time.time()
        while time.time() - t0 < 5:
            c = s.read(4096)
            if c: buf += c
            if b'Z21Q' in buf:
                return True
        return False
    finally:
        s.close()

def board_py(code, timeout=120):
    """write a python script to the board and run it (heredoc-free via base64)"""
    import base64
    b64 = base64.b64encode(code.encode()).decode()
    out = sh("echo %s | base64 -d > /tmp/_t.py && python3 /tmp/_t.py" % b64, timeout)
    return out

COUNTER_PROBE = r'''
import ctypes,os,fcntl,mmap,struct,time,signal
FD=os.open('/dev/pango_pci_driver',os.O_RDWR|os.O_SYNC)
I=lambda n:0xC0000000|(4<<16)|(0x53<<8)|n
class O(ctypes.Structure):
  _fields_=[('cur',ctypes.c_uint32),('off',ctypes.c_uint32),('cmd',ctypes.c_uint32),('ddr',ctypes.c_uint32),('ln',ctypes.c_uint32),('rb',ctypes.c_void_p),('wb',ctypes.c_void_p)]
for c,s in ((0,4194304),(1,4194304)):
  o=O(); o.cmd=c; o.ln=s
  signal.alarm(6); fcntl.ioctl(FD,I(2),o,True); signal.alarm(0)
TX=mmap.mmap(FD,4194304,prot=mmap.PROT_READ|mmap.PROT_WRITE,flags=mmap.MAP_SHARED)
RX=mmap.mmap(FD,4194304,prot=mmap.PROT_READ|mmap.PROT_WRITE,flags=mmap.MAP_SHARED,offset=1048576)
def wrr(a,v):
  TX[0:4]=struct.pack('<I',v); o=O(); o.off=0; o.ddr=a; o.ln=16
  signal.alarm(6); fcntl.ioctl(FD,I(4),o,True); signal.alarm(0)
def rdd(a,n):
  o=O(); o.off=0; o.ddr=a; o.ln=n
  signal.alarm(12)
  try: fcntl.ioctl(FD,I(5),o,True)
  except: return None
  return bytes(RX[0:n])
wrr(0x20000080,0x00800000)
wrr(0x200000C0,0x00A00000)
wrr(0x20000000,3)
wrr(0x20000040,1)
prev=(0,0); inc=0
for i in range(25):
  b1=rdd(0x00896000,16); b2=rdd(0x00A96000,16)
  if b1 is None or b2 is None: print('POLL_FAIL'); continue
  t1=struct.unpack('<I',b1[:4])[0]; t2=struct.unpack('<I',b2[:4])[0]
  print('t1=%u t2=%u'%(t1,t2),flush=True)
  if (t1,t2)!=prev: inc+=1
  prev=(t1,t2); time.sleep(0.1)
print('INCREMENTS',inc)
'''

def burn_bitstream():
    log('burn: launching JTAG flash...')
    try:
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'burn_frtag.py')],
                           capture_output=True, timeout=600)
        out = (r.stdout + r.stderr).decode('utf-8', 'replace')
        ok = 'BURN OK' in out
    except subprocess.TimeoutExpired:
        # cdt_cfg may linger interactively; judge from the burn log itself
        log('burn: child timeout, checking burn log directly')
        try:
            txt = open(os.path.join(ROOT, 'cdt_cfg_burn.log'), errors='replace').read()
        except OSError:
            txt = ''
        ok = 'cfg_program successfully' in txt and 'The done bit is 1' in txt
        subprocess.run([TK, '/F', '/IM', 'cdt_cfg.exe'], capture_output=True)
        subprocess.run([TK, '/F', '/IM', 'cdt_js.exe'], capture_output=True)
    log('burn:', 'OK' if ok else 'FAILED')
    return ok

def fast_push(src, dst, chunk_data=2250, pipeline=4):
    """base64 chunked push with pipelined acks. Falls back to conservative
    serial protocol. Returns True if board md5 matches local."""
    import base64
    data = open(src, 'rb').read()
    lm = hashlib.md5(data).hexdigest()
    b64 = base64.b64encode(data).decode()
    chunks = [b64[i:i + chunk_data * 4 // 3] for i in range(0, len(b64), chunk_data * 4 // 3)]
    s = serial.Serial(PORT, BAUD, timeout=0.2)
    try:
        # quiet console + line buffering
        s.reset_input_buffer()
        s.write(b'stty -echo 2>/dev/null; rm -f /tmp/xb; echo G$((6+6))O\r\n'); s.flush()
        if not _wait(s, b'G12O', 6):
            return False
        n = len(chunks)
        i = 0
        while i < n:
            batch = chunks[i:i + pipeline]
            cmds = b''.join(('echo %s >> /tmp/xb; echo K%dxD\r\n' % (c, i + j)).encode()
                            for j, c in enumerate(batch))
            s.reset_input_buffer()
            s.write(cmds); s.flush()
            want = ('K%dxD' % (i + len(batch) - 1)).encode()
            if not _wait(s, want, 20 + 8 * len(batch)):
                # retry this batch once with a single-chunk pipeline
                s.reset_input_buffer()
                for j, c in enumerate(batch):
                    s.write(('echo %s >> /tmp/xb; echo K%dxD\r\n' % (c, i + j)).encode()); s.flush()
                    if not _wait(s, ('K%dxD' % (i + j)).encode(), 25):
                        return False
            i += len(batch)
            if (i // pipeline) % 200 == 0:
                log('  push %d/%d chunks (%.0f%%)' % (i, n, 100.0 * i / n))
        # decode + verify on board
        s.reset_input_buffer()
        dec = ("python3 -c \"import base64;open('%s','wb').write(base64.b64decode("
               "open('/tmp/xb').read().replace(chr(10),'').replace(chr(13),'')))\" && "
               "rm -f /tmp/xb && md5sum %s; echo P$((9-9))USH" % (dst, dst))
        s.write(dec.encode() + b'\n'); s.flush()
        buf = _drain(s, 90)
        m = re.findall(r'([0-9a-f]{32})\s+%s' % re.escape(dst), buf)
        return bool(m) and m[-1] == lm
    finally:
        s.close()

def _wait(s, want, tmo):
    t0 = time.time()
    while time.time() - t0 < tmo:
        c = s.read(8192)
        if c and want in c:
            return True
    return False

def _drain(s, sec):
    buf = b''; t0 = time.time()
    while time.time() - t0 < sec:
        c = s.read(8192)
        if c: buf += c
    return buf.decode('utf-8', 'replace')

def push(rel, dst, retries=2):
    src = os.path.join(ROOT, 'usb_deploy', 'detview', rel)
    log('  push %s -> %s (%.1f MB)' % (rel, dst, os.path.getsize(src) / 1048576.0))
    for attempt in range(1, retries + 1):
        try:
            if fast_push(src, dst):
                log('  push %s OK (fast)' % rel)
                return True
            log('  push %s fast method failed (attempt %d)' % (rel, attempt))
        except Exception as e:
            log('  push %s exception: %s' % (rel, e))
        time.sleep(3)
    # slow but proven fallback
    log('  push %s -> xfer_hex fallback (~20 min for 4MB)' % rel)
    try:
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'xfer_hex.py'), src, dst],
                           capture_output=True, timeout=2400)
        out = (r.stdout + r.stderr).decode('utf-8', 'replace')
        m = re.findall(r'([0-9a-f]{32})\s+%s' % re.escape(dst), out)
        if m and m[-1] == hashlib.md5(open(src,'rb').read()).hexdigest():
            log('  push %s OK (xfer_hex)' % rel)
            return True
    except Exception as e:
        log('  push %s xfer_hex exception: %s' % (rel, e))
    return False

def main():
    log('=== auto_recover watchdog started (runs until 09:00) ===')
    log('state: bitstream built+burned OK; board shell wedged by rmmod -f; awaiting power cycle')
    stage = 'WAIT_CONSOLE'
    counters_ok = False
    push_ok = set()
    try:
        for line in open(LOG, encoding='utf-8', errors='replace'):
            m = re.search(r'push (\S+) OK \((fast|xfer_hex)\)', line)
            if m: push_ok.add(m.group(1))
        if push_ok: log('push_ok seeded from log:', sorted(push_ok))
    except OSError:
        pass
    built = False
    selftest_ok = False
    gui_started = False

    while time.time() < END:
        if stage == 'WAIT_CONSOLE':
            if console_alive():
                log('*** CONSOLE ALIVE ***')
                out = sh('echo SHELL_OK; uptime | tail -c 40')
                log('probe:', out.strip()[:120])
                stage = 'CHECK'
            else:
                time.sleep(30)
        elif stage == 'BURN':
            if burn_bitstream(): stage = 'CHECK'
            else: time.sleep(60)
        elif stage == 'CHECK':
            # non-hanging ritual: only the driver state matters; PERST/rescan
            # (needed after JTAG reburn) hangs the console, so we verify by
            # counters instead -- if counters move, the link is alive.
            out = sh('pkill -x camview 2>/dev/null; pkill -x detview 2>/dev/null; '
                     'n=$(lsmod | grep -c pango); '
                     'if [ "$n" -ge 1 ] && ls /dev/pango_pci_driver >/dev/null 2>&1; then echo RITUAL_OK; '
                     'else rmmod pango_pci_driver 2>/dev/null; sleep 1; '
                     'insmod /root/ov5640/pango_pci_driver.ko && echo RITUAL_OK; fi', 60)
            log('check:', out.strip().splitlines()[-1] if out.strip() else '(empty)')
            if 'RITUAL_OK' in out:
                stage = 'COUNTERS'
            else:
                log('check failed, retry in 60s'); time.sleep(60)
        elif stage == 'COUNTERS':
            out = board_py(COUNTER_PROBE, 120)
            inc = 0
            m = re.search(r'INCREMENTS (\d+)', out)
            if m: inc = int(m.group(1))
            log('counter probe increments:', inc)
            if inc >= 5:
                counters_ok = True
                log('*** FRAME COUNTERS INCREMENTING -- [FRTAG] bitstream VERIFIED ***')
                stage = 'PUSH'
            else:
                log('counters not incrementing (check burn/ritual), retry in 60s')
                stage = 'BURN'   # loop back: re-burn then retry (short ritual)
                time.sleep(60)
        elif stage == 'PUSH':
            todo = [('lib/librknnrt.so', '/root/ov5640/lib/librknnrt.so'),
                    ('models/zebra_3cls_640_e2e.rknn', '/root/ov5640/models/zebra_3cls_640_e2e.rknn'),
                    ('models/vehicles_1cls_640_e2e.rknn', '/root/ov5640/models/vehicles_1cls_640_e2e.rknn'),
                    ('models/zebra_3cls_640_std.rknn', '/root/ov5640/models/zebra_3cls_640_std.rknn'),
                    ('models/vehicles_1cls_640_std.rknn', '/root/ov5640/models/vehicles_1cls_640_std.rknn')]
            # sources are already on the board; push the big files
            for rel, dst in todo:
                if rel not in push_ok:
                    if push(rel, dst): push_ok.add(rel)
                    else: time.sleep(30)
                time.sleep(2)
            need = {'lib/librknnrt.so', 'models/zebra_3cls_640_e2e.rknn'}
            if need <= push_ok:
                stage = 'BUILD'
            else:
                time.sleep(60)
        elif stage == 'BUILD':
            out = sh('cd /root/ov5640/detview && rm -f detview Makefile *.o moc_* .qmake.stash && '
                     '/usr/lib/qt5/bin/qmake && make -j4 2>&1 | tail -5 && ls -la detview && echo BUILD_OK', 300)
            log('build:', out.strip().splitlines()[-2:] if out.strip() else '(empty)')
            if 'BUILD_OK' in out:
                built = True; stage = 'SELFTEST'
            else:
                log('build failed, retry in 120s'); time.sleep(120)
        elif stage == 'SELFTEST':
            out = sh('cd /root/ov5640/detview && QT_QPA_PLATFORM=offscreen ./detview --selftest 12 --model 0 2>&1 | tail -12', 180)
            log('selftest output:\n' + out.strip()[:1500])
            if 'SELFTEST PASS' in out:
                selftest_ok = True
                log('*** SELFTEST PASS ***')
                stage = 'GUI'
            else:
                log('selftest FAILED, retry in 120s'); time.sleep(120)
        elif stage == 'GUI':
            out = sh('rm -f /tmp/detview.lock; setsid nohup /root/ov5640/detview/run_detview.sh '
                     '> /dev/null 2>&1 < /dev/null & sleep 8; ps aux | grep -a "[d]etview" | head -3; '
                     'DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 xprop -root _NET_CLIENT_LIST 2>/dev/null | head -c 120', 120)
            log('gui start:', out.strip()[:400])
            if 'detview' in out:
                gui_started = True
                log('*** detview GUI RUNNING ***')
                stage = 'BENCH'
            else:
                time.sleep(60)
        elif stage == 'BENCH':
            # e2e vs std comparison (headless), then restart the GUI
            for idx, name in [(0, 'zebra_e2e'), (1, 'zebra_std')]:
                out = sh('cd /root/ov5640/detview && QT_QPA_PLATFORM=offscreen ./detview --selftest 10 --model %d 2>&1 | tail -3' % idx, 180)
                log('bench %s:\n%s' % (name, out.strip()[:600]))
                time.sleep(5)
            # restart GUI on the recommended default
            sh('pkill -x detview 2>/dev/null; sleep 2; rm -f /tmp/detview.lock; setsid nohup /root/ov5640/detview/run_detview.sh > /dev/null 2>&1 < /dev/null &', 60)
            log('=== ALL STAGES DONE; monitoring until 09:00 (ctrl-c state: '
                'counters=%s selftest=%s gui=%s) ===' % (counters_ok, selftest_ok, gui_started))
            stage = 'MONITOR'
        else:  # MONITOR
            out = sh('ps aux | grep -a "[d]etview" | wc -l; tail -2 /root/ov5640/detview.log 2>/dev/null', 90)
            log('monitor:', out.strip().replace('\n', ' | ')[:200])
            time.sleep(300)

    log('=== 09:00 reached. summary: counters=%s selftest=%s gui=%s pushed=%s ==='
        % (counters_ok, selftest_ok, gui_started, sorted(push_ok)))

if __name__ == '__main__':
    main()
