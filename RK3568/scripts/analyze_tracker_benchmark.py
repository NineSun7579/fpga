#!/usr/bin/env python3
"""Compare matching workloads with identical seeds/canvases and live counts."""
import argparse
import json
from pathlib import Path
import re


def read_run(path):
    text = path.read_text(encoding='utf-8', errors='replace')
    if 'TRACKER_BENCHMARK_PASS' not in text or 'TRACKER_BENCHMARK_FAIL' in text:
        raise ValueError(f'{path}: benchmark did not pass')
    cases = {}
    for line in text.splitlines():
        fields = dict(re.findall(r'(\w+)=([^\s]+)', line))
        if line.startswith('[tracker-benchmark-case]'):
            key = (fields['size'], int(fields['requested']))
            for name in ('live_min', 'live_max', 'matched_min', 'matched_max'):
                if int(fields[name]) != key[1]:
                    raise ValueError(f'{path}: {key} population mismatch')
            cases[key] = {'case': fields, 'cost': {}}
        elif line.startswith('[tracker-benchmark-cost]'):
            key = (fields['size'], int(fields['requested']))
            cases[key]['cost'][fields['operation']] = {
                name: float(fields[name]) for name in ('samples', 'mean_ms', 'max_ms')}
    if len(cases) != 9:
        raise ValueError(f'{path}: expected nine cases')
    return cases


def compare(reference, candidate):
    if set(reference) != set(candidate):
        raise ValueError('Case sets differ')
    result = []
    for key, old in reference.items():
        new = candidate[key]
        for field in ('seed', 'canvas', 'box', 'scale', 'measured_cycles', 'history_frames'):
            if old['case'][field] != new['case'][field]:
                raise ValueError(f'{key}: changed comparison condition {field}')
        if set(old['cost']) != set(new['cost']):
            raise ValueError(f'{key}: operation sets differ')
        operations = {}
        for name, before in old['cost'].items():
            after = new['cost'][name]
            if before['samples'] != after['samples']:
                raise ValueError(f'{key}: sample count differs for {name}')
            operations[name] = {'reference_mean_ms': before['mean_ms'],
                                'bounded_mean_ms': after['mean_ms'],
                                'ratio': after['mean_ms'] / before['mean_ms'] if before['mean_ms'] else None,
                                'reference_max_ms': before['max_ms'], 'bounded_max_ms': after['max_ms']}
        result.append({'size': key[0], 'targets': key[1], 'canvas': old['case']['canvas'],
                       'box': old['case']['box'], 'operations': operations})
    return {'cases': result,
            'notes': ['Synthetic compute workload; physical vehicle accuracy is unmeasured.',
                      'Large canvases are algorithm stress inputs, not 640x480 whole-system frame rates.',
                      'Compare repeated runs before attributing small changes to the cap.']}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('reference', type=Path)
    cli.add_argument('bounded', type=Path)
    cli.add_argument('output', type=Path)
    args = cli.parse_args()
    result = compare(read_run(args.reference), read_run(args.bounded))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    for case in result['cases']:
        operation = case['operations']['update']
        print(f"{case['targets']:2} {case['size']:6} {case['canvas']:10} update "
              f"{operation['reference_mean_ms']:.3f} -> {operation['bounded_mean_ms']:.3f}ms "
              f"ratio={operation['ratio']:.3f}")


if __name__ == '__main__':
    main()
