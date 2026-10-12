"""Check the verify20-qualified bit, then SRAM program and real camera captures."""
import importlib.util
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

delivery_spec = importlib.util.spec_from_file_location('preserved_delivery11_for20', preserved)
delivery = importlib.util.module_from_spec(delivery_spec)
delivery_spec.loader.exec_module(delivery)
r = delivery.r
delivery.HERE = HERE
r.HERE = HERE
r.checker = checker


def completed_build():
    manifest = r.BUILD/'BIT_MANIFEST.json'
    binding = r.BUILD/'resume_io_verify20_binding.json'
    assert manifest.is_file() and binding.is_file(), 'No verify20-qualified bit'
    r.save('io_verify_delivery_binding.json', {
        'utc': r.c.utc(), 'manifest_sha256': r.c.sha(manifest),
        'recovery_binding_sha256': r.c.sha(binding),
        'recovery_entry_sha256': r.c.sha(r.BUILD/'resume_io_verify20.py'),
        'delivery_entry_sha256': r.c.sha(__file__),
        'preserved_entry_sha256': r.c.sha(preserved),
        'base_entry_sha256': r.c.sha(preserved.with_name('runner.py')),
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
