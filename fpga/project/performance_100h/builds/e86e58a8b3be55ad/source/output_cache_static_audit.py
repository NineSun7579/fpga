"""Source audit only; does not execute or simulate Qt/RKNN or prove runtime parity."""
import argparse
import hashlib
from pathlib import Path
import re


def audit(reference):
    root = Path(__file__).resolve().parent
    original = (reference / 'main.cpp').read_bytes()
    current = (root / 'main.cpp').read_bytes()
    assert hashlib.sha256(original).hexdigest() == (
        '6d4087177ad9ba98584fef3eb076bfee4d696aa6e62375e8658d33139d9bb91c'
    ), 'reference changed: use the pinned original candidate source'
    # Compare complete unchanged regions, including every decoder and input path.
    before = original.decode('utf-8')
    after = current.decode('utf-8')
    assert before.split('        struct CachedModel {', 1)[0] == after.split('        struct CachedModel {', 1)[0]
    assert before.split('    static float sigmoidf', 1)[1] == after.split('    static float sigmoidf', 1)[1]
    input_start = '        /* Worker preprocessing has validated'
    input_end = '        resetOutputs(outs);'
    old_input = before.split(input_start, 1)[1].split('        std::vector<rknn_output> outs', 1)[0]
    new_input = after.split(input_start, 1)[1].split(input_end, 1)[0]
    assert old_input == new_input
    unchanged = 0
    for source in reference.rglob('*'):
        if source.is_file() and source.name != 'main.cpp':
            assert source.read_bytes() == (root / source.relative_to(reference)).read_bytes(), source
            unchanged += 1
    assert {p.relative_to(root) for p in root.rglob('*') if p.is_file()} == (
        {p.relative_to(reference) for p in reference.rglob('*') if p.is_file()} |
        {Path('output_cache_static_audit.py')}
    )

    worker = after.split('        struct CachedModel {', 1)[1].split('\nprivate:', 1)[0]
    frame = after.split('    bool runOnce(', 1)[1].split('    static float sigmoidf', 1)[0]
    reset = after.split('    static void resetOutputs(', 1)[1].split('    bool runOnce(', 1)[0]
    # Audit every production output-query/get/release site in this translation unit.
    assert after.count('RKNN_QUERY_OUTPUT_ATTR') == 2  # separate probe context + worker load
    assert worker.count('RKNN_QUERY_OUTPUT_ATTR') == 1
    assert 'RKNN_QUERY_OUTPUT_ATTR' not in frame
    assert 'ioNum.n_output == 0' in worker
    assert worker.index('RKNN_QUERY_IN_OUT_NUM') < worker.index('item.attrs.resize')
    assert worker.index('RKNN_QUERY_OUTPUT_ATTR') < worker.index('cache.append')
    failure = worker.split('if (queryRet != 0) {', 1)[1].split('}', 1)[0]
    assert failure.index('rknn_destroy(item.context)') < failure.index('emit modelLoaded')
    assert 'false,' in failure and 'attrsReady = false;' in failure and 'break;' in failure
    assert 'if (!attrsReady)\n                        continue;' in worker
    assert 'for (CachedModel &old : cache) rknn_destroy(old.context);\n                cache.clear();' in worker
    assert 'for (CachedModel &item : cache) rknn_destroy(item.context);\n        m_ctx = 0;' in worker
    assert 'm_ctx = item.context;' in worker and 'm_nOutput = item.outputs;' in worker
    assert 'preprocessingMs, item.attrs, item.outs)' in worker
    assert len(re.findall(r'\brunOnce\s*\(', after)) == 2  # one call, one definition
    assert 'const std::vector<rknn_tensor_attr> &attrs' in frame
    assert 'std::vector<rknn_output> &outs' in frame
    assert 'outs.resize(' not in frame and 'attrs.resize(' not in frame
    assert 'std::vector<rknn_output> outs(' not in frame
    assert after.count('rknn_outputs_get(') == 1 and after.count('rknn_outputs_release(') == 1
    assert 'memset(&outs[i], 0, sizeof(rknn_output));' in reset
    assert 'outs[i].index = static_cast<uint32_t>(i);' in reset and 'outs[i].want_float = 1;' in reset
    assert 'resetOutputs(outs);\n        if (rknn_outputs_get' in frame
    get_failure = frame.split('if (rknn_outputs_get', 1)[1].split('}', 1)[0]
    assert 'resetOutputs(outs);\n            return false;' in get_failure
    assert 'rknn_outputs_release' not in get_failure  # original failed-get policy
    assert frame.index('rknn_outputs_get') < frame.index('decodeLaneMask') < frame.index('rknn_outputs_release')
    assert 'rknn_outputs_release(m_ctx, m_nOutput, outs.data());\n        resetOutputs(outs);' in frame
    assert 'markLap(lap, tQuery)' not in frame
    assert 'tQuery = 0' in frame and 'm_accQuery += tQuery' in frame

    print('PASS source audit: pinned original; %d other source files identical;' % unchanged)
    print('unchanged lane probe/selftests, input preparation, all decoders and trailing code;')
    print('all runOnce/output API sites inspected; per-context load/failure/reload/shutdown lifecycle;')
    print('float descriptor reset before get, after failed get, after release; no per-frame query.')
    print('isolated main SHA256:', hashlib.sha256(current).hexdigest())
    print('LIMIT: no compilation, runtime fault injection, RKNN ownership verification, or output parity.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, default=Path(__file__).resolve().parents[2] / 'candidate/detview/src')
    audit(parser.parse_args().reference.resolve())
