"""Actual SRAM delivery of the map-view recovery, after native qualification."""
import importlib.util
import sys
import traceback
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
preserved = HERE.parent/'functional_delivery_execute12/runner.py'
spec = importlib.util.spec_from_file_location('preserved_delivery12', preserved)
entry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entry)
delivery = entry.delivery
r = entry.r
entry.HERE = HERE
delivery.HERE = HERE
r.HERE = HERE
original_completed_build = r.wait_controller

def completed_build():
    original_completed_build()
    binding = r.BUILD/'resume_map_view13_binding.json'
    assert binding.is_file(), 'Missing map-view recovery binding'
    r.save('map_view_delivery_binding.json', {
        'utc': r.c.utc(),
        'recovery_binding_sha256': r.c.sha(binding),
        'recovery_entry_sha256': r.c.sha(r.BUILD/'resume_map_view13.py'),
        'preserved_entry_sha256': r.c.sha(preserved),
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
