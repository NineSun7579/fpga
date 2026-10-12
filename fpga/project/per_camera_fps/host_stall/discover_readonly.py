import pathlib
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'tools'))
from board_host import ssh_connect
client = ssh_connect()
stdin, stdout, stderr = client.exec_command("ps -eo pid,comm,args | grep -E '[d]etview|[c]amview'", timeout=15)
print(stdout.read().decode())
client.close()
