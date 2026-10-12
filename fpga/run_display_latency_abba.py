"""Sequential physical-board A/B/B/A comparison; one DMA owner at a time."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
output = root / 'display_latency_delivery/measurement'
for label, mode in [('A1', '0'), ('B1', '1'), ('B2', '1'), ('A2', '0')]:
    result = subprocess.run([sys.executable, str(root / 'display_latency_board_run.py'),
        '--binary', '/userdata/linaro/display-latency-delivery/detview', '--label', label,
        '--env', 'DETVIEW_LATE_LATCH=' + mode, '--env', 'DETVIEW_PERF=1',
        '--env', 'DETVIEW_MIN_MS=24', '--seconds', '85', '--output', str(output)])
    if result.returncode:
        raise SystemExit(result.returncode)
    print('Completed ' + label, flush=True)
subprocess.run([sys.executable, str(root / 'display_latency_compare.py'),
    *[str(output / (label + '.log')) for label in ['A1', 'B1', 'B2', 'A2']],
    '--output', str(output / 'abba_summary.json')], check=True)
