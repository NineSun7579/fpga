"""Optimize remaining real timing paths from the completed PLC database."""
import ast
import json
import shutil
import sys
import traceback
import controller as f

sys.dont_write_bytecode = True


def main():
    k, h = f.r.lock()
    original_tool = f.r.tool
    try:
        f.idle('resume_plc_route18')
        assert not (f.E/'BIT_MANIFEST.json').exists(), 'Qualified delivery already exists'
        assert not (f.E/'functional_route05').exists(), 'Never repeat this route attempt'
        failed = f.E/'DEFAULT_HOLD16_FAIL.json'
        previous = json.loads(failed.read_bytes())['result']
        assert previous['status'] != 'PASS_FUNCTIONAL_ROUTE'
        assert previous['coverage_complete'] and previous['retention_pass']
        assert previous['minima_ns']['Setup Slow'] < 0
        assert previous['minima_ns']['Hold Slow'] < 0
        plc = f.E/'functional_route04/work/place_route/v7_sdt_top_plc.adf'
        assert plc.is_file()
        plc_sha = f.r.sha(plc)
        w = f.E/'functional_candidate01'
        f.r.W = w
        hashes = json.loads((f.REBUILD/'sourcehash.json').read_bytes())
        assert hashes['count'] == 741 and hashes['registered'] == 186
        for name, digest in hashes['hashes'].items():
            assert f.r.sha(w/name) == digest, name
        graph = f.E/'functional_map_view13_native/analysis/graph.json'
        mapdb = w/'device_map/v7_sdt_top_map.adf'
        bound = json.loads((f.E/'resume_default_hold16_binding.json').read_bytes())
        assert f.r.sha(mapdb) == bound['map_sha256']
        assert f.r.sha(graph) == bound['graph_sha256']
        assert f.r.sha(w/'constraints_live/clock.fdc') == bound['clock_sha256']
        helpfile = f.r.BOARD/'build04_diagnostic_behavior_route01/help.log'
        options = ('-max_hold_violated_paths_num 30000 -fix_hold_violation_threshold 100 '
                   '-enable_route_constraint_iterate -route_constraint_iterate_times 3 '
                   '-route_constraint_slack 0 -route_constraint_max_timing_path 32')
        assert all(option.encode() in helpfile.read_bytes()
                   for option in options.split() if option.startswith('-'))
        original = f.E/'continue_functional.py'
        f.save('resume_plc_route18_binding.json', dict(
            original_sha256=f.r.sha(original), resume_sha256=f.r.sha(__file__),
            map_sha256=f.r.sha(mapdb), graph_sha256=f.r.sha(graph),
            clock_sha256=f.r.sha(w/'constraints_live/clock.fdc'),
            previous_recovery_binding_sha256=f.r.sha(f.E/'resume_default_hold16_binding.json'),
            previous_failure_sha256=f.r.sha(failed), plc=str(plc), plc_sha256=plc_sha,
            official_help_sha256=f.r.sha(helpfile), options=options,
            timing_constraints_modified=False, program=False,
            rationale='Use real PLC input required by official route-constraint iteration. Remaining C1 count_prefix setup and PCIe FIFO hold paths require physical repair; request 100ps hold repair margin without changing timing constraints.'))

        def plc_tool(label, command, work, *args, **kwargs):
            if label == 'functional_route05_pnr':
                assert f.r.sha(plc) == plc_sha
                dest = work/'placement_input'
                dest.mkdir()
                staged = dest/plc.name
                shutil.copyfile(plc, staged)
                assert f.r.sha(staged) == plc_sha
                token = '-input_db_file {'+(work/'device_map/v7_sdt_top_map.adf').as_posix()+'}'
                assert command.count(token) == 1
                command = command.replace(token, '-input_db_file {'+staged.as_posix()+'}')
                f.save('functional_route05/plc_input_binding.json', dict(
                    source=str(plc), staged=str(staged), sha256=plc_sha, command=command))
            return original_tool(label, command, work, *args, **kwargs)

        f.r.tool = plc_tool
        result = f.route(w, json.loads(graph.read_bytes()), 'functional_route05', True, options)
        assert f.r.sha(plc) == plc_sha
        if result['status'] != 'PASS_FUNCTIONAL_ROUTE':
            f.save('PLC_ROUTE18_FAIL.json', dict(result=result, bit=False, program=False,
                next='Review remaining native timing paths for targeted placement or RTL correction'))
            return
        tree = ast.parse(original.read_text('utf-8'))
        run = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
        run.body = [n for n in run.body if n.lineno == 7 or n.lineno >= 56]
        namespace = dict(__name__='plc_route18', __file__=str(original), hashes=hashes, result=result)
        exec(compile(ast.fix_missing_locations(tree), str(original), 'exec'), namespace)
        namespace['run']()
    finally:
        f.r.tool = original_tool
        k.ReleaseMutex(h)
        k.CloseHandle(h)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        f.save('RESUME_PLC_ROUTE18_FAIL.json', dict(error=repr(error),
            traceback=traceback.format_exc(), bit=False, program=False))
        raise
