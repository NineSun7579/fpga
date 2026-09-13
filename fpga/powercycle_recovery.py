#!/usr/bin/env python3
"""powercycle_recovery.py : 板子断电重启后的一键恢复脚本
前提: 板子已断电并重新上电 (FPGA 从 SPI Flash 加载旧比特流)
执行: JTAG 烧新比特流 -> PCIe 重扫 -> 装载驱动 -> 启动 HDMI viewer -> 验证出帧
"""
import subprocess, serial, time, sys

S = None
def sr(cmd, timeout=60):
    S.reset_input_buffer()
    S.write((cmd + '\n').encode()); S.flush()
    t0 = time.time(); buf = b''
    while time.time() - t0 < timeout:
        c = S.read(8192)
        if c:
            buf += c
            if b'__RDY__' in buf.split(cmd.encode())[-1]:
                break
    S.reset_input_buffer()
    return buf.decode('utf-8', errors='replace')

def main():
    global S
    # 1) JTAG 烧录新比特流
    print('== 1. JTAG 烧录 bitstream_2026-09-11 ==', flush=True)
    r = subprocess.run(['C:/pango/PDS_2022.2-SP6.4/bin/cdt_cfg.exe', '-ip', '127.0.0.1',
                        '-port', '65420', '-file', r'C:\Users\NineSun\Desktop\ov56401\flash_jtag.tcl'],
                       capture_output=True, timeout=300)
    out = (r.stdout + r.stderr).decode('utf-8', errors='replace')
    if 'Program] execute successfully' not in out:
        print('烧录失败:', out[-500:]); return 1
    print('   烧录成功 (3.6s)')

    # 2) 串口连板
    S = serial.Serial('COM9', 1500000, timeout=0.05)
    S.reset_input_buffer(); S.write(b'\n'); time.sleep(0.5); S.reset_input_buffer()
    print('== 2. 重扫 PCIe + 装载驱动 ==', flush=True)
    sr('echo 1 > /sys/bus/pci/devices/0002:21:00.0/remove 2>/dev/null; sleep 1; echo 1 > /sys/bus/pci/rescan; sleep 2')
    sr('rmmod pango_pci_driver 2>/dev/null')
    out = sr('insmod /root/ov5640/pango_pci_driver.ko && echo INSMOD_OK; dmesg | grep -aE "MSI Interrupt" | tail -3')
    print(out)
    if 'MSI Interrupt2 registered' not in out:
        print('驱动 probe 失败'); return 1

    # 3) 启动 HDMI viewer (10 小时)
    print('== 3. 启动 HDMI viewer (10h) ==', flush=True)
    sr('pkill -f viewer.py 2>/dev/null; sleep 1')
    sr('cd /root/ov5640 && nohup python3 viewer.py 36000 > /root/ov5640/viewer3.log 2>&1 & echo STARTED')
    time.sleep(15)
    log = sr('tail -3 /root/ov5640/viewer3.log')
    print(log)
    if 'fps' in log:
        print('== 恢复完成: HDMI 实时画面输出中 ==')
        S.close(); return 0
    print('viewer 未出帧, 检查日志 /root/ov5640/viewer3.log')
    S.close(); return 1

if __name__ == '__main__':
    sys.exit(main())
