"""Deliver the genbit-final bit: full check, SRAM program, real camera captures."""
import importlib.util
import json
import sys
import traceback
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
preserved = GOAL/'functional_delivery_execute10/runner_corrected11.py'
checker_spec = importlib.util.spec_from_file_location('functional_bit_check10', GOAL/'check_functional_bit10.py')
checker = importlib.util.module_from_spec(checker_spec)
checker_spec.loader.exec_module(checker)

delivery_spec = importlib.util.spec_from_file_location('preserved_delivery11_for21', preserved)
delivery = importlib.util.module_from_spec(delivery_spec)
delivery_spec.loader.exec_module(delivery)
r = delivery.r
delivery.HERE = HERE
r.HERE = HERE
r.checker = checker
original_check = checker.check


def check(manifest):
    handoff = original_check(manifest)
    root = Path(manifest).resolve().parent
    binding = root/'resume_genbit_final21_binding.json'
    assert binding.is_file(), 'genbit-final recovery binding missing'
    doc = json.loads(binding.read_bytes())
    assert doc['resume_sha256'] == r.c.sha(root/'resume_genbit_final21.py'), 'recovery entry changed'
    assert doc['timing_constraints_modified'] is False
    assert doc['route_result_sha256'] == r.c.sha(root/'functional_route07/RESULT.json')
    result = json.loads((root/'functional_route07/RESULT.json').read_bytes())
    assert result['status'] == 'PASS_FUNCTIONAL_ROUTE' and result['retention_pass']
    assert Path(handoff['qualified_result']).parent.name == 'functional_route07'
    assert doc['sbit_sha256'] == handoff['bit_sha256']
    handoff.update(genbit_final_binding_sha256=r.c.sha(binding))
    return handoff


checker.check = check


def completed_build():
    manifest = r.BUILD/'BIT_MANIFEST.json'
    binding = r.BUILD/'resume_genbit_final21_binding.json'
    assert manifest.is_file() and binding.is_file(), 'No genbit-final qualified bit'
    r.save('genbit_final_delivery_binding.json', {
        'utc': r.c.utc(), 'manifest_sha256': r.c.sha(manifest),
        'recovery_binding_sha256': r.c.sha(binding),
        'recovery_entry_sha256': r.c.sha(r.BUILD/'resume_genbit_final21.py'),
        'delivery_entry_sha256': r.c.sha(__file__),
        'preserved_entry_sha256': r.c.sha(preserved),
        'checker_entry_sha256': r.c.sha(GOAL/'check_functional_bit10.py'),
        'goal_complete': False})


r.wait_controller = completed_build

if __name__ == '__main__':
    try:
        delivery.main()
    except Exception as error:
        if r.BOOT:
            try:
                r.ledger_mode('failure_admission_rehold', 0o644)
            except Exception as cleanup:
                r.save('failure_admission_rehold_error.json', {'error': repr(cleanup)})
        r.save('FAIL.json', {'utc': r.c.utc(), 'error': repr(error),
                            'traceback': traceback.format_exc(),
                            'goal_complete': False, 'functional_pass': False,
                            'old_bit_fallback': False})
        raise
