"""SRAM and real camera capture after hold-limit recovery passes native checks."""
import importlib.util
import sys
import traceback
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
preserved = HERE.parent/'functional_delivery_execute10/runner_corrected11.py'
spec = importlib.util.spec_from_file_location('preserved_delivery11_for15', preserved)
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)
r = delivery.r
delivery.HERE = HERE
r.HERE = HERE

def completed_build():
    manifest = r.BUILD/'BIT_MANIFEST.json'
    binding = r.BUILD/'resume_hold_limit15_binding.json'
    assert manifest.is_file() and binding.is_file(), 'No qualified hold-repair build'
    r.save('hold_repair_delivery_binding.json', {
        'utc': r.c.utc(), 'manifest_sha256': r.c.sha(manifest),
        'recovery_binding_sha256': r.c.sha(binding),
        'recovery_entry_sha256': r.c.sha(r.BUILD/'resume_hold_limit15.py'),
        'preserved_entry_sha256': r.c.sha(preserved),
        'base_entry_sha256': r.c.sha(preserved.with_name('runner.py')),
        'checker_sha256': r.c.sha(HERE.parent/'check_functional_bit09.py'),
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
