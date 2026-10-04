#!/usr/bin/env python3
"""Aggregate video tracker debug evidence without claiming ground-truth accuracy."""
import argparse
import json
from pathlib import Path
import re
import statistics

import analyze_display_perf as display


def overlap(a, b):
    inter = max(0, min(a['x'] + a['w'], b['x'] + b['w']) - max(a['x'], b['x'])) * \
            max(0, min(a['y'] + a['h'], b['y'] + b['h']) - max(a['y'], b['y']))
    union = a['w'] * a['h'] + b['w'] * b['h'] - inter
    return inter / union if union > 0 else 0


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('folder', type=Path)
    args = cli.parse_args()
    folder = args.folder
    text = (folder / 'detview.log').read_text(encoding='utf-8', errors='replace')
    bounds = json.loads((folder / 'sample.window.json').read_text())
    debug = [json.loads(line.split('] ', 1)[1]) for line in text.splitlines() if line.startswith('[tracker-debug]')]
    detected = [json.loads(line.split('] ', 1)[1]) for line in text.splitlines() if line.startswith('[detector-debug]')]
    steady = [row for row in debug if bounds['started_ms'] <= row['captured_at_host_ms'] <= bounds['ended_ms']]
    detections = [row for row in detected if bounds['started_ms'] <= row['received_at_host_ms'] <= bounds['ended_ms']]
    if not steady or not detections:
        raise ValueError('Missing sampled tracker/detector evidence')
    tracks = [box for row in steady for box in row['boxes'] if box['id'] != '0']
    if any(box['class'] != 1 for box in tracks):
        raise ValueError('Nonvehicle template track found')
    raw_classes = sorted({box['class'] for row in detections for box in row['boxes']})
    detector_gaps = [b['received_at_host_ms'] - a['received_at_host_ms'] for a, b in zip(detections, detections[1:])]
    source_tracks = {(row['generation'], row['source_frame']): row for row in steady}
    detector_agreement = []
    for row in detections:
        tracked_row = source_tracks.get((row['generation'], row['source_frame']))
        if tracked_row is None:
            continue
        vehicles = [box for box in tracked_row['boxes'] if box['id'] != '0' and box['class'] == 1]
        for box in row['boxes']:
            if box['class'] != 1 or box['score'] < .7:
                continue
            iou = max((overlap(box, track) for track in vehicles), default=0)
            detector_agreement.append({'source_frame': row['source_frame'], 'score': box['score'], 'best_track_iou': iou})
    potential_duplicates = []
    for row in steady:
        observed = [box for box in row['boxes'] if box['id'] != '0' and not box['predicted']]
        for i, a in enumerate(observed):
            for b in observed[i + 1:]:
                iou = overlap(a, b)
                if iou > .85:
                    potential_duplicates.append({'source_frame': row['source_frame'],
                        'ids': [a['id'], b['id']], 'iou': iou})
    windows = [row for row in display.parse(text) if
               row['metrics'].get('started_ms', -1) >= bounds['started_ms'] and
               row['metrics'].get('ended_ms', float('inf')) <= bounds['ended_ms']]
    samples = [json.loads(line) for line in (folder / 'sample.jsonl').read_text().splitlines() if line]
    elapsed = samples[-1]['monotonic_s'] - samples[0]['monotonic_s']
    decoder_measured = all(row.get('children') for row in samples)
    analysis_rows = []
    for line in text.splitlines():
        if not line.startswith('[analysis]'):
            continue
        row = dict(re.findall(r'(\w+)=([^\s]+)', line))
        if float(row.get('started_ms', -1)) >= bounds['started_ms'] and float(row.get('ended_ms', 'inf')) <= bounds['ended_ms']:
            analysis_rows.append(row)
    costs = {}
    for name in ('gray', 'prepare', 'match', 'snapshot', 'correct', 'replay'):
        sums = [tuple(map(float, row[name].split('/'))) for row in analysis_rows]
        total = sum(row[0] for row in sums)
        count = sum(row[1] for row in sums)
        costs[name] = {'sum_ms': total, 'count': count, 'mean_ms': total / count if count else None}
    result = {'source': json.loads((folder / 'active.json').read_text()),
              'sample_seconds': (bounds['ended_ms'] - bounds['started_ms']) / 1000,
              'tracker_sample_count': len(steady), 'detector_reply_count': len(detections),
              'mean_detector_reply_interval_ms': statistics.mean(detector_gaps) if detector_gaps else None,
              'mean_inference_ms': statistics.mean(row['inference_ms'] for row in detections),
              'detected_class_ids': raw_classes, 'template_class_ids': sorted({row['class'] for row in tracks}),
              'mean_tracked_vehicles': statistics.mean(row['tracked_vehicles'] for row in steady),
              'max_tracked_vehicles': max(row['tracked_vehicles'] for row in steady),
              'prediction_fraction_of_track_observations': sum(row['predicted'] for row in tracks) / len(tracks) if tracks else None,
              'mean_ncc_successful_observations': statistics.mean(row['ncc'] for row in tracks if not row['predicted'] and row['ncc'] > 0)
                    if any(not row['predicted'] and row['ncc'] > 0 for row in tracks) else None,
              'distinct_track_ids': len({row['id'] for row in tracks}),
              'potential_duplicate_observations_iou_gt_085': potential_duplicates,
              'same_frame_high_confidence_detector_agreement': {
                  'observations': len(detector_agreement),
                  'mean_best_track_iou': statistics.mean(row['best_track_iou'] for row in detector_agreement) if detector_agreement else None,
                  'below_05': sum(row['best_track_iou'] < .5 for row in detector_agreement),
                  'below_03': sum(row['best_track_iou'] < .3 for row in detector_agreement),
                  'lowest_10': sorted(detector_agreement, key=lambda row: row['best_track_iou'])[:10]},
              'behavior_checks': json.loads((folder / 'checks.json').read_text()),
              'mean_cpu_cores': (samples[-1]['cpu_seconds'] - samples[0]['cpu_seconds']) / elapsed,
              'mean_decoder_cpu_cores': (samples[-1]['decoder_cpu_seconds'] - samples[0]['decoder_cpu_seconds']) / elapsed if decoder_measured else None,
              'mean_viewer_plus_decoder_cpu_cores': ((samples[-1]['cpu_seconds'] + samples[-1]['decoder_cpu_seconds']) -
                  (samples[0]['cpu_seconds'] + samples[0]['decoder_cpu_seconds'])) / elapsed if decoder_measured else None,
              'max_rss_mib': max(row['rss_kib'] for row in samples) / 1024,
              'max_viewer_plus_decoder_rss_mib': max(row['rss_kib'] + row['decoder_rss_kib'] for row in samples) / 1024 if decoder_measured else None,
              'display': display.summarize(windows), 'analysis_stages': costs,
              'errors': [line for line in text.splitlines() if re.search(r'FATAL|SELFTEST_FAIL|shader.*failed|QOpenGLShader.*error', line, re.I)],
              'notes': ['Track ID count and prediction fraction are diagnostics, not annotated loss or identity-switch rates.',
                        'No ground truth labels supplied; NPU detections do not establish tracker accuracy.',
                        'Same-frame IoU compares tracker output with NPU boxes scored >=0.7 before or after correction; it is a diagnostic.',
                        'Input maintains source aspect ratio inside 640x480 at 30fps.',
                        'CPU and RSS of detview exclude the ffmpeg child; combined totals are null when decoder sampling is unavailable.',
                        'Replay cost includes matching and snapshot work; stage totals are not disjoint.']}
    (folder.parent / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k not in ('display', 'source')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
