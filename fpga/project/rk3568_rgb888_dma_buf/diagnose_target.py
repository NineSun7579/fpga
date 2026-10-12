"""Read-only target health with extended SSH handshake timeout."""
from pathlib import Path
import sys
import paramiko
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh
client=paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(board_ssh.HOST,username=board_ssh.USER,password=board_ssh.PW,
               timeout=15,banner_timeout=40,auth_timeout=20,allow_agent=False,look_for_keys=False)
try:
    rc,out,err=board_ssh.run(client,
        'ps -eo pid,ppid,stat,etime,pcpu,args | grep -E "model_contract_probe|detview|cc1plus"; '
        'free -m; cat /proc/sys/kernel/random/boot_id; fuser /dev/pango_pci_driver; '
        'ls /dev/pango_pci_driver; cat /sys/module/pango_zc/refcnt; '
        'dmesg | grep -Ei "out of memory|oom-kill|killed process" | tail -15; '
        'tail -12 /userdata/linaro/rgb888_trial_1791561582715191600/restored_acceptance.log; '
        'ps -eo pid,args | grep -E "Xorg|xinit"; '
        'ls -la /home/linaro/.Xauthority /root/.Xauthority; '
        'sha256sum /userdata/detview-hdmifull/detview-hdmifull',
        timeout=30,sudo=True)
    text=out+err
    (Path(__file__).resolve().parent/'target_health.log').write_text(text,encoding='utf-8')
    print(text)
    if rc: raise RuntimeError('Target health command failed')
finally:
    client.close()
