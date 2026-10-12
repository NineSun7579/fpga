"""Read a deployment's runtime logs and parity markers without changing state."""
from pathlib import Path
import argparse
import json
import shlex
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh
root=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('receipt',type=Path)
args=parser.parse_args()
receipt=args.receipt.resolve()
receipt.relative_to(root)
data=json.loads(receipt.read_text())
candidate=data['candidate']
client=board_ssh.connect()
try:
    with client.open_sftp() as sftp:
        sftp.get(candidate['log'],str(receipt.parent/'candidate_runtime.log'))
    log=(receipt.parent/'candidate_runtime.log').read_text(errors='replace')
    markers=[line for line in log.splitlines() if '[scheme2' in line]
    (receipt.parent/'parity_markers.log').write_text('\n'.join(markers)+'\n',encoding='utf-8')
    rc,out,err=board_ssh.run(client,'fuser /dev/pango_pci_driver; cat /proc/sys/kernel/random/boot_id; tail -20 '+shlex.quote(candidate['log']),timeout=25,sudo=True)
    (receipt.parent/'runtime_health.log').write_text(out+err,encoding='utf-8')
    print('\n'.join(markers[-35:]))
    print(out+err)
finally:
    client.close()
