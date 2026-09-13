#!/usr/bin/env python3
"""recover_display.py : HDMI 显示自动恢复看门狗 (PC 端运行)

每 60 秒检查一次板上 camview 窗口标题里的 fps 数值:
  - fps 数字连续 2 次无变化(冻结) 或窗口消失 → 自动执行完整恢复:
    JTAG 重烧比特流 → PERST/重扫/重载驱动 → 重启 camview 守护
  - 恢复全程约 40 秒, 显示中断约 1 分钟

用法: python recover_display.py      (Ctrl+C 停止)
依赖: pyserial; PDS 工具在 C:/pango/PDS_2022.2-SP6.4/bin/
"""
import serial, time, base64, subprocess, sys, re

PORT, BAUD = 'COM9', 1500000
PDS = r'C:/pango/PDS_2022.2-SP6.4/bin'
TCL = r'C:\Users\NineSun\Desktop\ov56401\flash_jtag.tcl'

def serial_cmd(snippet, tmo=90):
    """板上执行 shell 片段, 返回输出文本"""
    for _ in range(3):
        try:
            s = serial.Serial(PORT, BAUD, timeout=0.2)
        except Exception:
            time.sleep(2); continue
        s.write(b'\x03'); time.sleep(0.5); s.reset_input_buffer()
        s.write(b'\x15\r\nconsole\r\n'); time.sleep(0.8); s.reset_input_buffer()
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

def get_fps():
    out = serial_cmd(
        "for id in $(DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 "
        "xprop -root _NET_CLIENT_LIST 2>/dev/null | grep -oE '0x[0-9a-f]+'); do "
        "DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 xprop -id $id _NET_WM_NAME 2>/dev/null; done | grep -a 'fps'", 30)
    m = re.search(r'([\d.]+) fps', out)
    return float(m.group(1)) if m else None

def flash_fpga():
    subprocess.run(['taskkill', '/F', '/IM', 'cdt_cfg.exe'], capture_output=True)
    subprocess.run(['taskkill', '/F', '/IM', 'cdt_js.exe'], capture_output=True)
    time.sleep(2)
    subprocess.Popen([PDS + r'/cdt_js.exe', '-port', '65422'],
                     stdout=open('cdt_js_wd.log', 'w'), stderr=subprocess.STDOUT)
    time.sleep(5)
    r = subprocess.run([PDS + r'/cdt_cfg.exe', '-ip', '127.0.0.1', '-port', '65422',
                        '-file', TCL], capture_output=True, timeout=120)
    out = (r.stdout + r.stderr).decode('utf-8', errors='replace')
    return 'execute successfully' in out and 'cfg_program' in out

def recover():
    print(time.strftime('%H:%M:%S'), '== 冻结检测, 执行恢复 ==', flush=True)
    serial_cmd("pkill -f run_camview.sh; pkill -f camview", 30)
    print(' 1/4 JTAG 重烧...', flush=True)
    if not flash_fpga():
        print('   烧写失败, 重试一次...', flush=True)
        if not flash_fpga(): print('   烧写连续失败', flush=True); return False
    print(' 2/4 PCIe 重扫 + 驱动重载...', flush=True)
    serial_cmd("rmmod pango_pci_driver 2>/dev/null; "
               "echo 1 > /sys/bus/pci/devices/0002:21:00.0/remove 2>/dev/null; sleep 1; "
               "echo 1 > /sys/bus/pci/rescan; sleep 2; "
               "insmod /root/ov5640/pango_pci_driver.ko 2>/dev/null; "
               "ls /dev/pango_pci_driver > /dev/null && echo DRV_OK", 60)
    print(' 3/4 重启 camview...', flush=True)
    serial_cmd("rm -f /tmp/camview.lock; pkill -f run_camview.sh 2>/dev/null; "
               "setsid nohup /root/ov5640/run_camview.sh > /dev/null 2>&1 < /dev/null & sleep 1", 30)
    print(' 4/4 等待出流...', flush=True)
    time.sleep(12)
    return get_fps() is not None

def main():
    print('显示看门狗启动: 每 60s 检查, fps 冻结 2 次即自动恢复 (Ctrl+C 退出)', flush=True)
    last = None; frozen = 0
    while True:
        try:
            fps = get_fps()
        except Exception as e:
            print('serial err:', e, flush=True); time.sleep(30); continue
        if fps is None:
            frozen += 1
            print('fps=None (窗口消失/卡死) frozen=%d' % frozen, flush=True)
        elif fps == last:
            frozen += 1
            print('fps=%.1f frozen=%d' % (fps, frozen), flush=True)
        else:
            frozen = 0
            print('fps=%.1f OK' % fps, flush=True)
        if frozen >= 2:
            if recover():
                print('恢复成功', flush=True); frozen = 0; last = None
            else:
                print('恢复失败, 2 分钟后重试', flush=True); time.sleep(120)
            last = None; frozen = 0
        else:
            last = fps
        time.sleep(60)

if __name__ == '__main__':
    main()
