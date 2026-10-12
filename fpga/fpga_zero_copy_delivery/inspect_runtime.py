from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh
client=board_ssh.connect()
try:
    command="cat /proc/7004/maps | grep pango; ls -l /proc/7004/fd; dmesg | tail -n 8"
    rc,out,err=board_ssh.run(client,command,sudo=True,timeout=20)
    (Path(__file__).resolve().parent/'shared_smoke_failure.txt').write_text(out+err,encoding='utf-8')
    print(out+err)
finally:
    client.close()
