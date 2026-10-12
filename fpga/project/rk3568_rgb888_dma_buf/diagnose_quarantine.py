from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh
client=board_ssh.connect()
try:
    command='dmesg --color=never | grep -E "pango|ioctl=|uncertain DMA|reboot required" | tail -60; ps -L -p 20108 -o pid,tid,stat,wchan:32,comm; ls -l /proc/20108/fd; ls -l /sys/bus/pci/drivers/pango_zc/; cat /sys/module/pango_zc/refcnt'
    rc,out,err=board_ssh.run(client,command,timeout=25,sudo=True)
    (Path(__file__).resolve().parent/'quarantine_health.log').write_text(out+err,encoding='utf-8')
    print(out+err)
finally:
    client.close()
