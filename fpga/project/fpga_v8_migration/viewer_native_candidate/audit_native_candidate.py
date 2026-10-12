"""Frozen-byte audit and review manifest. Writes only beneath this directory."""
from pathlib import Path
import difflib
import hashlib
import json

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'viewer_build_recovered' / 'inputs'
SRC = HERE / 'src'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def audit():
    frozen = json.loads((HERE / 'frozen_inputs_sha256.json').read_text())
    current = {str(p.relative_to(BASE)): sha(p) for p in BASE.rglob('*') if p.is_file()}
    assert current == frozen and len(current) == 61, 'immutable recovered inputs changed'
    copied = json.loads((HERE / 'copied_sources.json').read_text())
    changed = [name for name in copied['source_files'] if sha(SRC / name) != frozen[name]]
    assert changed == ['main.cpp'], changed
    assert sha(SRC / 'raw_dfl_native.h') == copied['native_decoder_sha256']
    assert sha(SRC / 'rknn_api.h') == copied['rknn_api_sha256']
    assert not any(p.suffix in ('.o', '.obj', '.exe', '.moc') or p.name.startswith('moc_') or
                   p.name in ('detview', 'Makefile') for p in SRC.rglob('*') if p.is_file())
    original = (BASE / 'main.cpp').read_bytes()
    candidate = (SRC / 'main.cpp').read_bytes()
    decoder = HERE.parent / 'board' / 'board_production_decoder.inc'
    assert len(decoder.read_bytes()) == 11102
    assert sha(decoder) == 'bf268b78139e0489fe00ed5b7f0ef5e6a59fbc49d02b8424a6e5d63369e19700'
    assert decoder.read_bytes() in original and decoder.read_bytes() in candidate
    # Everything after the unchanged production decoder through CLI/display end
    # is byte-exact except the two explicit native state declarations.
    start = original.index(decoder.read_bytes())
    native_start = candidate.index(decoder.read_bytes())
    tail = candidate[native_start:].replace(
        b'    viewer_native::Session* m_nativeSession = nullptr; // Inference-thread-owned cache entry.\n'
        b'    quint64 m_nativeContextSerial = 0;\n', b'', 1)
    assert tail == original[start:], 'decoder/display/motion/CLI code changed'
    diff_lines = list(difflib.unified_diff(original.decode('utf-8').splitlines(keepends=True),
                                         candidate.decode('utf-8').splitlines(keepends=True),
                                         fromfile='frozen/inputs/main.cpp', tofile='candidate/src/main.cpp'))
    diff = ''.join(diff_lines)
    (HERE / 'patch.diff').write_text(diff, encoding='utf-8', newline='')
    sources = {str(p.relative_to(SRC)): {'bytes': p.stat().st_size, 'sha256': sha(p),
               'frozen_sha256': frozen.get(str(p.relative_to(SRC)))}
               for p in sorted(SRC.rglob('*')) if p.is_file()}
    report = dict(status='PREPARED_SOURCE_ONLY_NOT_DEPLOYED', deployed=False,
                  frozen_files_checked=len(frozen), copied_compiler_inputs=len(copied['source_files']),
                  changed_existing_files=changed, candidate_source_files=len(sources),
                  production_decoder_bytes=11102, production_decoder_sha256=sha(decoder),
                  production_decoder_exact_in_both=True, unchanged_decoder_display_motion_cli_tail=True,
                  source_files=sources, main_diff_sha256=sha(HERE / 'patch.diff'),
                  diff_added_lines=sum(l.startswith('+') and not l.startswith('+++') for l in diff_lines),
                  diff_removed_lines=sum(l.startswith('-') and not l.startswith('---') for l in diff_lines),
                  pending_validation=['complete RK3568 viewer build/link', 'actual candidate runtime/head measurement',
                                      'candidate viewer semantic/failure validation'],
                  prohibited_actions_performed=[])
    (HERE / 'candidate_manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    return report

if __name__ == '__main__':
    r = audit()
    print(json.dumps({k: r[k] for k in ('status', 'deployed', 'frozen_files_checked',
                     'changed_existing_files', 'candidate_source_files', 'diff_added_lines', 'diff_removed_lines')}, indent=2))
