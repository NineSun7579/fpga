"""Read-only board/session identity; never opens the DMA device."""
from pathlib import Path
import sys
import json
import argparse
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from board_host import ssh_connect, board_host

COMMAND = """cat /proc/sys/kernel/random/boot_id
uname -r
fuser /dev/pango_pci_driver 2>&1
pgrep -a -f '[d]etview|[c]amview'
lsmod | grep pango
lspci -nn | grep '0755'
sha256sum /userdata/linaro/projects/fpga/RK3568/driver/pango_pci_driver_fixed_20260926.ko
od -An -tx1 /sys/module/pango_pci_driver/notes/.note.gnu.build-id
"""

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('baseline_identity.json'))
    args = parser.parse_args()
    client = ssh_connect()
    try:
        _, stdout, stderr = client.exec_command(COMMAND, timeout=20)
        result = {'host': board_host(), 'captured_utc': datetime.now(timezone.utc).isoformat(),
                  'command': COMMAND, 'stdout': stdout.read().decode(errors='replace'),
                  'stderr': stderr.read().decode(errors='replace'),
                  'exit_code': stdout.channel.recv_exit_status()}
    finally:
        client.close()
    args.output.write_text(
        json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
