"""Summarize retained detview logs without treating sampled rates as totals."""
import argparse
import json
from pathlib import Path
import re


def summarize(text):
    displays = []
    cameras = {str(index): [] for index in range(1, 7)}
    inference = []
    camera_upload_bytes = 0
    for line in text.splitlines():
        values = dict(re.findall(r'(\w+)=([\d.]+)', line))
        if line.startswith('[display-perf]') and 'seconds' in values:
            displays.append({key: float(value) for key, value in values.items()})
        elif line.startswith('[capture]') and values.get('camera') in cameras:
            cameras[values['camera']].append({key: float(value) for key, value in values.items()})
        elif line.startswith('[stats]') and 'npu_completed_fps' in values:
            inference.append(float(values['npu_completed_fps']))
        elif line.startswith('[display-upload]') and 'bytes' in values:
            camera_upload_bytes += int(values['bytes'])
    seconds = sum(row['seconds'] for row in displays)
    def weighted(key):
        return sum(row.get(key, 0) * row['seconds'] for row in displays) / seconds if seconds else None
    return {
        'display_window_seconds': seconds,
        'display_fresh_paint_fps': weighted('new_paint_fps'),
        'display_upload_fps': weighted('upload_fps'),
        'display_swap_fps': weighted('swap_fps'),
        'hud_upload_payload_bytes_per_second': sum(row.get('upload_bytes', 0) for row in displays) / seconds if seconds else None,
        'camera_gpu_upload_payload_bytes_per_second': camera_upload_bytes / seconds if seconds else None,
        'sampled_one_second_inference_completed_fps': inference,
        'inference_measurement_limit': 'Sampled one-second counts do not establish total completions over the observation.',
        'camera_windows': cameras,
        'traffic_measurement_limit': 'GPU payload counts measure uploads; they do not measure FPGA or host physical DDR bandwidth.'
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.log.read_text(encoding='utf-8'))
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key != 'camera_windows'}, indent=2))
