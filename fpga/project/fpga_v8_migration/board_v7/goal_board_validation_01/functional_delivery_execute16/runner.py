"""SRAM delivery of the qualified default-strategy hold-repair candidate."""
import importlib.util
import json
import sys
import traceback
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
preserved = HERE.parent/'functional_delivery_execute10/runner_corrected11.py'
spec = importlib.util.spec_from_file_location('preserved_delivery11_for16', preserved)
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)
r = delivery.r
delivery.HERE = HERE
r.HERE = HERE
original_check = r.checker.check


def check(manifest):
    handoff = original_check(manifest)
    root = Path(manifest).resolve().parent
    entry = root/'resume_default_hold16.py'
    binding = root/'resume_default_hold16_binding.json'
    recovery = json.loads(binding.read_bytes())
    candidate = root/'functional_candidate01'
    assert recovery['original_sha256'] == r.c.sha(root/'continue_functional.py')
    assert recovery['resume_sha256'] == r.c.sha(entry)
    assert recovery['timing_constraints_modified'] is False
    for key, path in [
        ('map_sha256', candidate/'device_map/v7_sdt_top_map.adf'),
        ('graph_sha256', root/'functional_map_view13_native/analysis/graph.json'),
        ('clock_sha256', candidate/'constraints_live/clock.fdc'),
        ('hold_recovery_binding_sha256', root/'resume_hold_limit15_binding.json'),
        ('previous_failure_sha256', root/'HOLD_LIMIT15_FAIL.json'),
        ('baseline_result_sha256', root/'functional_route01/RESULT.json')]:
        assert recovery[key] == r.c.sha(path), str(path)
    assert recovery['options'] == '-max_hold_violated_paths_num 30000'
    qualified = root/'functional_route04/RESULT.json'
    assert Path(handoff['qualified_result']).resolve() == qualified.resolve()
    assert handoff['qualified_result_sha256'] == r.c.sha(qualified)
    receipt = json.loads((root/'functional_route04_pnr_receipt.json').read_bytes())
    assert receipt['rc'] == 0 and not receipt['errors']
    assert receipt['log_sha256'] == r.c.sha(root/'functional_route04_pnr.log')
    handoff.update(default_hold_recovery_binding_sha256=r.c.sha(binding),
                   default_hold_recovery_entry_sha256=r.c.sha(entry))
    return handoff


def completed_build():
    assert (r.BUILD/'BIT_MANIFEST.json').is_file(), 'No qualified default-strategy bit'
    binding = r.BUILD/'resume_default_hold16_binding.json'
    assert binding.is_file(), 'Missing default-strategy recovery binding'
    r.save('default_hold_delivery_binding.json', {
        'utc': r.c.utc(), 'manifest_sha256': r.c.sha(r.BUILD/'BIT_MANIFEST.json'),
        'recovery_binding_sha256': r.c.sha(binding),
        'recovery_entry_sha256': r.c.sha(r.BUILD/'resume_default_hold16.py'),
        'delivery_entry_sha256': r.c.sha(__file__),
        'preserved_entry_sha256': r.c.sha(preserved),
        'base_entry_sha256': r.c.sha(preserved.with_name('runner.py')),
        'checker_sha256': r.c.sha(HERE.parent/'check_functional_bit09.py'),
        'goal_complete': False})


r.checker.check = check
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
