"""Compare actual [parity] JSON detection tuples; reject failed/incomplete runs."""
import argparse
import json
import math
from pathlib import Path

FIELDS = ('class', 'score', 'x1', 'y1', 'x2', 'y2')


def parse(text):
    events = [json.loads(line[len('[parity] '):]) for line in text.splitlines()
              if line.startswith('[parity] ')]
    frames = [e for e in events if e['event'] == 'frame']
    summaries = [e for e in events if e['event'] == 'summary']
    if len(summaries) != 1 or summaries[0] != dict(event='summary', requested=3, completed=3, errors=0, rc=0):
        raise ValueError('Missing successful 3-completion summary')
    if any(e['event'] == 'error' or (e['event'] == 'load' and not e['ok']) for e in events):
        raise ValueError('RKNN load/inference error')
    if len(frames) != 3:
        raise ValueError('Wrong frame count')
    for i, frame in enumerate(frames, 1):
        if frame['completion'] != i or frame['frame_id'] != i or frame['count'] != len(frame['detections']):
            raise ValueError('Invalid completion sequence or detection count')
        for det in frame['detections']:
            if set(det) != set(FIELDS) or any(not math.isfinite(det[f]) for f in FIELDS):
                raise ValueError('Invalid/nonfinite tuple')
    return frames


def match(a, b, score_tol, box_tol):
    if len(a) != len(b):
        return False
    edges = [[j for j, right in enumerate(b) if left['class'] == right['class']
              and abs(left['score'] - right['score']) <= score_tol
              and all(abs(left[f] - right[f]) <= box_tol for f in FIELDS[2:])]
             for left in a]
    assigned = {}
    def augment(i, seen):
        for j in edges[i]:
            if j in seen:
                continue
            seen.add(j)
            if j not in assigned or augment(assigned[j], seen):
                assigned[j] = i
                return True
        return False
    return all(augment(i, set()) for i in range(len(a)))


def compare(left, right, score_tol=1e-6, box_tol=1e-4):
    a, b = parse(left), parse(right)
    exact = all(match(x['detections'], y['detections'], 0, 0) for x, y in zip(a, b))
    tolerance = all(match(x['detections'], y['detections'], score_tol, box_tol) for x, y in zip(a, b))
    stable_a = all(match(a[0]['detections'], x['detections'], 0, 0) for x in a)
    stable_b = all(match(b[0]['detections'], x['detections'], 0, 0) for x in b)
    return {'exact_tuple_match': exact, 'tolerance_match': tolerance,
            'baseline_repeat_exact': stable_a, 'candidate_repeat_exact': stable_b,
            'baseline_counts': [x['count'] for x in a], 'candidate_counts': [x['count'] for x in b],
            'positive_detection_evidence': any(x['count'] for x in a + b),
            'score_absolute_tolerance': score_tol, 'coordinate_absolute_tolerance_pixels': box_tol,
            'baseline_frames': a, 'candidate_frames': b}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('candidate', type=Path)
    args = parser.parse_args()
    report = compare(args.baseline.read_text(), args.candidate.read_text())
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['tolerance_match'] else 1)
