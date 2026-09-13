#!/usr/bin/env python3
"""deploy_camview.py : 串口恢复后一键部署
   1) 传输带 ACK 修复的 camview 源码
   2) 板上重编
   3) 重启显示（单实例守护）
   4) 读窗口标题确认 fps
"""
import serial, time, base64, subprocess, sys, hashlib

PORT, BAUD = 'COM9', 1500000
SRC, DST = 'host/camview/main.cpp', '/root/ov5640/camview/main.cpp'

def sh(snippet, tmo=60, quiet=False):
    """在板上执行 shell 片段(sh2 风格), 返回输出"""
    for _ in range(3):
        try:
            s = serial.Serial(PORT, BAUD, timeout=0.3)
        except Exception:
            time.sleep(2); continue
        s.write(b'\x03'); time.sleep(0.6)
        s.write(b'\x15\r\nconsole\r\n'); time.sleep(0.8)
        s.reset_input_buffer()
        b64 = base64.b64encode(snippet.encode()).decode()
        s.write(('echo %s | base64 -d | bash; echo __E__' % b64).encode() + b'\n')
        t0 = time.time(); buf = b''
        while time.time() - t0 < tmo:
            c = s.read(16384)
            if c:
                buf += c
                if b'__E__' in buf: break
        s.close()
        if b'__E__' in buf:
            return buf.decode('utf-8', 'replace')
        time.sleep(1)
    return ''

print('== 0. 探测串口 ==')
out = sh('echo BOARD_OK', 20)
if 'BOARD_OK' not in out:
    print('  板子无响应 —— 请先拔插 USB 串口线(或复位板子)后重跑本脚本')
    sys.exit(2)
print('  板子在线')

print('== 1. 传输 camview 源码 ==')
data = open(SRC, 'rb').read()
md5 = hashlib.md5(data).hexdigest()
hx = data.hex().upper()
CH = 2000
chunks = [hx[i:i+CH] for i in range(0, len(hx), CH)]
sh('rm -f /tmp/xh', 10)
for i, ch in enumerate(chunks):
    r = sh('echo %s >> /tmp/xh; echo A$((%d))xD' % (ch, i), 25)
    if ('A%dxD' % i) not in r:
        print('  分片 %d 失败' % i); sys.exit(1)
print('  %d 分片传输完毕' % len(chunks))
out = sh("python3 -c \"import binascii;open('%s','wb').write(binascii.unhexlify(open('/tmp/xh').read().replace(chr(10),'').replace(chr(13),'')))\" && rm -f /tmp/xh && md5sum %s" % (DST, DST), 40)
ok = md5 in out
print('  md5 %s (%s)' % ('一致' if ok else '不一致!', md5))
if not ok:
    print(out[-300:]); sys.exit(1)

print('== 2. 板上重编 ==')
out = sh('pkill -f run_camview.sh 2>/dev/null; pkill -f camview 2>/dev/null; sleep 1; '
         'cd /root/ov5640/camview && rm -f camview Makefile *.o moc_* .qmake.stash && '
         '/usr/lib/qt5/bin/qmake && make -j4 > /tmp/mk.log 2>&1; echo RC=$?; '
         'grep -aiE "error" /tmp/mk.log | head -5; ls -la camview 2>/dev/null', 240)
print(' ', out.strip().splitlines()[-1] if out.strip() else '(无输出)')
if 'camview' not in out or 'RC=0' not in out:
    print('  编译可能失败, 日志尾部:'); print(sh('tail -12 /tmp/mk.log', 20))
    sys.exit(1)

print('== 3. 重启显示 ==')
sh('rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh > /dev/null 2>&1 < /dev/null & sleep 12', 60)
out = sh("ps aux|grep -a './camview'|grep -v grep|wc -l", 20)
print('  camview 进程数:', ''.join(c for c in out if c.isdigit())[:2] or '?')

print('== 4. 读窗口标题 ==')
out = sh("DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 xprop -root _NET_CLIENT_LIST > /tmp/wl 2>/dev/null; "
         "for id in $(grep -oE '0x[0-9a-f]+' /tmp/wl); do "
         "DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 xprop -id $id _NET_WM_NAME 2>/dev/null; done | grep -a camview", 40)
line = [l for l in out.splitlines() if 'camview' in l]
print(' ', line[0].strip() if line else '(未取到标题)')
print('部署完成: HDMI 应显示 RAW 相机画面(按 E 切处理缓冲, H 看帮助)')
