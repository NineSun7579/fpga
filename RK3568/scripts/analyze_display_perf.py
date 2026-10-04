#!/usr/bin/env python3
"""Aggregate complete detview display-perf windows; keep per-window quantiles.

Usage: python analyze_display_perf.py run.log [summary.json]
Quantiles cannot be merged from quantile values. This script reports each
window's bucket bounds and aggregates only exact counts and duration sums.
"""
import json
import argparse
from pathlib import Path
import re


def parse(text):
    windows = []
    current = None
    for line in text.splitlines():
        fields = dict(re.findall(r'(\w+)=([^\s]+)', line))
        if line.startswith('[display-perf]'):
            current = {'metrics': {k: float(v) for k, v in fields.items()}, 'events': {}, 'stages': {}, 'cameras': {}}
            windows.append(current)
        elif current is not None and line.startswith('[display-events]'):
            current['events'] = {k: int(v) for k, v in fields.items()}
        elif current is not None and line.startswith('[display-stage]'):
            name = fields.pop('name')
            current['stages'][name] = {k: float(v) for k, v in fields.items()}
        elif current is not None and line.startswith('[display-upload]'):
            camera = fields.pop('camera')
            current['cameras'][camera] = {k: int(v) for k, v in fields.items()}
    return windows


def summarize(windows):
    complete = [w for w in windows if len(w['stages']) == 11 and len(w['cameras']) == 6 and len(w['events']) == 4]
    if not complete:
        raise ValueError('No complete display-perf windows; enable DETVIEW_PERF and sample for at least 5 seconds')
    seconds = sum(w['metrics']['seconds'] for w in complete)
    events = {k: sum(w['events'][k] for w in complete) for k in complete[0]['events']}
    stages = {}
    for name in complete[0]['stages']:
        rows = [w['stages'][name] for w in complete]
        count = sum(r['count'] for r in rows)
        total = sum(r['sum_ms'] for r in rows)
        stages[name] = {'count': int(count), 'sum_ms': round(total, 3),
                        'mean_ms': round(total / count, 3) if count else 0,
                        'max_ms': max(r['max_ms'] for r in rows),
                        'overflow': int(sum(r['overflow'] for r in rows))}
    stage_names = ['camera_upload', 'hud_regions', 'hud_raster', 'hud_pack', 'hud_upload', 'camera_draw', 'hud_draw']
    total_paint = stages['paint_total']['sum_ms'] + stages['settings_paint']['sum_ms']
    measured = sum(stages[n]['sum_ms'] for n in stage_names)
    return {'complete_windows': len(complete), 'discarded_windows': len(windows) - len(complete),
            'seconds': round(seconds, 3), 'events': events,
            'rates': {k: round(v / seconds, 3) for k, v in events.items()},
            'stages': stages, 'unclassified_paint_ms': round(total_paint - measured, 3),
            'work': {k: sum(w['metrics'].get(k, 0) for w in complete) for k in
                     ['replaced_snapshots', 'hud_rebuilds', 'revision', 'periodic', 'expired', 'layout',
                      'upload_rects', 'upload_bytes', 'draw_rects', 'text_hits', 'text_misses', 'text_clears']},
            'windows': complete,
            'notes': ['CPU wall-clock timings include GL call waits, not GPU execution durations.',
                      'Quantiles are per-window bucket upper bounds; overflow bucket starts at 127.5ms and returns the window maximum.',
                      'Camera upload/paint/swap rates are distinct; swap does not measure physical scanout.',
                      'Use separate monitor/settings sampling windows for fair comparisons.']}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('log', type=Path)
    cli.add_argument('output', nargs='?', type=Path)
    cli.add_argument('--window', type=Path, help='Keep only complete windows contained in started_ms/ended_ms JSON')
    args = cli.parse_args()
    source = args.log
    output = args.output or source.with_suffix('.perf.json')
    windows = parse(source.read_text(encoding='utf-8', errors='replace'))
    if args.window:
        selected = json.loads(args.window.read_text(encoding='utf-8'))
        windows = [w for w in windows if w['metrics'].get('started_ms', -1) >= selected['started_ms'] and
                   w['metrics'].get('ended_ms', float('inf')) <= selected['ended_ms']]
    result = summarize(windows)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'windows'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
