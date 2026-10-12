"""Summarize runtime counters without treating redraws as unique frames."""
import json
import re
from pathlib import Path
root = Path(__file__).resolve().parents[2] / 'log/camview_fps_audit_20261003'
reports = {}
for p in root.glob('*_runtime.txt'):
    text = p.read_text(encoding='utf8', errors='replace')
    displays = [float(x) for x in re.findall(r'(?:submit|camview)_fps=([\d.]+)', text)]
    paints = [float(x) for x in re.findall(r'uploaded_fps=([\d.]+)', text)]
    cameras = {}
    presented = {}
    for line in text.splitlines():
        present = re.match(r'(?:upload|present) camera=(\d+) fps=([\d.]+)', line)
        if present:
            presented.setdefault(int(present[1]), []).append(float(present[2]))
        if not line.startswith('capture camera='):
            continue
        values = dict(re.findall(r'(\w+)=([\d.]+)', line))
        cameras.setdefault(int(values['camera']), []).append({k: float(v) for k, v in values.items()})
    result = {'composition_fps_mean': sum(displays) / len(displays) if displays else None,
              'uploaded_fps_mean': sum(paints) / len(paints) if paints else None,
              'cameras': {},
              'presented_camera_fps': {cam: sum(values) / len(values) for cam, values in presented.items()}}
    for cam, rows in cameras.items():
        seconds = sum(r['seconds'] for r in rows)
        frames = sum(r['frames'] for r in rows)
        result['cameras'][cam] = {
            'seconds': seconds,
            'delivered_fps': frames / seconds,
            'sequence_fps': sum(r['sequence_fps'] * r['seconds'] for r in rows) / seconds,
            'unstable': sum(r['unstable'] for r in rows),
            'read_ms': sum(r['read_ms'] * r['frames'] for r in rows) / frames if frames else 0,
            'dma_ms': sum(r.get('dma_ms', 0) * r['frames'] for r in rows) / frames if frames else 0,
        }
    reports[p.stem] = result
(root / 'fps_summary.json').write_text(json.dumps(reports, indent=2), encoding='utf8')
print(json.dumps(reports, indent=2))
