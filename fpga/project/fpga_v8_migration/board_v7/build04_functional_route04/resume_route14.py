"""Continue successful map13 from its exact native graph; preserve path failure."""
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
        hashes = json.loads((f.REBUILD/'sourcehash.json').read_bytes())
        assert hashes['count'] == 741 and hashes['registered'] == 186
        for name, digest in hashes['hashes'].items():
            assert f.r.sha(w/name) == digest, name
        for label in ['functional_map_view13', 'functional_map_view13_native_export']:
            receipt = json.loads((f.E/(label+'_receipt.json')).read_bytes())
            assert receipt['rc'] == 0 and not receipt['errors']
            assert f.r.sha(f.E/(label+'.log')) == receipt['log_sha256']
        parser = json.loads((f.E/'functional_map_view13_native_parser_receipt.json').read_bytes())
        db = w/'device_map/v7_sdt_top_map.adf'
        assert parser['rc'] == 0 and parser['adf_sha256'] == f.r.sha(db)
        recovery = json.loads((f.E/'resume_map_view13_binding.json').read_bytes())
        assert recovery['clock_sha256'] == f.r.sha(w/'constraints_live/clock.fdc')
        assert recovery['synthesis_sha256'] == f.r.sha(w/'synthesize/v7_sdt_top_syn.adf')
        graph = f.E/'functional_map_view13_native/analysis/graph.json'
        mg = json.loads(graph.read_bytes())
        mp = f.actual_pairs(mg)
        original = f.E/'continue_functional.py'
        tree = ast.parse(original.read_text('utf-8'))
        run = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
        run.body = [n for n in run.body if n.lineno == 7 or n.lineno >= 38]
        for node in ast.walk(run):
            if isinstance(node, ast.Constant) and node.value == 'functional_map_native/analysis/graph.json':
                node.value = 'functional_map_view13_native/analysis/graph.json'
        f.save('resume_route14_binding.json', dict(
            original_sha256=f.r.sha(original), resume_sha256=f.r.sha(__file__),
            map_sha256=f.r.sha(db), graph_sha256=f.r.sha(graph), actual_pairs=len(mp),
            map_recovery_binding_sha256=f.r.sha(f.E/'resume_map_view13_binding.json'),
            preserved_failure_sha256=f.r.sha(f.E/'RESUME_MAP_VIEW13_FAIL.json'),
            resumed_source=ast.unparse(tree), map_repeated=False,
            rationale='Successful native map/export retained; correct stale graph path before physical route.'))
        namespace = dict(__name__='route_resume14', __file__=str(original), hashes=hashes, mg=mg, mp=mp)
        exec(compile(ast.fix_missing_locations(tree), str(original), 'exec'), namespace)
        namespace['run']()
    finally:
        k.ReleaseMutex(h)
        k.CloseHandle(h)

if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        f.save('RESUME_ROUTE14_FAIL.json', dict(error=repr(error), traceback=traceback.format_exc(), bit=False, program=False))
        raise
