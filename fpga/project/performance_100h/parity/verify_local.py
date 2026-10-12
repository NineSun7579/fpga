"""Local artifact/matcher checks only; never imports board tooling."""
import hashlib
import json
from pathlib import Path
from compare import compare

HERE = Path(__file__).resolve().parent


def log(dets, errors=0):
    events = [dict(event='frame', completion=i, frame_id=i, count=len(dets), detections=dets)
              for i in range(1, 4)]
    events.append(dict(event='summary', requested=3, completed=3, errors=errors, rc=0))
    return '\n'.join('[parity] ' + json.dumps(e) for e in events)


def main():
    checks = []
    for path in HERE.glob('*.py'):
        compile(path.read_bytes(), str(path), 'exec')
    checks.append('Python syntax valid')
    d = dict(zip(('class', 'score', 'x1', 'y1', 'x2', 'y2'), (1, 0.9, 10, 20, 30, 40)))
    e = dict(d, x1=50, x2=60)
    assert compare(log([d, e]), log([e, d]))['exact_tuple_match']
    checks.append('Permutation-independent exact matching')
    result = compare(log([d]), log([dict(d, score=0.9000005)]))
    assert result['tolerance_match'] and not result['exact_tuple_match']
    checks.append('Score tolerance distinguished from exact equality')
    assert not compare(log([d]), log([dict(d, x1=11)]))['tolerance_match']
    assert not compare(log([d]), log([dict(d, **{'class': 2})]))['tolerance_match']
    assert not compare(log([d, e]), log([d]))['tolerance_match']
    checks.append('Coordinate/class/count mismatches rejected')
    assert not compare(log([]), log([]))['positive_detection_evidence']
    checks.append('Empty-only result carries no positive evidence')
    try:
        compare(log([d], errors=1), log([d]))
    except ValueError:
        checks.append('Failed summary rejected')
    else:
        raise AssertionError('Failed summary accepted')
    manifest = json.loads((HERE / 'manifest.json').read_text())
    for harness in manifest['harnesses'].values():
        src = HERE / harness['source']
        actual = {p.relative_to(src).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted(src.rglob('*')) if p.is_file()}
        assert actual == harness['source_sha256']
        assert [name for name in actual if actual[name] != harness['original_source_sha256'].get(name)] == ['main.cpp']
        text = (src / 'main.cpp').read_bytes()
        assert text.index(b'const int parityTest') < text.index(b'const int videoArg')
    checks.append('Harnesses match manifest; only main.cpp differs; branch before controller flow')
    result = dict(status='local_checks_passed', checks=checks,
                  board_connected=False, build_executed=False, rknn_executed=False)
    (HERE / 'verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
