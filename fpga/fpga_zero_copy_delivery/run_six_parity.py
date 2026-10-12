from pathlib import Path
import json
import sys
import argparse

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root.parent))
import board_ssh

parser=argparse.ArgumentParser()
parser.add_argument('--snapshots',action='store_true')
parser.add_argument('--background',action='store_true')
parser.add_argument('--cameras',default='1,2,3,4')
args=parser.parse_args()
if not args.cameras or any(value not in ('1','2','3','4','5','6') for value in args.cameras.split(',')):
    parser.error('Cameras must be comma-separated physical numbers 1..6')
cameras=[int(value)-1 for value in args.cameras.split(',')]
if len(set(cameras))!=len(cameras): parser.error('Duplicate camera')
client = board_ssh.connect()
snapshots = args.snapshots
name = 'thumbnail_six_snapshot_parity' if snapshots else 'thumbnail_six_parity'
if args.background: name='background_thumbnail_parity'
artifact=name+'_c'+args.cameras.replace(',','')
remote = '/userdata/linaro/fpga-zero-copy-host/' + name
if args.background: remote='/userdata/linaro/fpga-zero-copy-host-background/'+name
try:
    rc, out, err = board_ssh.run(client,
        'fuser /dev/pango_pci_driver 2>/dev/null || true', sudo=True, timeout=10)
    if rc or out.strip():
        raise RuntimeError('Six-camera parity requires exclusive device ownership')
    command=('env OFFLOAD_PARITY_CAMERAS='+args.cameras+' '+('OFFLOAD_VERIFY_SNAPSHOTS=1 ' if snapshots else '') + remote + ' 10')
    if args.background:
        command=remote+' --cameras '+args.cameras+' --count 10 --attempts 128 --timeout 30'+(' --snapshots' if snapshots else '')
    rc, out, err = board_ssh.run(client,command+' >'+remote+'.jsonl 2>'+remote+'.stderr',
        sudo=True, timeout=3600 if args.background else 120)
    with client.open_sftp() as sftp:
        for suffix in ('.jsonl', '.stderr'):
            sftp.get(remote + suffix, str(root / (artifact + suffix)))
    if rc:
        raise RuntimeError('Six-camera hardware parity failed; preserve owner and inspect stderr')
    rows = [json.loads(line) for line in (root / (artifact + '.jsonl')).read_text().splitlines()]
    frames = [row for row in rows if not row.get('summary')]
    expected = {(camera, bank): 10 for camera in cameras for bank in range(2)}
    observed = {}
    for row in frames:
        key = (row['camera']-1, row['bank']) if args.background else (row['camera'], row['output_bank'])
        observed[key] = observed.get(key, 0) + 1
        if not row['pass'] or (not args.background and not row['published']) or row['bytes_compared'] != 153600:
            raise RuntimeError('Missing hardware pixel/publication evidence')
        if snapshots and row.get('snapshot_parity') is not True:
            raise RuntimeError('Missing snapshot/scalar hardware evidence')
    if observed != expected or not rows[-1].get('pass') or rows[-1].get('frames_passed') != len(cameras)*20:
        raise RuntimeError('Incomplete camera/output-bank hardware coverage')
    print(json.dumps(rows[-1], indent=2))
finally:
    client.close()
