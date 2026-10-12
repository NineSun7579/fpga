"""Read-only Linux process and devfreq sampling; CPU 100% means one full core."""
import argparse
import json
import os
from pathlib import Path
import time

parser = argparse.ArgumentParser()
parser.add_argument('--pid', type=int, required=True)
parser.add_argument('--seconds', type=int, default=60)
args = parser.parse_args()
ticks = os.sysconf('SC_CLK_TCK')
proc = Path('/proc') / str(args.pid)

def read():
    stat = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
    status = (proc / 'status').read_text().splitlines()
    rss = next(int(line.split()[1]) for line in status if line.startswith('VmRSS:'))
    freq = {}
    for device in Path('/sys/class/devfreq').iterdir():
        try:
            freq[device.name] = int((device / 'cur_freq').read_text())
        except (OSError, ValueError):
            pass
    return {'time': time.monotonic(), 'ticks': int(stat[11]) + int(stat[12]),
            'start_ticks': int(stat[19]), 'rss_kib': rss, 'frequencies': freq}

first = previous = read()
rows = []
for _ in range(args.seconds):
    time.sleep(1)
    current = read()
    if current['start_ticks'] != first['start_ticks']:
        raise RuntimeError('PID recycled during sampling')
    current['cpu_percent_one_core'] = (current['ticks'] - previous['ticks']) / ticks / (current['time'] - previous['time']) * 100
    rows.append(current)
    previous = current
duration = previous['time'] - first['time']
print(json.dumps({'pid': args.pid, 'wall_seconds': duration,
    'cpu_percent_one_core': (previous['ticks'] - first['ticks']) / ticks / duration * 100,
    'peak_rss_kib': max(row['rss_kib'] for row in rows), 'samples': rows}, indent=2))
