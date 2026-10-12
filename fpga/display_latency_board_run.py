"""Run one authorized display comparison arm and collect logs after a bounded interval."""
import argparse
import pathlib
import shlex
import time

import board_ssh

parser = argparse.ArgumentParser()
parser.add_argument('--binary', required=True)
parser.add_argument('--label', required=True)
parser.add_argument('--env', action='append', default=[])
parser.add_argument('--seconds', type=int, default=85)
parser.add_argument('--output', required=True, type=pathlib.Path)
args = parser.parse_args()
if not args.label.replace('_', '').isalnum():
    raise ValueError('invalid label')
for item in args.env:
    if '=' not in item or not item.split('=', 1)[0].replace('_', '').isalnum():
        raise ValueError('invalid environment argument')
remote_log = '/userdata/linaro/display-latency-delivery/' + args.label + '.log'
env = ['DISPLAY=:0', 'XAUTHORITY=/var/run/lightdm/root/:0', 'QT_QPA_PLATFORM=xcb',
       'QT_XCB_GL_INTEGRATION=xcb_egl', 'DET_BENCH=1'] + args.env
client = board_ssh.connect()
try:
    rc, out, err = board_ssh.run(client, 'pkill -x detview-hdmiful; pkill -x detview; sleep 1; fuser /dev/pango_pci_driver', sudo=True)
    if out.strip() or 'pango_pci_driver:' in err:
        raise RuntimeError('DMA still owned: ' + out + err)
    command = ('cd /userdata/detview-hdmifull; setsid nohup env '
               + ' '.join(map(shlex.quote, env)) + ' ' + shlex.quote(args.binary)
               + ' --model MVP_accuracy_round1 --fullscreen >' + shlex.quote(remote_log)
               + ' 2>&1 </dev/null & echo $!')
    rc, out, err = board_ssh.run(client, command, sudo=True)
    if rc:
        raise RuntimeError(out + err)
    print('Started ' + args.label + ' PID ' + out.strip(), flush=True)
finally:
    client.close()
# Run this tool in background; completion notification delivers the final receipt.
remaining = args.seconds
while remaining > 0:
    interval = min(30, remaining)
    time.sleep(interval)
    remaining -= interval
client = board_ssh.connect()
try:
    args.output.mkdir(parents=True, exist_ok=True)
    with client.open_sftp() as stream:
        stream.get(remote_log, str(args.output / (args.label + '.log')))
    rc, out, err = board_ssh.run(client, 'pgrep -a -x detview; pgrep -a -x detview-hdmiful; tail -n 5 ' + shlex.quote(remote_log), sudo=True)
    print(out + err)
finally:
    client.close()
