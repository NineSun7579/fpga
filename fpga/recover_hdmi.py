#!/usr/bin/env python3
"""recover_hdmi.py : 完整恢复链 = JTAG 重烧 + PERST 复位 + PCIe 重扫 + insmod + DMA 验证 + viewer"""
import subprocess, serial, time, sys

def flash():
    subprocess.run(['taskkill', '/F', '/IM', 'cdt_cfg.exe'], capture_output=True)
    subprocess.run(['taskkill', '/F', '/IM', 'cdt_js.exe'], capture_output=True)
    time.sleep(2)
    subprocess.Popen([r'C:/pango/PDS_2022.2-SP6.4/bin/cdt_js.exe', '-port', '65422'],
                     stdout=open('cdt_js_r.log', 'w'), stderr=subprocess.STDOUT)
    time.sleep(5)
    out = ''
    try:
        rr = subprocess.run([r'C:/pango/PDS_2022.2-SP6.4/bin/cdt_cfg.exe', '-ip', '127.0.0.1',
                             '-port', '65422', '-file', r'C:\Users\NineSun\Desktop\ov56401\flash_jtag.tcl'],
                            capture_output=True, timeout=120)
        out = (rr.stdout + rr.stderr).decode('utf-8', errors='replace')
    except subprocess.TimeoutExpired:
        subprocess.run(['taskkill', '/F', '/IM', 'cdt_cfg.exe'], capture_output=True)
        return False
    if 'execute successfully, takes' in out and 'cfg_program' in out:
        print('   flash OK via port 65422')
        return True
    print('flash FAILED:', out[-300:])
    return False

def main():
    print('== 1. JTAG 重烧 (清布线楔死) ==', flush=True)
    if not flash():
        return 1

    S = serial.Serial('COM9', 1500000, timeout=0.05)
    def sr(cmd, timeout=60):
        S.reset_input_buffer()
        S.write((cmd + '\n').encode()); S.flush()
        t0 = time.time(); buf = b''
        while time.time() - t0 < timeout:
            c = S.read(8192)
            if c:
                buf += c
                tail = buf.split(cmd.encode())[-1]
                if b'__EOC__' in tail or b'#' in tail[-8:]:
                    break
        S.reset_input_buffer()
        return buf.decode('utf-8', errors='replace')
    time.sleep(0.5); S.reset_input_buffer()

    print('== 2. PERST 复位 + PCIe 重扫 ==', flush=True)
    sr('echo 144 > /sys/class/gpio/export 2>/dev/null; echo out > /sys/class/gpio/gpio144/direction 2>/dev/null')
    sr('echo 0 > /sys/class/gpio/gpio144/value; sleep 0.2; echo 1 > /sys/class/gpio/gpio144/value; sleep 0.5; echo PERST_TOGGLED')
    out = sr('echo 1 > /sys/bus/pci/devices/0002:21:00.0/remove 2>/dev/null; sleep 1; echo 1 > /sys/bus/pci/rescan; sleep 2; lspci | grep 0755')
    print('  ', out.strip().splitlines()[-1] if out.strip() else 'lspci 空')

    print('== 3. 装载驱动 ==', flush=True)
    out = sr('insmod /root/ov5640/pango_pci_driver.ko 2>/dev/null; dmesg | grep -a "MSI Interrupt" | tail -3')
    ok = 'MSI Interrupt2 registered' in out
    print('   MSI:', 'OK' if ok else 'FAIL')
    if not ok:
        S.close(); return 1

    print('== 4. 单笔 DMA 验证 (op1 读 DDR) ==', flush=True)
    out = sr('timeout 15 python3 /root/ov5640/matrix.py E 2>/dev/null | grep -a RESULT', timeout=30)
    print('  ', out.strip().splitlines()[-1] if out.strip() else '(无输出)')
    if 'PASS' not in out:
        print('   DMA 仍不通 -> 恢复失败')
        S.close(); return 1

    print('== 5. 启动 viewer (10h) ==', flush=True)
    sr('rmmod pango_pci_driver 2>/dev/null; sleep 1; insmod /root/ov5640/pango_pci_driver.ko >/dev/null 2>&1')
    sr('cd /root/ov5640 && nohup python3 viewer.py 36000 > viewer4.log 2>&1 & echo BG')
    time.sleep(20)
    out = sr('tail -2 /root/ov5640/viewer4.log; dmesg | grep -ac "GET_IMG Error"')
    print(out)
    good = 'fps' in out and out.strip().splitlines()[-1].strip().endswith('0')
    print('== 恢复%s ==' % ('成功: HDMI 输出中' if good else '结果存疑, 查 viewer4.log'))
    S.close()
    return 0 if good else 2

if __name__ == '__main__':
    sys.exit(main())
