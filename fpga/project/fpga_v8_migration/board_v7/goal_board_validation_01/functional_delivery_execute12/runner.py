"""Actual SRAM and camera delivery after the recovered build finishes successfully."""
import importlib.util
import sys
import traceback
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
previous = HERE.parent/'functional_delivery_execute10/runner_corrected11.py'
spec = importlib.util.spec_from_file_location('preserved_delivery11', previous)
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)
r = delivery.r
delivery.HERE = HERE
r.HERE = HERE

def completed_build():
    # Invoke only after resume completion; native report checks still run in main.
    manifest = r.BUILD/'BIT_MANIFEST.json'
    assert manifest.is_file(), 'Recovered build has no qualified bitstream'
    r.save('recovered_build_binding.json', {
        'utc': r.c.utc(),
        'manifest_sha256': r.c.sha(manifest),
        'resume_binding_sha256': r.c.sha(r.BUILD/'resume12_binding.json'),
        'preserved_runner_sha256': r.c.sha(previous),
        'base_runner_sha256': r.c.sha(previous.with_name('runner.py')),
        'goal_complete': False})

r.wait_controller = completed_build

if __name__ == '__main__':
    try:
        # The original entry also records runner.py in its evidence directory.
        # This file is the new entry; prior implementation hashes are bound above.
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
