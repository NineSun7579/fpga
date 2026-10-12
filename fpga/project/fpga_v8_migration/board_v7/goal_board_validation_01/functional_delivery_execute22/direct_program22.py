"""Second authorized SRAM programming round of the official genbit sbit.

Round 1 (functional_delivery_execute21) programmed the board and captured both
modes. The user requested one more burn round immediately after round 1 lands.
This entry re-executes the identical chain (bind -> reboot -> SRAM -> PCIe ->
six-camera + driving captures) and cross-references the round-1 receipts.
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

spec = importlib.util.spec_from_file_location(
    'preserved11_for_direct22', GOAL/'functional_delivery_execute10/runner_corrected11.py')
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
    assert round1['status'] == 'success' and all(round1['stages'].values())
    assert round1['bit_sha256'] == digest

    def io_table(path):
        m = re.search(rb'<table\b[^>]*\bid="pnr_io_report"[^>]*>.*?</table>', path.read_bytes(), re.S)
        assert m, 'IO table missing: ' + str(path)
        return m[0]

    w = build/'functional_candidate01'
    fresh = io_table(w/'place_route/prr.db')
    base = io_table(build.parent/'source_diagnostics_timing_build_01/place_route/prr.db')
    assert fresh == base, 'IO report differs from qualified baseline'
    bit = dict(path=str(sbit), sha256=digest, size=sbit.stat().st_size)
    doc = dict(
        status='DIRECT_PROGRAM_AUTHORIZED_ROUND2',
        user_instruction='还要再烧一轮',
        bit=bit,
        verified=dict(
            official_genbit_rc=0,
            genbit_receipt_sha256=r.c.sha(build/'functional_genbit_receipt.json'),
            round1_receipt_sha256=r.c.sha(ROUND1/'sram_program/receipt.json'),
            round1_bit_sha256=round1['bit_sha256'],
            round1_boot_id=round1['boot_id'],
            io_table_byte_identical_baseline=True),
        flash_modified=False,
        program=True)
    r.save('direct_program22_binding.json', doc)
    return bit, doc


def wait_controller():
    assert (r.BUILD/'functional_candidate01/generate_bitstream/v7_sdt_top.sbit').is_file()
    r.save('controller_wait.json', {'utc': r.c.utc(), 'direct_program_mode': True, 'round': 2})


r.wait_controller = wait_controller


def main():
    assert not (HERE/'direct_program22_started.json').exists(), 'Never repeat direct program22'
    bit, doc = bind_direct()
    r.save('direct_program22_started.json', {'utc': r.c.utc(), 'bit': bit,
                                             'binding_sha256': r.c.sha(HERE/'direct_program22_binding.json'),
                                             'goal_complete': False})
    digest = bit['sha256']
    print(r.c.utc(), 'Round2 program binding recorded', digest, flush=True)
    k, h = r.c.tool_lease(HERE)
    try:
        r.vendor.idle()
        r.reboot()
        r.snapshot('before_sram')
        directory = HERE/'sram_program'
        directory.mkdir()
        receipt = {'status': 'blocked', 'target': 'PG2L100H', 'mode': 'sram', 'round': 2,
                   'bit': bit['path'], 'bit_sha256': digest, 'stages': {}, 'stage_errors': [],
                   'boot_id': r.BOOT,
                   'handoff_sha256': r.c.sha(HERE/'direct_program22_binding.json'),
                   'started_utc': r.c.utc()}
        try:
            r.vendor.run(SimpleNamespace(mode='sram', timeout=300), receipt, directory, Path(bit['path']), digest)
        finally:
            receipt['ended_utc'] = r.c.utc()
            r.c.save(directory/'receipt.json', receipt)
        assert receipt['status'] == 'success' and all(receipt['stages'].values())
        r.link_driver()
        mode_results = {}
        for mode in ['six-camera', 'driving']:
            try:
                r.viewer(mode, Path(bit['path']), directory/'receipt.json')
                mode_results[mode] = 'pass'
            except Exception as error:
                mode_results[mode] = 'fail: ' + repr(error)
                r.save(mode+'_viewer_error.json', {'utc': r.c.utc(), 'error': repr(error),
                                                   'traceback': traceback.format_exc()})
                print(r.c.utc(), 'mode', mode, 'failed but continuing:', repr(error), flush=True)
        r.snapshot('final_state')
        r.save('RESULT.json', {
            'status': 'DIRECT22_SRAM_PROGRAMMED_TWO_MODES_CAPTURED_REQUIRES_VISUAL_REVIEW',
            'utc': r.c.utc(), 'boot_id': r.BOOT,
            'bit': bit['path'], 'bit_sha256': digest,
            'vendor_receipt': str(directory/'receipt.json'),
            'vendor_receipt_sha256': r.c.sha(directory/'receipt.json'),
            'binding_sha256': r.c.sha(HERE/'direct_program22_binding.json'),
            'mode_results': mode_results,
            'goal_complete': False, 'functional_pass': all(v == 'pass' for v in mode_results.values()),
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
