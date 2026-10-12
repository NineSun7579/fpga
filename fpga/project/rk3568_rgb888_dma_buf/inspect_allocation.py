from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh
client=board_ssh.connect()
try:
    command='grep -E "Cma|MemAvailable" /proc/meminfo; grep -E "pango|ioctl=|cma_alloc|alloc failed" /userdata/linaro/ov56401-recovery-logs-1791576402528345876/kern.log | tail -30; fuser /dev/pango_pci_driver'
    rc,out,err=board_ssh.run(client,command,timeout=30,sudo=True)
    (Path(__file__).resolve().parent/'allocation_evidence.log').write_text(out+err,encoding='utf-8')
    print(out+err)
finally:client.close()
