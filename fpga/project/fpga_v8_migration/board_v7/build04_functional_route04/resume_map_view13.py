"""Resume native map with a query-only FDC to initialize the floorplan view."""
from pathlib import Path
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
        for name, digest in hashes['hashes'].items():
            assert f.r.sha(w/name) == digest, name
        binding = json.loads((f.E/'full_compile_constraint_binding.json').read_bytes())
        assert f.r.sha(w/'constraints_live/clock.fdc') == binding['clock_sha256']
        for stage in ['functional_syn', 'functional_syn_native_export', 'functional_syn_native_parser']:
            receipt = json.loads((f.E/(stage+'_receipt.json')).read_bytes())
            assert receipt['rc'] == 0 and not receipt.get('errors')
        failed = json.loads((f.E/'functional_map_receipt.json').read_bytes())
        assert failed['rc'] != 0
        assert failed['errors'] and all('ConstraintEditor-0062' in e or 'Failed to execute' in e for e in failed['errors'])
        query = w/'constraints_live/map_view_query13.fdc'
        with query.open('x', encoding='ascii') as output:
            output.write('# Query only: create native structure view before LCF; retain compiled timing CDB.\nget_ports {free_clk}\n')
        original = f.E/'continue_functional.py'
        tree = ast.parse(original.read_text('utf-8'))
        run = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
        run.body = [n for n in run.body if n.lineno == 7 or n.lineno >= 35]
        for node in ast.walk(run):
            if isinstance(node, ast.Constant) and node.value == 'functional_map':
                node.value = 'functional_map_view13'
            elif isinstance(node, ast.Constant) and node.value == 'functional_map_native':
                node.value = 'functional_map_view13_native'
        base_tool = f.r.tool
        def map_tool(label, text, cwd, project_stage=None):
            if label == 'functional_map_view13':
                text = text.replace(f.r.ARCH, f.r.ARCH+'add_constraint {'+query.as_posix()+'}\n', 1)
            return base_tool(label, text, cwd, project_stage)
        f.r.tool = map_tool
        f.save('resume_map_view13_binding.json', dict(
            original_sha256=f.r.sha(original), resume_sha256=f.r.sha(__file__),
            synthesis_sha256=f.r.sha(w/'synthesize/v7_sdt_top_syn.adf'),
            compile_sha256=f.r.sha(w/'compile/v7_sdt_top_comp.adf'),
            clock_sha256=f.r.sha(w/'constraints_live/clock.fdc'), query_sha256=f.r.sha(query),
            failed_map_receipt_sha256=f.r.sha(f.E/'functional_map_receipt.json'),
            resumed_source=ast.unparse(tree), timing_constraints_modified=False,
            rationale='LCF-only map lacks native FloorPlan Structure View; initialize by get_ports query before loading identical LCF.'))
        namespace = dict(__name__='map_resume13', __file__=str(original), hashes=hashes)
        exec(compile(ast.fix_missing_locations(tree), str(original), 'exec'), namespace)
        namespace['run']()
    finally:
        k.ReleaseMutex(h)
        k.CloseHandle(h)

if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        f.save('RESUME_MAP_VIEW13_FAIL.json', dict(error=repr(error), traceback=traceback.format_exc(), bit=False, program=False))
        raise
