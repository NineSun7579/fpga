"""Check the PLC optimization recovery before actual SRAM and camera capture."""
import importlib.util
import json
import sys
import traceback
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
preserved = HERE.parent/'functional_delivery_execute10/runner_corrected11.py'
spec = importlib.util.spec_from_file_location('preserved_delivery11_for18', preserved)
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)
r = delivery.r
delivery.HERE = HERE
r.HERE = HERE
original_check = r.checker.check


def check(manifest):
    handoff = original_check(manifest)
    root = Path(manifest).resolve().parent
    binding = root/'resume_plc_route18_binding.json'
    recovery = json.loads(binding.read_bytes())
    require = r.checker.require
    require(recovery['timing_constraints_modified'] is False, 'Recovery changed timing constraints')
    candidate = root/'functional_candidate01'
    for key, path in [
        ('original_sha256', root/'continue_functional.py'),
        ('resume_sha256', root/'resume_plc_route18.py'),
        ('map_sha256', candidate/'device_map/v7_sdt_top_map.adf'),
        ('graph_sha256', root/'functional_map_view13_native/analysis/graph.json'),
        ('clock_sha256', candidate/'constraints_live/clock.fdc'),
        ('previous_recovery_binding_sha256', root/'resume_default_hold16_binding.json'),
        ('previous_failure_sha256', root/'DEFAULT_HOLD16_FAIL.json'),
        ('official_help_sha256', root.parent/'build04_diagnostic_behavior_route01/help.log'),
        ('plc_sha256', Path(recovery['plc']))]:
        require(recovery[key] == r.c.sha(path), 'PLC recovery binding changed: '+str(path))
    prior = json.loads((root/'resume_default_hold16_binding.json').read_bytes())
    require(prior['resume_sha256'] == r.c.sha(root/'resume_default_hold16.py')
            and prior['timing_constraints_modified'] is False,
            'Previous PLC-producing recovery changed')
    plc = root/'functional_route04/work/place_route/v7_sdt_top_plc.adf'
    require(Path(recovery['plc']).resolve() == plc.resolve(), 'Wrong PLC predecessor')
    staged = json.loads((root/'functional_route05/plc_input_binding.json').read_bytes())
    staged_path = root/'functional_route05/work/placement_input/v7_sdt_top_plc.adf'
    require(Path(staged['source']).resolve() == plc.resolve()
            and Path(staged['staged']).resolve() == staged_path.resolve()
            and staged['sha256'] == recovery['plc_sha256'] == r.c.sha(staged_path),
            'Staged PLC input changed')
    require('-input_db_file {'+staged_path.as_posix()+'}' in staged['command']
            and recovery['options'] in staged['command'], 'PLC command binding changed')
    for label in ['functional_route04', 'functional_route05']:
        receipt = json.loads((root/(label+'_pnr_receipt.json')).read_bytes())
        require(receipt['rc'] == 0 and not receipt['errors']
                and receipt['log_sha256'] == r.c.sha(root/(label+'_pnr.log')),
                'PLC predecessor or optimization stage failed: '+label)
    qualified = root/'functional_route05/RESULT.json'
    require(Path(handoff['qualified_result']).resolve() == qualified.resolve()
            and handoff['qualified_result_sha256'] == r.c.sha(qualified),
            'Bit does not bind the PLC-optimized route')
    handoff.update(plc_recovery_binding_sha256=r.c.sha(binding),
                   plc_input_binding_sha256=r.c.sha(root/'functional_route05/plc_input_binding.json'))
    return handoff


def completed_build():
    manifest = r.BUILD/'BIT_MANIFEST.json'
    binding = r.BUILD/'resume_plc_route18_binding.json'
    assert manifest.is_file() and binding.is_file(), 'No qualified PLC optimization bit'
    r.save('plc_route_delivery_binding.json', {
        'utc': r.c.utc(), 'manifest_sha256': r.c.sha(manifest),
        'recovery_binding_sha256': r.c.sha(binding),
        'recovery_entry_sha256': r.c.sha(r.BUILD/'resume_plc_route18.py'),
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
