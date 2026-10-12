from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh
client=board_ssh.connect()
try:
    rc,out,err=board_ssh.run(client,'dmesg --color=never | grep -aE "pango|ioctl=|quarant|uncertain DMA|reboot required" | tail -60; cat /sys/module/pango_zc/refcnt; cat /sys/module/pango_zc/holders/*/refcnt 2>/dev/null; fuser /dev/pango_pci_driver',timeout=30,sudo=True)
    (Path(__file__).resolve().parent/'idle_driver_health.log').write_text(out+err,encoding='utf-8')
    print(out+err)
finally:client.close()
