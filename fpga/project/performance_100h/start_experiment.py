"""Launch a pinned private detview build with explicit experiment settings."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--build', default='053c691e05d07408')
parser.add_argument('--ring', type=int, default=1)
parser.add_argument('--capture-fps', type=int, default=0)
parser.add_argument('--check', action='store_true')
args = parser.parse_args()
if not 1 <= args.ring <= 3 or not 0 <= args.capture_fps <= 120:
    parser.error('Ring 1..3 and capture FPS 0..120 required')
receipt = json.loads((HERE / 'builds' / args.build / 'receipt.json').read_text())
if receipt['status'] != 'built':
    raise RuntimeError('Successful build required')
assets = json.loads((HERE / 'model_assets.json').read_text())
command = [sys.executable, str(HERE / 'board_session.py'), '--check' if args.check else '--start',
           '--exe', receipt['binary'], '--sha256', receipt['binary_sha256'],
           '--env', 'DETVIEW_TEXTURE_RING=' + str(args.ring),
           '--env', 'DETVIEW_CAPTURE_MAX_FPS=' + str(args.capture_fps)]
for path, digest in assets.items():
    command += ['--asset', path + '=' + digest]
subprocess.run(command, check=True)
