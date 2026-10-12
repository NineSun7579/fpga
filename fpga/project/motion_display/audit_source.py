"""Offline byte audit of the isolated viewer; never contacts the board."""
import difflib
import hashlib
import json
from pathlib import Path


def main():
    here = Path(__file__).resolve().parent
    original = here.parent / 'motion_scheduling' / 'host' / 'src'
    candidate = here / 'host' / 'src'
    source = {p.relative_to(original).as_posix(): p.read_bytes()
              for p in original.rglob('*') if p.is_file()}
    copied = {p.relative_to(candidate).as_posix(): p.read_bytes()
              for p in candidate.rglob('*') if p.is_file()}
    assert source.keys() <= copied.keys(), 'missing original file'
    changed = sorted(n for n in source if source[n] != copied[n])
    assert changed == ['detview.pro', 'main.cpp'], changed
    a, b = source['main.cpp'], copied['main.cpp']
    for start, end in [
        (b'class CameraWorker :', b'class DetView :'),
        (b'class DetViewController :', b'int main('),
        (b'    void drawOverlay(', b'    void recordPaint('),
        (b'        // Clear the previous frame', b'    void uploadOverlay('),
    ]:
        assert a[a.index(start):a.index(end)] == b[b.index(start):b.index(end)], start
    # main.cpp only adds the helper/opt-in branch/storage/entry point/logging;
    # every baseline line remains byte-identical and in the original order.
    matcher = difflib.SequenceMatcher(None, a.splitlines(True), b.splitlines(True), autojunk=False)
    assert all(op in ('equal', 'insert') for op, *_ in matcher.get_opcodes()), 'baseline code modified'
    assert source['detview.pro'] in copied['detview.pro']
    diff = b''.join(difflib.diff_bytes(difflib.unified_diff, a.splitlines(True), b.splitlines(True),
                                     fromfile=b'motion_scheduling/main.cpp', tofile=b'motion_display/main.cpp'))
    (here / 'source_changes.patch').write_bytes(diff)
    digest = lambda data: hashlib.sha256(data).hexdigest()
    report = {
        'baseline': str(original), 'candidate': str(candidate),
        'baseline_file_count': len(source), 'candidate_file_count': len(copied),
        'changed_existing_files': changed,
        'added_files': sorted(copied.keys() - source.keys()),
        'unchanged_existing_files': sorted(n for n in source if source[n] == copied[n]),
        'camera_and_inference_class_bytes_identical': True,
        'controller_scheduling_stereo_bytes_identical': True,
        'overlay_draw_scissors_bytes_identical': True,
        'raster_clear_paint_and_upload_invocation_bytes_identical': True,
        'baseline_sha256': {n: digest(data) for n, data in source.items()},
        'candidate_sha256': {n: digest(data) for n, data in copied.items()},
    }
    (here / 'source_audit.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('SOURCE_AUDIT_PASS', len(source), 'baseline files;', len(copied), 'candidate files;', changed)


if __name__ == '__main__':
    main()
