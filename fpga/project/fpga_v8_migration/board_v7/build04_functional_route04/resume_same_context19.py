"""Place from MAP and optimize PLC in one native tool invocation."""
import ast
import json
import sys
import traceback
import controller as f

sys.dont_write_bytecode = True


def main():
    k, h = f.r.lock()
    original_tool = f.r.tool
    try:
        f.idle('resume_same_context19')
        assert not (f.E/'BIT_MANIFEST.json').exists()
        assert not (f.E/'functional_route06').exists()
        failed = f.E/'PLC_ROUTE18_FAIL.json'
        previous = json.loads(failed.read_bytes())['result']
        assert previous['timing_pass'] and previous['coverage_complete']
        assert not previous['retention_pass']
        io = json.loads((f.E/'functional_route05/native_IO112_comparison.json').read_bytes())
        assert io['ports'] == 112 and io['differences']
        assert all(row['field'] == 'BANK' and row['fresh'] == 'BANKL6' for row in io['differences'])
        baseline_io = json.loads((f.E/'functional_route04/native_IO112_comparison.json').read_bytes())
        assert baseline_io['table_bytes_equal'] and not baseline_io['differences']
        w = f.E/'functional_candidate01'
        f.r.W = w
        hashes = json.loads((f.REBUILD/'sourcehash.json').read_bytes())
        assert hashes['count'] == 741 and hashes['registered'] == 186
        for name, digest in hashes['hashes'].items():
            assert f.r.sha(w/name) == digest, name
        graph = f.E/'functional_map_view13_native/analysis/graph.json'
        mapdb = w/'device_map/v7_sdt_top_map.adf'
        bound = json.loads((f.E/'resume_plc_route18_binding.json').read_bytes())
        assert f.r.sha(mapdb) == bound['map_sha256']
        assert f.r.sha(graph) == bound['graph_sha256']
        assert f.r.sha(w/'constraints_live/clock.fdc') == bound['clock_sha256']
        options = bound['options']
        original = f.E/'continue_functional.py'
        f.save('resume_same_context19_binding.json', dict(
            original_sha256=f.r.sha(original), resume_sha256=f.r.sha(__file__),
            map_sha256=f.r.sha(mapdb), graph_sha256=f.r.sha(graph),
            clock_sha256=f.r.sha(w/'constraints_live/clock.fdc'),
            previous_failure_sha256=f.r.sha(failed),
            previous_recovery_binding_sha256=f.r.sha(f.E/'resume_plc_route18_binding.json'),
            failed_io_sha256=f.r.sha(f.E/'functional_route05/native_IO112_comparison.json'),
            options=options, timing_constraints_modified=False, program=False,
            rationale='All route05 timing and crossing checks pass, but occupied IO banks become BANKL6 after PLC reload. Regenerate placement from MAP and optimize that PLC within one official invocation; retain full native IO acceptance.'))

        def same_context_tool(label, command, work, *args, **kwargs):
            if label == 'functional_route06_pnr':
                mapped = work/'device_map/v7_sdt_top_map.adf'
                plc = work/'place_route/v7_sdt_top_plc.adf'
                token = '-input_db_file {'+mapped.as_posix()+'}'
                assert command.count(token) == 1
                prefix, route = command.split('pnr -force_to_run', 1)
                place = ('pnr -force_to_run -input_db_file {'+mapped.as_posix()+
                         '} -place_only -optimize_multi_corner_timing\n')
                route = ('pnr -force_to_run'+route).replace(token,
                            '-input_db_file {'+plc.as_posix()+'}')
                command = prefix+place+route
                f.save('functional_route06/same_context_command.json', dict(
                    map=str(mapped), map_sha256=f.r.sha(mapped),
                    generated_plc=str(plc), command=command, one_tool_invocation=True))
            return original_tool(label, command, work, *args, **kwargs)

        f.r.tool = same_context_tool
        result = f.route(w, json.loads(graph.read_bytes()), 'functional_route06', True, options)
        if result['status'] != 'PASS_FUNCTIONAL_ROUTE':
            f.save('SAME_CONTEXT19_FAIL.json', dict(result=result, bit=False, program=False,
                next='Review native IO and timing from same-context placement/routing'))
            return
        tree = ast.parse(original.read_text('utf-8'))
        run = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
        run.body = [n for n in run.body if n.lineno == 7 or n.lineno >= 56]
        namespace = dict(__name__='same_context19', __file__=str(original), hashes=hashes, result=result)
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
        f.save('RESUME_SAME_CONTEXT19_FAIL.json', dict(error=repr(error),
            traceback=traceback.format_exc(), bit=False, program=False))
        raise
