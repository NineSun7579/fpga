"""Resume completed compile after disk-full parser failure; preserve failed evidence."""
from pathlib import Path
import ast
import hashlib
import json
import shutil
import sys
import traceback
import controller as f

def main():
    f.idle('resume12_start')
    original = Path(__file__).with_name('continue_functional.py')
    source = original.read_text('utf-8')
    tree = ast.parse(source)
    run = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
    # Keep the work directory assignments and everything after the successful compile.
    run.body = [n for n in run.body if n.lineno == 7 or n.lineno >= 28]
    for node in ast.walk(run):
        if isinstance(node, ast.Constant) and node.value == 'functional_compile_native':
            node.value = 'functional_compile_native_retry12'
    failure = (f.E/'functional_compile_native/analysis/parser.log').read_text()
    assert 'No space left on device' in failure
    assert shutil.disk_usage(f.E).free > 8 * 1024**3, 'Need disk space before restarting tools'
    db = f.E/'functional_candidate01/compile/v7_sdt_top_comp.adf'
    assert db.is_file()
    hashes = json.loads((f.REBUILD/'sourcehash.json').read_bytes())
    assert hashes['count'] == 741 and hashes['registered'] == 186
    for name, digest in hashes['hashes'].items():
        assert f.r.sha(f.E/'functional_candidate01'/name) == digest, name
    binding = json.loads((f.E/'full_compile_constraint_binding.json').read_bytes())
    assert binding['all_signature_included'] and binding['budget_ns'] == 15.238
    assert f.r.sha(f.E/'functional_candidate01/constraints_live/clock.fdc') == binding['clock_sha256']
    f.save('resume12_binding.json', dict(
        original_sha256=hashlib.sha256(source.encode()).hexdigest(),
        resumed_source=ast.unparse(tree),
        compile_adf_sha256=f.r.sha(db),
        rationale='Compile succeeded; preserve disk-full parser failure and resume with a new native export directory',
        compile_repeated=False))
    namespace = dict(__name__='disk_resume12', __file__=str(Path(__file__).resolve()), hashes=hashes)
    exec(compile(ast.fix_missing_locations(tree), str(original), 'exec'), namespace)
    namespace['run']()

if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        f.save('RESUME12_FAIL.json', dict(error=repr(error), traceback=traceback.format_exc(), bit=False, program=False))
        raise
