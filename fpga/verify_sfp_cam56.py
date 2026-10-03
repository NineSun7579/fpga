# -*- coding: utf-8 -*-
"""100H烧录后启动camview并截图验证cam5/cam6"""
import sys, time, base64
sys.path.insert(0, r'C:\Users\NineSun\Desktop\ov56401\project')
import board_ssh

def sh(cli, cmd, timeout=120):
    rc, out, err = board_ssh.run(cli, cmd, timeout=timeout, sudo=True)
    print(f"$ {cmd}")
    if out.strip(): print(out.rstrip())
    if err.strip() and "password" not in err: print(f"ERR: {err.rstrip()[:400]}")
    return rc, out, err

print("=== 1. 连接3568 (192.168.10.203) ===")
cli = board_ssh.connect()

print("\n=== 2. 停止camview + 卸载驱动 ===")
sh(cli, "pkill -9 -x run_camview.sh; pkill -9 -x camview; sleep 2")
sh(cli, "rmmod pango_pci_driver 2>/dev/null || echo 'not loaded'")

print("\n=== 3. PCIe remove + rescan ===")
sh(cli, "echo 1 > /sys/bus/pci/devices/0002:21:00.0/remove; sleep 2")
sh(cli, "echo 1 > /sys/bus/pci/rescan; sleep 3")
sh(cli, "lspci | grep -i xilinx || echo 'PCIe设备未识别'")

print("\n=== 4. 加载驱动 ===")
sh(cli, "insmod /root/ov5640/pango_pci_driver.ko && echo 'insmod OK'; sleep 2")
sh(cli, "ls -l /dev/pango_pci_driver")

print("\n=== 5. 启动camview ===")
sh(cli, "export DISPLAY=:0; export XAUTHORITY=/var/run/lightdm/root/:0; "
       "rm -f /tmp/camview.lock; cd /root/ov5640/camview && "
       "setsid nohup /root/ov5640/run_camview.sh > /tmp/camview.log 2>&1 < /dev/null &")
time.sleep(6)
sh(cli, "pgrep -af camview")

print("\n=== 6. 等待5秒后截图 (xwd) ===")
time.sleep(5)
XENV = "export DISPLAY=:0; export XAUTHORITY=/var/run/lightdm/root/:0;"
sh(cli, f"{XENV} xwd -root -silent | gzip -1 | base64 -w0 > /tmp/shot_sfp_cam56.b64", timeout=40)
rc, out, err = sh(cli, "wc -c /tmp/shot_sfp_cam56.b64", 30)
print(f"截图base64大小: {out.strip()}")

print("\n=== 7. 下载截图到本地 ===")
rc, b64_data, err = board_ssh.run(cli, "cat /tmp/shot_sfp_cam56.b64", timeout=60)
import gzip
raw_xwd = gzip.decompress(base64.b64decode(b64_data.strip()))
local_path = r'C:\Users\NineSun\Desktop\ov56401\project\shot_sfp_cam56.xwd'
with open(local_path, 'wb') as f:
    f.write(raw_xwd)
print(f"✓ 截图已保存: {local_path} ({len(raw_xwd)} bytes)")

print("\n=== 8. 转换为PNG ===")
import subprocess
try:
    subprocess.run(['convert', local_path, local_path.replace('.xwd', '.png')], 
                   check=True, timeout=30, capture_output=True)
    print(f"✓ PNG已生成: {local_path.replace('.xwd', '.png')}")
except Exception as e:
    print(f"转换失败 (需要ImageMagick): {e}")
    print(f"手动转换: convert {local_path} {local_path.replace('.xwd', '.png')}")

cli.close()
print("\n=== 完成 ===")
print("请查看 shot_sfp_cam56.png，确认cam5/cam6是否显示50K双摄画面")
