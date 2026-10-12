"""Third SRAM round: driving-mode screenshots first (the missing deliverable),
then six-camera. Per-mode resilience with one reboot+reprogram recovery retry.

Evidence so far: round 1 produced real post-burn six-camera screenshots (5/6 cams
live, C5 frozen); round 2 hit an intermittent PCIe DMA wedge (all tag reads
ETIMEDOUT) and captured nothing. This round maximizes the chance of complete
evidence per mode and records both receipts.
"""
import importlib.util
import json
import re
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
BUILD = GOAL.parent / 'build04_functional_route04'
ROUND1 = GOAL/'functional_delivery_execute21'
ROUND2 = GOAL/'functional_delivery_execute22'

spec = importlib.util.spec_from_file_location(
    'preserved11_for_direct23', GOAL/'functional_delivery_execute10/runner_corrected11.py')
pres = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pres)
r = pres.r
r.HERE = HERE


def bind_direct():
    build = r.BUILD
    sbit = build/'functional_candidate01/generate_bitstream/v7_sdt_top.sbit'
    assert sbit.is_file() and sbit.stat().st_size > 0
    digest = r.c.sha(sbit)
    receipt = json.loads((build/'functional_genbit_receipt.json').read_bytes())
    assert receipt['rc'] == 0 and not receipt['errors'], 'genbit stage failed'
    assert receipt['log_sha256'] == r.c.sha(build/'functional_genbit.log'), 'genbit log changed'
    round1 = json.loads((ROUND1/'sram_program/receipt.json').read_bytes())
    assert round1['status'] == 'success' and all(round1['stages'].values()) and round1['bit_sha256'] == digest
    round2 = json.loads((ROUND2/'sram_program/receipt.json').read_bytes())
    assert round2['status'] == 'success' and all(round2['stages'].values()) and round2['bit_sha256'] == digest
    bit = dict(path=str(sbit), sha256=digest, size=sbit.stat().st_size)
    doc = dict(
        status='DIRECT_PROGRAM_AUTHORIZED_ROUND3',
        user_instruction='继续获取RK3568截图验证; driving截图优先',
        bit=bit,
        verified=dict(
            official_genbit_rc=0,
            genbit_receipt_sha256=r.c.sha(build/'functional_genbit_receipt.json'),
            round1_receipt_sha256=r.c.sha(ROUND1/'sram_program/receipt.json'),
            round2_receipt_sha256=r.c.sha(ROUND2/'sram_program/receipt.json'),
            validated_sbit_round1_sha256=r.c.sha(ROUND1/'sram_program/validated.sbit')),
        known_findings=dict(
            round1_six_camera='5/6 cams live; C5 frozen at 0.0 with valid last frame',
            round2='PCIe DMA wedge: all six tag reads ETIMEDOUT, viewer exit(3)'),
        flash_modified=False,
        program=True)
    r.save('direct_program23_binding.json', doc)
    return bit, doc


def wait_controller():
    assert (r.BUILD/'functional_candidate01/generate_bitstream/v7_sdt_top.sbit').is_file()
    r.save('controller_wait.json', {'utc': r.c.utc(), 'direct_program_mode': True, 'round': 3})


r.wait_controller = wait_controller


def sram(directory):
    directory.mkdir(exist_ok=True)
    digest = r.c.sha(r.BUILD/'functional_candidate01/generate_bitstream/v7_sdt_top.sbit')
    receipt = {'status': 'blocked', 'target': 'PG2L100H', 'mode': 'sram', 'round': 3,
               'bit': str(r.BUILD/'functional_candidate01/generate_bitstream/v7_sdt_top.sbit'),
               'bit_sha256': digest, 'stages': {}, 'stage_errors': [],
               'boot_id': r.BOOT,
               'handoff_sha256': r.c.sha(HERE/'direct_program23_binding.json'),
               'started_utc': r.c.utc()}
    try:
        r.vendor.run(SimpleNamespace(mode='sram', timeout=300), receipt, directory,
                     Path(receipt['bit']), digest)
    finally:
        receipt['ended_utc'] = r.c.utc()
        r.c.save(directory/'receipt.json', receipt)
    assert receipt['status'] == 'success' and all(receipt['stages'].values())
    return directory/'receipt.json'


def main():
    assert not (HERE/'direct_program23_started.json').exists(), 'Never repeat direct program23'
    bit, doc = bind_direct()
    r.save('direct_program23_started.json', {'utc': r.c.utc(), 'bit': bit,
                                             'binding_sha256': r.c.sha(HERE/'direct_program23_binding.json'),
                                             'goal_complete': False})
    print(r.c.utc(), 'Round3 binding recorded', bit['sha256'], flush=True)
    k, h = r.c.tool_lease(HERE)
    try:
        r.vendor.idle()
        r.reboot()
        r.snapshot('before_sram')
        receipt_path = sram(HERE/'sram_program')
        r.link_driver()
        mode_results = {}
        for mode in ['driving', 'six-camera']:
            try:
                r.viewer(mode, Path(bit['path']), receipt_path)
                mode_results[mode] = 'pass'
                continue
            except Exception as error:
                mode_results[mode] = 'fail: ' + repr(error)
                r.save(mode+'_viewer_error.json', {'utc': r.c.utc(), 'error': repr(error),
                                                   'traceback': traceback.format_exc()})
                print(r.c.utc(), 'mode', mode, 'failed; recovery cycle:', repr(error), flush=True)
            try:
                r.reboot()
                r.snapshot('before_sram_recovery')
                receipt_path = sram(HERE/('sram_program_recovery_' + mode))
                r.link_driver()
                r.viewer(mode, Path(bit['path']), receipt_path)
                mode_results[mode] += ' | retry after recovery: pass'
            except Exception as error:
                mode_results[mode] += ' | retry after recovery: fail: ' + repr(error)
                r.save(mode+'_viewer_error_retry.json', {'utc': r.c.utc(), 'error': repr(error),
                                                         'traceback': traceback.format_exc()})
                print(r.c.utc(), 'mode', mode, 'retry failed:', repr(error), flush=True)
        r.snapshot('final_state')
        r.save('RESULT.json', {
            'status': 'DIRECT23_SRAM_PROGRAMMED_MODES_CAPTURED_REQUIRES_VISUAL_REVIEW',
            'utc': r.c.utc(), 'boot_id': r.BOOT,
            'bit': bit['path'], 'bit_sha256': bit['sha256'],
            'vendor_receipt': str(receipt_path),
            'vendor_receipt_sha256': r.c.sha(receipt_path),
            'binding_sha256': r.c.sha(HERE/'direct_program23_binding.json'),
            'mode_results': mode_results,
            'goal_complete': False,
            'functional_pass': all(v == 'pass' for v in mode_results.values()),
            'flash_modified': False, 'admission_mode': '0o644', 'ledger_retained': True})
    finally:
        k.ReleaseMutex(h)
        k.CloseHandle(h)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        if r.BOOT:
            try:
                r.ledger_mode('failure_admission_rehold', 0o644)
            except Exception as cleanup:
                r.save('failure_admission_rehold_error.json', {'error': repr(cleanup)})
        r.save('FAIL.json', {'utc': r.c.utc(), 'error': repr(error),
                             'traceback': traceback.format_exc(),
                             'goal_complete': False, 'functional_pass': False,
                             'old_bit_fallback': False, 'flash_modified': False})
        traceback.print_exc()
        sys.exit(1)
