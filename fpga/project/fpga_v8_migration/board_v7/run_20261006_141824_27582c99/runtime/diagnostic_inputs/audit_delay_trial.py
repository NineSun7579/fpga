"""Report delay trial counts without equating sampled windows to all frames."""
import json
from pathlib import Path
import sys

path = Path(sys.argv[1])
doc = json.loads(path.read_bytes())
assert doc['status'] == 'completed_restored_140', doc['status']
result = {'status': doc['status'], 'stages': [], 'limitations':
    'Stable source windows are sampled, may repeat, and do not certify image pixel values. Delay readback is unavailable. DDR counters cover all rejected frames within each measured interval.'}
for stage in doc['stages']:
    cameras = []
    for camera in range(2):
        rows = [row[camera] for row in stage['rows'] if row[camera]['stable']]
        pixels = {}
        unique_short = set()
        for row in rows:
            key = str(row['pixels'])
            pixels[key] = pixels.get(key, 0) + 1
            if row['pixels'] != 307200:
                unique_short.add(row['before'])
        before, after = stage['before'][camera], stage['after'][camera]
        cameras.append({'camera': camera + 1, 'stable_samples': len(rows), 'pixels': pixels,
            'distinct_sampled_short_sequences': sorted(unique_short),
            'drop_values': sorted(set(row['drop'] for row in rows)),
            'ddr_short_delta': ((after['short_overflow'] & 65535) - (before['short_overflow'] & 65535)) & 65535,
            'ddr_overflow_delta': ((after['short_overflow'] >> 16) - (before['short_overflow'] >> 16)) & 65535,
            'published_delta': (after['published'] - before['published']) & 0xffffffff,
            'source_sequence_delta': (after['source_sequence'] - before['source_sequence']) & 0xffffffff,
            'last_fault': hex(after['fault'])})
    result['stages'].append({'step': stage['step'], 'seconds': stage['ended'] - stage['started'], 'cameras': cameras})
(path.parent / (path.stem + '_audit.json')).write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
