"""Recover RK PCIe after FPGA reload and retain camera/optical diagnostics."""
import argparse
import json
import shlex
import warnings
from pathlib import Path

from board_host import ssh_connect

parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
parser.add_argument('--seconds', type=int, default=30)
parser.add_argument('--cam1-delay', type=int, default=140)
args = parser.parse_args()
if not args.label.replace('_', '').replace('-', '').isalnum():
    parser.error('label must contain only letters, digits, underscores or hyphens')
if not 0 <= args.cam1_delay <= 255 or not 1 <= args.seconds <= 300:
    parser.error('invalid delay or duration')
warnings.filterwarnings('ignore')
root = Path(__file__).resolve().parents[2]
destination = root / 'log' / args.label
destination.mkdir(exist_ok=True)
remote = '/tmp/' + args.label
connection = ssh_connect(timeout=8)
try:
    sftp = connection.open_sftp()
    for name in ('cam3_i2c_pt.py', 'read_sfp_diagnostics.py', 'accept_six_streams.py'):
        sftp.put(str(root / 'project/tools' / name), '/tmp/' + name)
    sftp.close()
    delay_code = ("import sys;sys.path.insert(0,'/tmp');from cam3_i2c_pt import PciDriver;"
                  "d=PciDriver();d.write32(0x20000030,%d);d.close()" % args.cam1_delay)
    operations = (
        'rmmod pango_pci_driver && '
        'echo 1 > /sys/bus/pci/devices/0002:21:00.0/remove && '
        'sleep 1 && echo 1 > /sys/bus/pci/rescan && sleep 3 && '
        'insmod /root/ov5640/pango_pci_driver.ko && '
        'python3 -c ' + shlex.quote(delay_code) + ' && '
        'timeout 20 python3 /tmp/read_sfp_diagnostics.py && '
        'timeout %d python3 /tmp/accept_six_streams.py --seconds %d --output %s'
        % (args.seconds + 20, args.seconds, shlex.quote(remote)))
    command = 'echo 123456 | sudo -S bash -c ' + shlex.quote(operations)
    _, output, error = connection.exec_command(command, timeout=args.seconds + 45)
    data = output.read()
    errors = error.read()
    status = output.channel.recv_exit_status()
    (destination / 'board.jsonl').write_bytes(data)
    (destination / 'board.stderr').write_bytes(errors)
    sftp = connection.open_sftp()
    try:
        for name in sftp.listdir(remote):
            sftp.get(remote + '/' + name, str(destination / name))
    finally:
        sftp.close()
    report = json.loads((destination / 'report.json').read_text())
    print(json.dumps(report, indent=2))
    print('Evidence:', destination)
    raise SystemExit(status)
finally:
    connection.close()
