"""Local immutable-input copy and byte-based minimal main integration. No remote calls."""
from pathlib import Path
import hashlib
import json
import difflib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASE = ROOT / 'current_viewer_binding_02/inputs/userdata/linaro/detview-driving-demo-src'
OLD = ROOT / 'viewer_native_candidate'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    src = HERE / 'src'
    assert not (src / 'main.cpp').exists(), 'refuse to overwrite prepared sources'
    frozen = {str(p.relative_to(ROOT)): sha(p) for folder in
              [ROOT / 'current_viewer_binding_02/inputs', ROOT / 'current_viewer_rebuild_02']
              for p in folder.rglob('*') if p.is_file()}
    originals = sorted(p for p in BASE.rglob('*') if p.suffix in ('.cpp', '.h', '.pro')
                       and not p.name.startswith('moc_'))
    assert len(originals) == 35, len(originals)
    for p in originals:
        dest = src / p.relative_to(BASE)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(p.read_bytes())
    headers = ['raw_dfl_native.h', 'viewer_native_guard.hpp', 'viewer_native_qt.hpp']
    for name in headers: (src / name).write_bytes((OLD / 'src' / name).read_bytes())
    for name in ['native_guard_selftest.cpp', 'build_native_guard_selftest.cmd']:
        (HERE / name).write_bytes((OLD / name).read_bytes())
    (HERE / 'recorded_profile.txt').write_bytes((OLD / 'artifacts/recorded_profile.txt').read_bytes())
    (HERE / 'current_retained_decoder.inc').write_bytes((ROOT / 'current_viewer_binding_02/current_retained_decoder.inc').read_bytes())
    original = (src / 'main.cpp').read_bytes()
    data = original
    def replace(a, b):
        nonlocal data
        a, b = a.encode(), b.encode()
        assert data.count(a) == 1, a
        data = data.replace(a, b)
    replace('#include "rknn_api.h"', '#include "rknn_api.h"\n#include "current_native_qt.hpp"')
    replace('            std::vector<rknn_tensor_attr> outputAttrs;','            std::vector<rknn_tensor_attr> outputAttrs;\n            viewer_native::Session native;')
    replace('        QVector<CachedModel> cache;', '        std::vector<CachedModel> cache;')
    replace('            if (reload) {\n                for (CachedModel &old : cache)',
            '            if (reload) {\n                m_nativeSession = nullptr;\n                m_outputAttrs = nullptr;\n                m_ctx = 0;\n                for (CachedModel &old : cache)')
    replace('                    cache.append(std::move(item));', '''                    item.native = viewer_native::prepare_current(item.context, item.bytes, info.path,
                        ioNum.n_input, item.outputs, info.nc, info.lane, info.trafficlight,
                        item.geometry.width, item.geometry.height, inputAttr, item.outputAttrs,
                        ++m_nativeContextSerial);
                    cache.push_back(std::move(item));''')
    replace('cache.last().geometry.height', 'cache.back().geometry.height')
    replace('!cache.isEmpty()', '!cache.empty()')
    replace('next = (next + 1) % cache.size();', 'next = (next + 1) % static_cast<int>(cache.size());')
    replace('                m_ctx = item.context;', '                m_ctx = item.context;\n                m_nativeSession = &item.native;')
    replace('        for (CachedModel &item : cache) rknn_destroy(item.context);',
            '        m_nativeSession = nullptr;\n        m_outputAttrs = nullptr;\n        m_ctx = 0;\n        for (CachedModel &item : cache) rknn_destroy(item.context);')
    # Reuse old integration blocks, with current geometry guard and cached attrs.
    oldmain = (OLD / 'src/main.cpp').read_bytes()
    start = oldmain.index(b'        bool nativeDecode =')
    stop = oldmain.index(b'        QElapsedTimer lap;', start)
    setup = oldmain[start:stop].decode()
    setup = setup.replace('if (int8In || m_lane || m_nc != 3 || m_nOutput != 6)',
        'if (!viewer_native::current_geometry_gate(m_trafficlight, m_geometry.width, m_geometry.height, 3) ||\n                    qEnvironmentVariableIsSet("DET_INT8_IN") || m_lane || m_nc != 3 || m_nOutput != 6)')
    replace('        QElapsedTimer lap;\n        double tPrep', setup + '        QElapsedTimer lap;\n        double tPrep')
    replace('            outs[i].want_float = 1;', '            outs[i].want_float = nativeDecode ? 0 : 1;')
    replace('        if (bench) markLap(lap, tGet);',
            '        viewer_native::OutputLease outputLease(m_ctx, outs, &rknn_outputs_release);\n        if (bench) markLap(lap, tGet);')
    start = oldmain.index(b'        if (nativeDecode) {', oldmain.index(b'        QImage laneMask;', stop))
    stop = oldmain.index(b'            laneMask = decodeLaneMask', start)
    native = oldmain[start:stop].decode()
    # Canonical restoration remains the existing production call, for both paths.
    native = native.replace('        } else if (m_lane)\n',
        '            tdm::restoreCanonicalDetections(dets, m_geometry);\n        } else if (m_lane)\n')
    replace('        if (m_lane)\n            laneMask = decodeLaneMask(outs[0], attrs[0], m_nc);',
        native + '            laneMask = decodeLaneMask(outs[0], attrs[0], m_nc);')
    replace('        rknn_outputs_release(m_ctx, m_nOutput, outs.data());', '''        const int releaseRet = outputLease.finish();
        if (nativeDecode && releaseRet != RKNN_SUCC) {
            fprintf(stderr, "[v8-native-candidate] outputs_release failed ret=%d\\n", releaseRet);
            return false;
        }''')
    replace('    uint32_t m_nOutput = 0;', '''    uint32_t m_nOutput = 0;
    viewer_native::Session* m_nativeSession = nullptr; // Bound only after cache growth finishes.
    quint64 m_nativeContextSerial = 0;''')
    (src / 'main.cpp').write_bytes(data)
    (HERE / 'patch.diff').write_text(''.join(difflib.unified_diff(
        original.decode().splitlines(True), data.decode().splitlines(True),
        fromfile='frozen/current/main.cpp', tofile='candidate/src/main.cpp')), encoding='utf-8')
    manifest = {'baseline': str(BASE.relative_to(ROOT)),
        'originals': {str(p.relative_to(BASE)): sha(p) for p in originals},
        'byteexact_old_headers': {n: sha(OLD / 'src' / n) for n in headers},
        'executable_sha256': sha(ROOT / 'current_viewer_binding_02/inputs/userdata/detview-driving-demo/detview-driving-demo'),
        'decoder_binding_sha256': sha(HERE / 'current_retained_decoder.inc')}
    assert manifest['executable_sha256'] == 'f1fd98042a6f87c410cc44fbff574fc01f42e63a3f08827574cff3e51b6433b4'
    (HERE / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (HERE / 'frozen_inputs_sha256.json').write_text(json.dumps(frozen, indent=2)+'\n')
    print('Prepared 35 authored inputs and byteexact old headers, local only')
if __name__ == '__main__': main()
