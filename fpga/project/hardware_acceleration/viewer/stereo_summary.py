"""Validate timestamped stereo computation windows against an accepted counter interval."""
import re

PATTERN = re.compile(r'^\[stereo\] window=\[(\d+),(\d+)\) window_ms=5000 C(\d+)/C(\d+) '
                     r'pair_compute_ok=(\d+) pair_compute_failed=(\d+) .*?compute_mean_ms=([0-9.]+) '
                     r'compute_max_ms=([0-9.]+)', re.MULTILINE)


def stereo_records(text, pairs):
    expected = {tuple(pair) for pair in pairs}
    if not expected or len(expected) != len(pairs):
        raise ValueError('Distinct configured stereo pairs required')
    result = {pair: [] for pair in expected}
    for values in PATTERN.findall(text):
        begin, end, left, right, ok, failed = map(int, values[:6])
        pair = (left, right)
        if pair not in expected or end - begin != 5000:
            raise ValueError('Stereo log has an unexpected pair or window duration')
        result[pair].append(dict(begin_ns=begin * 1000000, end_ns=end * 1000000,
                                 completed=ok, failed=failed, mean_ms=float(values[6]), max_ms=float(values[7])))
    if any(not windows for windows in result.values()):
        raise ValueError('A configured stereo pair has no window records')
    return result


def latest_stereo_endpoint(text, pairs):
    records = stereo_records(text, pairs)
    return min(max(row['end_ns'] for row in windows) for windows in records.values())


def validate_stereo(text, pairs, begin_ns, end_ns):
    if int(end_ns) <= int(begin_ns):
        raise ValueError('Invalid stereo interval')
    results = []
    for pair, windows in sorted(stereo_records(text, pairs).items()):
        selected = [row for row in windows if row['end_ns'] > begin_ns and row['begin_ns'] < end_ns]
        if not selected or selected[0]['begin_ns'] > begin_ns or selected[-1]['end_ns'] < end_ns:
            raise ValueError('Stereo windows do not cover the accepted interval')
        for i, row in enumerate(selected):
            if i and selected[i-1]['end_ns'] != row['begin_ns']:
                raise ValueError('Missing, overlapping or reordered stereo windows')
            if not row['completed'] or row['failed']:
                raise ValueError('Stereo stopped or failed within an accepted window')
        total = sum(row['completed'] for row in selected)
        results.append(dict(pair=list(pair), covering_windows=selected, completed_in_covering_windows=total,
                            failed_in_covering_windows=0,
                            weighted_compute_mean_ms=sum(row['completed'] * row['mean_ms'] for row in selected)/total,
                            max_compute_ms=max(row['max_ms'] for row in selected)))
    return dict(status='all_configured_pairs_continuous_success', accepted_begin_ns=int(begin_ns),
                accepted_end_ns=int(end_ns), pairs=results,
                count_scope='Covering five-second windows can include up to five seconds beyond either counter endpoint.')
