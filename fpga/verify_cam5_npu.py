"""Collect RK3568 live NPU/camera evidence without opening a second DMA client."""
import argparse
import json
import re
import time
from pathlib import Path
import board_ssh

parser = argparse.ArgumentParser()
parser.add_argument('--seconds', type=int, default=180)
parser.add_argument('--log', default='/userdata/linaro/cam5_npu_verify/npu_after_flash.log')
parser.add_argument('--output', default='cam5_verification')
parser.add_argument('--gl', action='store_true', help='Use detview --shot for GL screenshots')
args = parser.parse_args()
dest = Path(args.output)
dest.mkdir(exist_ok=True)
client = board_ssh.connect()
samples = []
try:
    for index in range(args.seconds // 10 + 1):
        rc, out, err = board_ssh.run(client,
            'tail -100 ' + args.log + '; cat /sys/kernel/debug/rknpu/load', sudo=True)
        panes = re.findall(r'\[panes\].*', out)
        infer = re.findall(r'\[infer-diag\].*', out)
        load = re.findall(r'NPU load:.*', out)
        sample = {'elapsed': index*10, 'panes': panes[-1:] ,
                  'infer': infer[-1:], 'load': load, 'rc': rc}
        samples.append(sample)
        print(json.dumps(sample, ensure_ascii=False), flush=True)
        if not args.gl and index in (0, args.seconds // 10):
            remote = '/tmp/cam5_verify_%d.png' % index
            rc, out, err = board_ssh.run(client,
                'export DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0; '
                '/root/ov5640/qshot/qshot ' + remote + ' 1920', sudo=True)
            if rc:
                raise RuntimeError(out + err)
            sftp = client.open_sftp()
            sftp.get(remote, str(dest / ('screen_%d.png' % index)))
            sftp.close()
        if index < args.seconds // 10:
            time.sleep(10)
    rc, out, err = board_ssh.run(client, 'cat ' + args.log, sudo=True)
    (dest / 'npu.log').write_text(out, encoding='utf8')
    (dest / 'samples.json').write_text(json.dumps(samples, ensure_ascii=False, indent=2), encoding='utf8')
    live = [s for s in samples if s['panes'] and 'have=111111' in s['panes'][0]]
    camera_rates = [float(re.search(r'cam=([\d./]+)', s['panes'][0]).group(1).split('/')[4])
                    for s in live]
    generations = [list(map(int, re.search(r'gen=([\d/]+)', s['panes'][0]).group(1).split('/')))
                   for s in live if re.search(r'gen=([\d/]+)', s['panes'][0])]
    advancing = (len(generations) == len(samples) and len(generations) > 1 and
                 all(all(b > a for a, b in zip(previous, current))
                     for previous, current in zip(generations, generations[1:])))
    passed = (advancing and len(live) == len(samples) and all(rate > 0 for rate in camera_rates)
              and all(s['infer'] for s in samples))
    print('ALL_SIX_LIVE_AND_NPU_PASS=' + str(passed), flush=True)
    if not passed:
        raise SystemExit(2)
finally:
    client.close()
