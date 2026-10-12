#!/usr/bin/env python3
"""final_sweep.py : 解码现成 /tmp/xh -> 校验 -> 补传缺失分片 -> 合并/解压/装Qt开发包"""
import serial, sys, time, hashlib, subprocess, base64

PORT, BAUD = 'COM9', 1500000
PARTS = ['p%02d' % i for i in range(14)]
LOCAL_DIR, REMOTE_DIR = 'qt_parts', '/root/qt_parts'
TAR = '/root/qt_debs.tar.gz'

def md5f(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()

def sh(snippet, tmo=90):
    """sh2 风格: console恢复 + base64 命令, 返回输出文本"""
    for _ in range(4):
        try:
            s = serial.Serial(PORT, BAUD, timeout=0.2)
        except Exception:
            time.sleep(2); continue
        s.write(b'\x15\r\nconsole\r\n'); time.sleep(0.8)
        s.reset_input_buffer()
        b64 = base64.b64encode(snippet.encode()).decode()
        s.write(('echo %s | base64 -d | bash; echo __E__' % b64).encode() + b'\n')
        t0 = time.time(); buf = b''
        while time.time() - t0 < tmo:
            c = s.read(8192)
            if c:
                buf += c
                if b'__E__' in buf: break
        s.close()
        if b'__E__' in buf:
            return buf.decode('utf-8', 'replace')
        time.sleep(1)
    return ''

def remote_md5(part):
    out = sh('md5sum %s/%s 2>/dev/null' % (REMOTE_DIR, part), 15)
    for line in out.splitlines():
        t = line.strip()
        if len(t) >= 32 and all(c in '0123456789abcdef' for c in t[:32]):
            return t[:32]
    return None

# 1) 解码已躺在 /tmp/xh 的 p04
out = sh("python3 -c \"import binascii;open('%s/p04','wb').write(binascii.unhexlify(open('/tmp/xh').read().replace(chr(10),'').replace(chr(13),'')))\" && rm -f /tmp/xh; md5sum %s/p04" % (REMOTE_DIR, REMOTE_DIR), 60)
print('decode p04:', [l for l in out.splitlines() if 'p04' in l], flush=True)

# 2) 逐片补齐
for part in PARTS:
    local = md5f('%s/%s' % (LOCAL_DIR, part))
    rm = remote_md5(part)
    if rm == local:
        print(part, 'already OK', flush=True)
        continue
    ok = False
    for attempt in range(4):
        print(part, 'attempt', attempt + 1, flush=True)
        r = subprocess.run([sys.executable, 'xfer_hex.py', '%s/%s' % (LOCAL_DIR, part),
                            '%s/%s' % (REMOTE_DIR, part)],
                           capture_output=True, text=True, timeout=600)
        if 'MATCH' in (r.stdout + r.stderr):
            ok = True; break
        time.sleep(2)
    if not ok:
        print(part, 'FAILED ALL', flush=True)
        sys.exit(1)
print('ALL_PARTS_OK', flush=True)

# 3) 合并 + 总校验 + 解压 + 安装
want = md5f('qt_debs.tar.gz')
out = sh('cat %s/p* > %s && md5sum %s' % (REMOTE_DIR, TAR, TAR), 120)
print('assemble:', [l for l in out.splitlines() if 'qt_debs' in l], flush=True)
if want not in out:
    print('TAR MD5 MISMATCH, want', want, flush=True)
    sys.exit(1)
cmds = (
    'rm -rf /root/qtdebs && mkdir -p /root/qtdebs && tar xzf %s -C /root/qtdebs && ls /root/qtdebs | wc -l' % TAR,
    'cd /root/qtdebs && dpkg -i --force-depends *.deb 2>&1 | tail -6',
    'qmake -v 2>&1 | head -2; ls /usr/lib/qt5/bin/moc 2>/dev/null && echo QT_DEV_READY',
)
for c in cmds:
    out = sh(c, 300)
    print('>>>', c[:60], '\n', out[-600:], flush=True)
print('FINAL_DONE', flush=True)
