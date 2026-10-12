"""Read-only semantic/copy/frozen-input audit; write report only in this candidate."""
from pathlib import Path
import difflib
import hashlib
import json
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    manifest = json.loads((HERE / 'manifest.json').read_text())
    frozen = json.loads((HERE / 'frozen_inputs_sha256.json').read_text())
    for name, digest in frozen.items(): assert sha(ROOT / name) == digest, name
    base = ROOT / manifest['baseline']
    src = HERE / 'src'
    unchanged = []
    for name, digest in manifest['originals'].items():
        assert sha(base / name) == digest
        if name != 'main.cpp':
            assert sha(src / name) == digest, name
            unchanged.append(name)
    for name, digest in manifest['byteexact_old_headers'].items():
        assert sha(src / name) == digest
        assert sha(ROOT / 'viewer_native_candidate/src' / name) == digest
    old, new = (base / 'main.cpp').read_bytes(), (src / 'main.cpp').read_bytes()
    def section(data, start, end):
        return data[data.index(start):data.index(end, data.index(start))]
    decoder = section(new, b'    static float sigmoidf', b'    QMutex m_mutex;')
    assert decoder == section(old, b'    static float sigmoidf', b'    QMutex m_mutex;')
    assert decoder == (HERE / 'current_retained_decoder.inc').read_bytes()
    assert sha(HERE / 'current_retained_decoder.inc') == manifest['decoder_binding_sha256']
    # Preserve actual feed selection, input override, memcpy, inputs_set/run.
    assert section(old, b'        // The square producer contract', b'        std::vector<rknn_output> outs') == section(new, b'        // The square producer contract', b'        std::vector<rknn_output> outs')
    # Emissions, geometry/class labels, epoch/metrics behavior remain unchanged.
    assert section(old, b'        if (bench) markLap(lap, tRel);', b'    static float sigmoidf') == section(new, b'        if (bench) markLap(lap, tRel);', b'    static float sigmoidf')
    assert b'const std::vector<rknn_tensor_attr> &attrs = *m_outputAttrs;' in new
    assert new.count(b'RKNN_QUERY_OUTPUT_ATTR') == old.count(b'RKNN_QUERY_OUTPUT_ATTR')
    assert b'RKNN_QUERY_OUTPUT_ATTR' not in (src / 'current_native_qt.hpp').read_bytes()
    assert b'RKNN_QUERY_INPUT_ATTR' not in (src / 'current_native_qt.hpp').read_bytes()
    assert b'std::vector<CachedModel> cache;' in new
    assert b'cache.push_back' in new and b'cache.append' not in new
    assert new.index(b'm_nativeSession = nullptr;', new.index(b'if (reload)')) < new.index(b'rknn_destroy(old.context)')
    assert new.index(b'm_outputAttrs = nullptr;', new.index(b'if (reload)')) < new.index(b'rknn_destroy(old.context)')
    assert new.count(b'tdm::restoreCanonicalDetections(dets, m_geometry);') == old.count(b'tdm::restoreCanonicalDetections(dets, m_geometry);') + 1
    # Release happens once only after successful get and before completed count.
    run = section(new, b'    bool runOnce(', b'    static float sigmoidf')
    assert run.count(b'OutputLease outputLease') == 1
    assert run.count(b'outputLease.finish()') == 1
    assert run.index(b'outputs_release failed') < run.index(b'++m_completed')
    assert run.index(b'native decode failed') < run.index(b'++m_completed')
    assert b'outs[i].want_float = nativeDecode ? 0 : 1;' in run
    diff = ''.join(difflib.unified_diff(old.decode().splitlines(True), new.decode().splitlines(True),
             fromfile='frozen/current/main.cpp', tofile='candidate/src/main.cpp'))
    for name in ['current_native_gate.hpp', 'current_native_qt.hpp']:
        diff += ''.join(difflib.unified_diff([], (src / name).read_text().splitlines(True),
                    fromfile='/dev/null', tofile='candidate/src/' + name))
    (HERE / 'patch.diff').write_text(diff, encoding='utf-8')
    report = {'pass': True, 'frozen_files_verified': len(frozen),
              'original_authored_files': 35, 'unchanged_authored_files': unchanged,
              'production_decoder_byteexact': True, 'input_pipeline_byteexact': True,
              'completion_emission_tail_byteexact': True,
              'headers_byteexact': manifest['byteexact_old_headers'],
              'candidate_source_sha256': {str(p.relative_to(src)): sha(p) for p in src.rglob('*') if p.is_file()},
              'full_viewer_compiled': False, 'device_accessed': False}
    (HERE / 'audit_results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('AUDIT_PASS', len(unchanged), 'unchanged originals; decoder/input pipeline byteexact;', len(frozen), 'frozen inputs unchanged')
if __name__ == '__main__': main()
