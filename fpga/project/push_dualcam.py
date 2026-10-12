#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""push_dualcam.py : FMC 双目 camview 上板工具（COM9 @1500000）

用法:
    python push_dualcam.py probe     # 只探测板子/驱动/显示状态，不推送
    python push_dualcam.py push      # 推送 camview 源码 -> 板上重编 -> 复位 PCIe -> 重启显示
    python push_dualcam.py push --no-rebuild   # 只传源码，不重编

说明:
    - 源码: host/camview/main.cpp  ->  /root/ov5640/camview/main.cpp
    - 采用大写 HEX 分片 + md5 校验（避免串口出现字面量 'fiq' 触发 FIQ 调试器）
    - push 前请确认已烧写 bitstream_2026-09-16_dualcam/top.sbit（JTAG 需人工执行）
"""
import serial, sys, time, hashlib, os

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

PORT, BAUD = 'COM5', 1500000   # [DEBUGPORT] board console moved to the CH340 debug port
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'host', 'camview', 'main.cpp')
DST = '/root/ov5640/camview/main.cpp'
CHUNK = 2000

RECOVER = b'\x03'

def open_port():
    for _ in range(6):
        try:
            return serial.Serial(PORT, BAUD, timeout=0.2)
        except Exception:
            time.sleep(2)
    raise SystemExit('无法打开 %s（板子/串口未连接？）' % PORT)

def send_wait(s, cmd, want, tmo=8, tries=3):
    w = want.encode() if isinstance(want, str) else want
    for _ in range(tries):
        s.reset_input_buffer()
        s.write(cmd.encode() + b'\n'); s.flush()
        t0 = time.time(); buf = b''
        while time.time() - t0 < tmo:
            c = s.read(8192)
            if c:
                buf += c
                if w in buf:
                    return True, buf.decode('utf-8', 'replace')
        time.sleep(0.2)
    return False, buf.decode('utf-8', 'replace')

def board_ready(s):
    for _ in range(6):
        s.write(b'\x15\x15\r\n'); time.sleep(0.3)
        s.write(b'console\r\n'); time.sleep(0.8)
        s.write(b'\x15\r\n'); time.sleep(0.4)
        ok, _ = send_wait(s, 'stty -echo; echo R$((3+4))DY', 'R7DY', 4, tries=1)
        if ok:
            return True
    return False

def sh(s, snippet, tmo=60):
    import base64
    b64 = base64.b64encode(snippet.encode()).decode()
    ok, buf = send_wait(s, "echo %s | base64 -d | bash; echo __E__" % b64, '__E__', tmo)
    lines = [l for l in buf.splitlines() if 'base64 -d | bash' not in l and '__E__' not in l]
    return '\n'.join(lines).strip()

def do_probe(s):
    print('== 板子 ==')
    print(sh(s, 'uname -a; echo ---; ls -l /dev/pango_pci_driver 2>/dev/null; '
                'lspci -nn 2>/dev/null | grep -i 0755; echo ---; '
                'ps aux | grep -a "./camview" | grep -v grep | wc -l; echo PROBE_DONE', 40))

def do_push(s, rebuild=True):
    if not os.path.exists(SRC):
        raise SystemExit('缺少 %s' % SRC)
    data = open(SRC, 'rb').read()
    md5 = hashlib.md5(data).hexdigest()
    hx = data.hex().upper()
    chunks = [hx[i:i+CHUNK] for i in range(0, len(hx), CHUNK)]
    print('本地 %s  %d bytes  md5=%s  (%d 分片)' % (SRC, len(data), md5, len(chunks)))

    if not board_ready(s):
        raise SystemExit('板子无响应（先执行 python push_dualcam.py probe 排查）')

    print('== 1. 传输源码 ==')
    sh(s, 'stty -echo; rm -f /tmp/xh')
    for i, ch in enumerate(chunks):
        ok, _ = send_wait(s, 'echo %s >> /tmp/xh; echo A$((%d))xD' % (ch, i), 'A%dxD' % i, 8, tries=3)
        if not ok:
            raise SystemExit('第 %d 片传输失败' % i)
    dec = ("python3 -c \"import binascii;open('%s','wb').write("
           "binascii.unhexlify(open('/tmp/xh').read().replace(chr(10),'').replace(chr(13),'')))\" "
           "&& rm -f /tmp/xh && md5sum %s; echo F$((7-7))INX" % (DST, DST))
    send_wait(s, dec, 'F0INX', 60)
    out = sh(s, 'stty echo; md5sum %s' % DST, 20)
    print('  远端 md5:', out.strip()[:64])
    if md5 not in out:
        raise SystemExit('源码 md5 不一致，中止')
    print('  md5 一致 OK')

    if not rebuild:
        print('== 2. 跳过重编（--no-rebuild）==')
        return

    print('== 2. 板上重编 ==')
    out = sh(s, 'pkill -f run_camview.sh 2>/dev/null; pkill -f camview 2>/dev/null; sleep 1; '
                'cd /root/ov5640/camview && rm -f camview Makefile *.o moc_* .qmake.stash && '
                '/usr/lib/qt5/bin/qmake && make -j4 > /tmp/mk.log 2>&1; echo RC=$?; '
                'grep -aiE "error" /tmp/mk.log | head -8; ls -la camview 2>/dev/null', 300)
    print(out)
    if 'RC=0' not in out:
        print('编译失败，日志尾部：'); print(sh(s, 'tail -15 /tmp/mk.log', 20)); return

    print('== 3. 复位 PCIe 驱动 ==')
    sh(s, 'pkill -f camview 2>/dev/null; sleep 1; '
          'rmmod pango_pci_driver 2>/dev/null; '
          'echo 1 > /sys/bus/pci/devices/0002:21:00.0/remove 2>/dev/null; sleep 1; '
          'echo 1 > /sys/bus/pci/rescan; sleep 2; '
          'insmod /root/ov5640/pango_pci_driver.ko 2>/dev/null; '
          'ls -l /dev/pango_pci_driver', 60)

    print('== 4. 启动显示 ==')
    sh(s, 'rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh > /dev/null 2>&1 < /dev/null & sleep 12', 60)
    print('  camview 进程数:', sh(s, 'ps aux | grep -a "./camview" | grep -v grep | wc -l', 20))
    print('== 5. 窗口状态 ==')
    print(sh(s, "DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 xprop -root _NET_CLIENT_LIST 2>/dev/null "
                "| grep -oE '0x[0-9a-f]+' | while read id; do "
                "DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 xprop -id \"$id\" _NET_WM_NAME 2>/dev/null; "
                "done | grep -a camview", 40))
    print('完成。HDMI 应显示左右并排双路画面。')

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    mode = args[0] if args else 'probe'
    s = open_port()
    try:
        if mode == 'probe':
            do_probe(s)
        elif mode == 'push':
            do_push(s, rebuild='--no-rebuild' not in sys.argv)
        else:
            print(__doc__)
    finally:
        s.close()

if __name__ == '__main__':
    main()
