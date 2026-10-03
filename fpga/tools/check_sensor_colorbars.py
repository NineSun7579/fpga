"""Measure stationary sensor bar geometry in saved 640x480 RGB565 frames."""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


def inspect(path):
    data = path.read_bytes()
    if len(data) != 640 * 480 * 2:
        raise ValueError(f'Unexpected frame size: {path}: {len(data)}')
    pixels = np.frombuffer(data, dtype='<u2').reshape(480, 640)
    rgb = np.stack([((pixels >> 11) & 31) * 255 // 31,
                    ((pixels >> 5) & 63) * 255 // 63,
                    (pixels & 31) * 255 // 31], axis=-1).astype('uint8')
    Image.fromarray(rgb).save(path.with_suffix('.png'))
    # Standard bars contain a broad yellow strip. Ignore isolated bright noise.
    yellow = (rgb[:, :, 0] > 180) & (rgb[:, :, 1] > 180) & (rgb[:, :, 2] < 100)
    edges = []
    for row_index, row in enumerate(yellow):
        changes = np.diff(np.pad(row.astype('int8'), (1, 1)))
        starts, ends = np.flatnonzero(changes == 1), np.flatnonzero(changes == -1)
        runs = [(int(start), int(end)) for start, end in zip(starts, ends) if end - start >= 30]
        if len(runs) == 1:
            edges.append((row_index, *runs[0]))
    reference = rgb[0].astype('int16')
    difference = np.max(np.abs(rgb.astype('int16') - reference[None, :, :]), axis=2)
    changed_fraction = np.mean(difference > 24, axis=1)
    result = {'frame': str(path), 'yellow_rows': len(edges), 'geometry_pass': False,
              'whole_row_comparison': {
                  'reference_row': 0,
                  'rgb_difference_threshold': 24,
                  'maximum_changed_fraction': float(np.max(changed_fraction)),
                  'last_row_changed_fraction': float(changed_fraction[-1]),
                  'rows_with_over_3_percent_changed': int(np.count_nonzero(changed_fraction > 0.03)),
                  'interpretation': 'Supporting evidence for stationary bars only; compare palette and screenshot separately.'}}
    if len(edges) >= 2:
        points = np.asarray(edges)
        result.update(first=edges[0], last=edges[-1],
                      left_edge_span=int(np.ptp(points[:, 1])),
                      right_edge_span=int(np.ptp(points[:, 2])),
                      left_slope_pixels_per_row=float(np.polyfit(points[:, 0], points[:, 1], 1)[0]))
        result['geometry_pass'] = (len(edges) == 480 and result['left_edge_span'] <= 2
                                   and result['right_edge_span'] <= 2)
    result['scope'] = 'Yellow bar edge continuity only; frame freshness and complete-frame counters require separate board evidence.'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('frames', nargs='+', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    results = [inspect(path) for path in args.frames]
    report = {'results': results, 'geometry_pass': all(row['geometry_pass'] for row in results)}
    args.output.write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps(report, indent=2))
    return 0 if report['geometry_pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
