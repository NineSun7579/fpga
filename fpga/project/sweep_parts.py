#!/usr/bin/env python3
"""sweep_parts.py : 清点并补齐 14 个分片, 然后合并/解压/安装 Qt 开发包。"""
import subprocess, sys, time, hashlib, os

sys.path.insert(0, '.')
PORT = 'COM9'
PARTS = ['p%02d' % i for i in range(14)]
LOCAL_DIR = 'qt_parts'
REMOTE_DIR = '/root/qt_parts'

def md5f(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()

def remote_md5(part, retries=4):
    """读远端单个分片的 md5（sh2 风格: console 恢复 + base64 命令）"""
    import serial, base64
    snippet = 'md5sum %s/%s' % (REMOTE_DIR, part)
    for _ in range(retries):
        try:
            s = serial.Serial(PORT, 1500000, timeout=0.2)
        except Exception:
            time.sleep(2); continue
        s.write(b'console\r\n'); time.sleep(0.8); s.reset_input_buffer()
        b64 = base64.b64encode(snippet.encode()).decode()
        s.write(('echo %s | base64 -d | bash; echo __E__' % b64).encode() + b'\n')
        t0 = time.time(); buf = b''
        while time.time() - t0 < 8:
            c = s.read(4096)
            if c:
                buf += c
                if b'__E__' in buf: break
        s.close()
        for line in buf.decode('utf-8', 'replace').splitlines():
            t = line.strip()
            if len(t) >= 32 and all(ch in '0123456789abcdef' for ch in t[:32]):
                return t[:32]
        time.sleep(1)
    return None

def xfer(part):
    r = subprocess.run([sys.executable, 'xfer_hex.py',
                        os.path.join(LOCAL_DIR, part),
                        '%s/%s' % (REMOTE_DIR, part)],
                       capture_output=True, text=True, timeout=400)
    return 'MATCH' in (r.stdout + r.stderr)

# pass 1..3
for part in PARTS:
    local = md5f(os.path.join(LOCAL_DIR, part))
    rm = remote_md5(part)
    if rm == local:
        print('%s already OK' % part, flush=True)
        continue
    done = False
    for attempt in range(3):
        print('%s transfer attempt %d' % (part, attempt + 1), flush=True)
        if xfer(part):
            done = True; break
        time.sleep(2)
    if not done:
        print('%s FAILED ALL ATTEMPTS' % part, flush=True)
        sys.exit(1)
print('ALL_PARTS_OK', flush=True)
