"""Run native hold repair above the observed 15817-path router limit."""
import ast
import json
import sys
import traceback
import controller as f

sys.dont_write_bytecode = True

def main():
    k, h = f.r.lock()
    try:
        w = f.E/'functional_candidate01'
        f.r.W = w
        hashes = json.loads((f.REBUILD/'sourcehash.json').read_bytes())
        assert hashes['count'] == 741 and hashes['registered'] == 186
        for name, digest in hashes['hashes'].items():
            assert f.r.sha(w/name) == digest, name
        prior = json.loads((f.E/'functional_route01/RESULT.json').read_bytes())
        assert prior['retention_pass'] and prior['coverage_complete'] and prior['DDR131_25'] and not prior['old_camera_async']
        raw = (f.E/'functional_route01_pnr.log').read_bytes()
        assert b'Number of hold violated paths is 15817, over the limit 15000' in raw
        assert b'Hold Violation Fix in router takes 0 iterations' in raw
        helpfile = f.r.BOARD/'build04_diagnostic_behavior_route01/help.log'
        assert b'-max_hold_violated_paths_num integer_number' in helpfile.read_bytes()
        phasefail = json.loads((f.E/'functional_route02_pnr_receipt.json').read_bytes())
        assert phasefail['rc'] != 0 and any('Flow-0013' in e for e in phasefail['errors'])
        graph = f.E/'functional_map_view13_native/analysis/graph.json'
        mg = json.loads(graph.read_bytes())
        mapdb = w/'device_map/v7_sdt_top_map.adf'
        bound = json.loads((f.E/'resume_route14_binding.json').read_bytes())
        assert f.r.sha(mapdb) == bound['map_sha256'] and f.r.sha(graph) == bound['graph_sha256']
        recovery = json.loads((f.E/'resume_map_view13_binding.json').read_bytes())
        assert recovery['clock_sha256'] == f.r.sha(w/'constraints_live/clock.fdc')
        original = f.E/'continue_functional.py'
        options = '-gplace_seed 2 -groute_seed 2 -max_hold_violated_paths_num 30000'
        f.save('resume_hold_limit15_binding.json', dict(
            original_sha256=f.r.sha(original), resume_sha256=f.r.sha(__file__),
            map_sha256=f.r.sha(mapdb), graph_sha256=f.r.sha(graph),
            clock_sha256=f.r.sha(w/'constraints_live/clock.fdc'),
            prior_result_sha256=f.r.sha(f.E/'functional_route01/RESULT.json'),
            prior_router_log_sha256=f.r.sha(f.E/'functional_route01_pnr.log'),
            phase_failure_sha256=f.r.sha(f.E/'functional_route02_pnr_receipt.json'),
            official_help_sha256=f.r.sha(helpfile), options=options,
            rationale='Router skipped hold repair at 15817 > 15000 paths; raise documented limit to 30000. Remove PLC-only route constraint iteration from fresh MAP input.',
            timing_constraints_modified=False, program=False))
        result = f.route(w, mg, 'functional_route03', True, options)
        if result['status'] != 'PASS_FUNCTIONAL_ROUTE':
            f.save('HOLD_LIMIT15_FAIL.json', dict(result=result, bit=False, program=False,
                next='Review actual hold-repair iterations and remaining clock skew/reset removal paths'))
            return
        tree = ast.parse(original.read_text('utf-8'))
        run = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
        run.body = [n for n in run.body if n.lineno == 7 or n.lineno >= 56]
        namespace = dict(__name__='hold_limit15', __file__=str(original), hashes=hashes, result=result)
        exec(compile(ast.fix_missing_locations(tree), str(original), 'exec'), namespace)
        namespace['run']()
    finally:
        k.ReleaseMutex(h)
        k.CloseHandle(h)

if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        f.save('RESUME_HOLD_LIMIT15_FAIL.json', dict(error=repr(error), traceback=traceback.format_exc(), bit=False, program=False))
        raise
