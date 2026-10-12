"""Summarize a successful real-provider JSONL run; do not substitute simulation."""
import argparse
import json
import math
from pathlib import Path
import statistics

parser = argparse.ArgumentParser()
parser.add_argument('log', type=Path)
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
records = [json.loads(line) for line in args.log.read_text().splitlines() if line.strip()]
if not records or records[0].get('kind') != 'identity' or records[-1].get('kind') != 'pass':
    raise RuntimeError('Missing complete hardware benchmark identity/pass receipts')
identity, final = records[0], records[-1]
pairs = records[1:-1]
if not pairs or any(row.get('kind') != 'pair' for row in pairs) or final.get('pairs') != len(pairs):
    raise RuntimeError('Incomplete pair inventory')
for field in ('model_sha256', 'runtime_sha256'):
    value = identity.get(field, '')
    if len(value) != 64 or any(char not in '0123456789abcdef' for char in value):
        raise RuntimeError('Invalid identity: ' + field)
if identity.get('rtl_signature') not in (0x444c5632, '444c5632', '0x444c5632'):
    raise RuntimeError('Missing actual DLV2 hardware signature')
seen = set()
for row in pairs:
    key = (row['generation'], row['sequence'], row['camera'])
    if key in seen:
        raise RuntimeError('Repeated raw-frame identity')
    seen.add(key)
    for field in ('cpu_total_ms', 'fpga_total_ms'):
        value = row[field]
        if not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0:
            raise RuntimeError('Invalid latency')
result = {'identity': identity, 'paired_frames': len(pairs),
          'metric': 'sum of measured per-arm stages including claim, DMA, preparation, completed inference and lease release',
          'exclusions': 'cross-arm parity checking and output bookkeeping; not viewer FPS or concurrent pipeline throughput',
          'input_parity': 'benchmark only emits pass after byte equality and detection parity on every pair',
          'profiles': {}}
for name in ('cpu', 'fpga'):
    values = sorted(row[name + '_total_ms'] for row in pairs)
    result['profiles'][name] = {'mean_ms': statistics.mean(values),
                                'median_ms': statistics.median(values),
                                'p95_ms': values[math.ceil(.95 * len(values)) - 1],
                                'stage_accounted_fps': 1000 * len(values) / sum(values)}
baseline = result['profiles']['cpu']['stage_accounted_fps']
candidate = result['profiles']['fpga']['stage_accounted_fps']
result['stage_accounted_speedup_percent'] = 100 * (candidate / baseline - 1)
args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, indent=2))
