"""Retry the setup-passing default physical strategy with native hold repair."""
import ast
import json
import sys
import traceback
import controller as f

sys.dont_write_bytecode = True


def main():
    k, h = f.r.lock()
    try:
        f.idle('resume_default_hold16')
        assert not (f.E/'BIT_MANIFEST.json').exists(), 'Qualified delivery already exists'
        assert not (f.E/'functional_route04').exists(), 'Never repeat this route attempt'
        failed = f.E/'HOLD_LIMIT15_FAIL.json'
        previous = json.loads(failed.read_bytes())['result']
        assert previous['status'] != 'PASS_FUNCTIONAL_ROUTE'
        assert previous['minima_ns']['Setup Slow'] < 0
        assert all(previous['minima_ns'][kind+' '+corner] >= 0
                   for kind in ['Hold', 'Removal'] for corner in ['Slow', 'Fast'])
        baseline = json.loads((f.E/'functional_route01/RESULT.json').read_bytes())
        assert all(baseline['minima_ns']['Setup '+corner] >= 0
                   for corner in ['Slow', 'Fast'])
        w = f.E/'functional_candidate01'
        f.r.W = w
        hashes = json.loads((f.REBUILD/'sourcehash.json').read_bytes())
        assert hashes['count'] == 741 and hashes['registered'] == 186
        for name, digest in hashes['hashes'].items():
            assert f.r.sha(w/name) == digest, name
        assert not (w/'place_route').exists() and not (w/'generate_bitstream').exists()
        graph = f.E/'functional_map_view13_native/analysis/graph.json'
        mapdb = w/'device_map/v7_sdt_top_map.adf'
        bound = json.loads((f.E/'resume_hold_limit15_binding.json').read_bytes())
        assert f.r.sha(mapdb) == bound['map_sha256']
        assert f.r.sha(graph) == bound['graph_sha256']
        assert f.r.sha(w/'constraints_live/clock.fdc') == bound['clock_sha256']
        original = f.E/'continue_functional.py'
        options = '-max_hold_violated_paths_num 30000'
        f.save('resume_default_hold16_binding.json', dict(
            original_sha256=f.r.sha(original), resume_sha256=f.r.sha(__file__),
            map_sha256=f.r.sha(mapdb), graph_sha256=f.r.sha(graph),
            clock_sha256=f.r.sha(w/'constraints_live/clock.fdc'),
            hold_recovery_binding_sha256=f.r.sha(f.E/'resume_hold_limit15_binding.json'),
            previous_failure_sha256=f.r.sha(failed),
            baseline_result_sha256=f.r.sha(f.E/'functional_route01/RESULT.json'),
            options=options, timing_constraints_modified=False, program=False,
            rationale='Seed-2 route repaired hold/removal but failed camera-1 half-cycle setup. Restore the baseline default placement/routing strategy that passed setup, retaining the documented 30000-path hold repair limit.'))
        result = f.route(w, json.loads(graph.read_bytes()), 'functional_route04', True, options)
        if result['status'] != 'PASS_FUNCTIONAL_ROUTE':
            f.save('DEFAULT_HOLD16_FAIL.json', dict(result=result, bit=False, program=False,
                next='Review remaining native setup/hold paths before targeted placement or RTL correction'))
            return
        tree = ast.parse(original.read_text('utf-8'))
        run = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
        run.body = [n for n in run.body if n.lineno == 7 or n.lineno >= 56]
        namespace = dict(__name__='default_hold16', __file__=str(original), hashes=hashes, result=result)
        exec(compile(ast.fix_missing_locations(tree), str(original), 'exec'), namespace)
        namespace['run']()
    finally:
        k.ReleaseMutex(h)
        k.CloseHandle(h)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        f.save('RESUME_DEFAULT_HOLD16_FAIL.json', dict(error=repr(error),
            traceback=traceback.format_exc(), bit=False, program=False))
        raise
