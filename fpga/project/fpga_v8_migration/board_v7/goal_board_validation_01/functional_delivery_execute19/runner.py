"""Deliver only the checked same-context MAP/PLC route candidate."""
import importlib.util
import json
import sys
import traceback
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
preserved = HERE.parent/'functional_delivery_execute10/runner_corrected11.py'
spec = importlib.util.spec_from_file_location('delivery11_for19', preserved)
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)
r = delivery.r
delivery.HERE = HERE
r.HERE = HERE
original_check = r.checker.check


def check(manifest):
    handoff = original_check(manifest)
    root = Path(manifest).resolve().parent
    binding = root/'resume_same_context19_binding.json'
    recovery = json.loads(binding.read_bytes())
    require = r.checker.require
    require(recovery['timing_constraints_modified'] is False, 'Timing constraints changed')
    for key, path in [
        ('original_sha256', root/'continue_functional.py'),
        ('resume_sha256', root/'resume_same_context19.py'),
        ('map_sha256', root/'functional_candidate01/device_map/v7_sdt_top_map.adf'),
        ('graph_sha256', root/'functional_map_view13_native/analysis/graph.json'),
        ('clock_sha256', root/'functional_candidate01/constraints_live/clock.fdc'),
        ('previous_failure_sha256', root/'PLC_ROUTE18_FAIL.json'),
        ('previous_recovery_binding_sha256', root/'resume_plc_route18_binding.json'),
        ('failed_io_sha256', root/'functional_route05/native_IO112_comparison.json')]:
        require(recovery[key] == r.c.sha(path), 'Recovery19 input changed: '+str(path))
    qualified = root/'functional_route06/RESULT.json'
    require(Path(handoff['qualified_result']).resolve() == qualified.resolve()
            and handoff['qualified_result_sha256'] == r.c.sha(qualified), 'Wrong qualified route')
    command_path = root/'functional_route06/same_context_command.json'
    command = json.loads(command_path.read_bytes())
    require(command['one_tool_invocation'] is True
            and command['command'].count('pnr -force_to_run') == 2
            and '-place_only' in command['command']
            and recovery['options'] in command['command'], 'MAP/PLC command binding differs')
    require(command['map_sha256'] == recovery['map_sha256'] == r.c.sha(command['map']),
            'Same-context MAP input changed')
    receipt = json.loads((root/'functional_route06_pnr_receipt.json').read_bytes())
    require(receipt['rc'] == 0 and not receipt['errors']
            and receipt['log_sha256'] == r.c.sha(root/'functional_route06_pnr.log'),
            'Native route06 stage failed or changed')
    io = json.loads((root/'functional_route06/native_IO112_comparison.json').read_bytes())
    require(io['ports'] == 112 and io['table_bytes_equal'] and not io['differences'],
            'Complete native IO table differs from baseline')
    require(io['native_table_sha256'] == r.c.sha(root/'functional_route06/native_IO112_raw.xml'),
            'Native IO artifact changed')
    handoff.update(same_context_recovery_binding_sha256=r.c.sha(binding),
                   same_context_command_sha256=r.c.sha(command_path))
    return handoff


def completed_build():
    handoff = check(r.BUILD/'BIT_MANIFEST.json')
    r.save('same_context_delivery_binding.json', {
        'utc': r.c.utc(), 'bit_sha256': handoff['bit_sha256'],
        'recovery_binding_sha256': handoff['same_context_recovery_binding_sha256'],
        'delivery_entry_sha256': r.c.sha(__file__),
        'preserved_entry_sha256': r.c.sha(preserved),
        'base_entry_sha256': r.c.sha(preserved.with_name('runner.py')),
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
