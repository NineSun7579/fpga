from pathlib import Path
import sys, json, hashlib, datetime
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'tools'))
from board_host import ssh_connect, board_host
out = Path(__file__).parent
label = sys.argv[1]
command = (out / (label + '.command.txt')).read_text(encoding='utf-8')
start = datetime.datetime.now(datetime.timezone.utc).isoformat()
cli = ssh_connect()
try:
    _, stdout, stderr = cli.exec_command(command, timeout=90)
    rawout = stdout.read(); rawerr = stderr.read()
    rc = stdout.channel.recv_exit_status()
finally:
    cli.close()
(out / (label + '.stdout.txt')).write_bytes(rawout)
(out / (label + '.stderr.txt')).write_bytes(rawerr)
receipt = dict(command=command, host=board_host(), rc=rc, started_utc=start,
    ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    stdout_sha256=hashlib.sha256(rawout).hexdigest(), stderr_sha256=hashlib.sha256(rawerr).hexdigest())
(out / (label + '.receipt.json')).write_text(json.dumps(receipt, indent=2), encoding='utf-8')
print(json.dumps(receipt, indent=2)); print(rawout.decode(errors='replace')); print(rawerr.decode(errors='replace'))
