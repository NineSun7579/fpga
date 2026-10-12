"""Audit finite motion snapshots and report tag progression without lease claims."""
import json
import sys
from pathlib import Path

p = Path(sys.argv[1])
doc = json.loads(p.read_bytes())
assert doc['status'] == 'completed' and len(doc['rows']) == 7
rows = doc['rows']
result = {'motion': [], 'camera_tag_delta': [], 'cam5_lease_validation': 'pending', 'errors': []}
for camera in range(4):
    sequences = []
    for row in rows:
        w = row['motion'][camera]['words']
        assert len(w) == 10
        seq, flags, counts, bbox = w[:4]
        bitmap = sum(value << (32 * index) for index, value in enumerate(w[4:]))
        blocks, samples = counts & 255, counts >> 8 & 65535
        assert blocks == bitmap.bit_count(), (camera, 'bitmap/count', w)
        assert samples <= 19200 and blocks <= 192
        if flags & 2:
            cells = [i for i in range(192) if bitmap >> i & 1]
            assert cells
            expected = min(i % 16 for i in cells) | max(i % 16 for i in cells) << 4 | min(i // 16 for i in cells) << 8 | max(i // 16 for i in cells) << 12
            assert bbox & 65535 == expected, (camera, 'bbox', w)
        if flags & 4:
            result['errors'].append({'camera': camera + 1, 'sequence': seq, 'error': 'frame_error'})
        sequences.append(seq)
    result['motion'].append({'camera': camera + 1, 'sequences': sequences,
                             'advances': sum(a != b for a, b in zip(sequences, sequences[1:])),
                             'comparison_valid_samples': sum(bool(row['motion'][camera]['words'][1] & 1) for row in rows)})
for camera in range(6):
    first, last = max(rows[0]['tags'][camera]), max(rows[-1]['tags'][camera])
    result['camera_tag_delta'].append({'camera': camera + 1, 'first': first, 'last': last,
                                     'delta': (last - first) & 0xffffffff})
result['limitations'] = 'Tag progression does not certify frame ownership or physical RAW identity. CAM5 remains unarmed pending dual-consumer lease validation.'
result['motion_frame_error_check_passed'] = not result['errors']
(p.parent / 'observation_audit.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
raise SystemExit(0 if not result['errors'] else 2)
