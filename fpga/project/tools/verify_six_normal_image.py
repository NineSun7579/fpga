"""Recover PCIe, capture six streams and sample faults throughout acceptance."""
import argparse
import json
from pathlib import Path
import shlex
from board_host import ssh_connect

parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
parser.add_argument('--seconds', type=int, default=30)
parser.add_argument('--cam1-delay', type=int, default=140)
args = parser.parse_args()
if not args.label.replace('_', '').replace('-', '').isalnum():
    parser.error('invalid label')
if not 1 <= args.seconds <= 300 or not 0 <= args.cam1_delay <= 255:
    parser.error('invalid duration or delay')
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
        'mkdir -p ' + shlex.quote(remote) + ' && '
        'timeout %d python3 /tmp/accept_six_streams.py --diagnostics --seconds %d --output %s'
        % (args.seconds + 20, args.seconds, shlex.quote(remote)))
    stdin, output, error = connection.exec_command('sudo -S bash -c ' + shlex.quote(operations), timeout=args.seconds + 55)
    stdin.write('123456\n'); stdin.flush()
    data, errors = output.read(), error.read()
    status = output.channel.recv_exit_status()
    (destination / 'board.jsonl').write_bytes(data)
    (destination / 'board.stderr').write_bytes(errors)
    sftp = connection.open_sftp()
    try:
        for name in sftp.listdir(remote):
            sftp.get(remote + '/' + name, str(destination / name))
    finally:
        sftp.close()
    print(json.dumps(json.loads((destination / 'report.json').read_text()), indent=2))
    raise SystemExit(status)
finally:
    connection.close()
