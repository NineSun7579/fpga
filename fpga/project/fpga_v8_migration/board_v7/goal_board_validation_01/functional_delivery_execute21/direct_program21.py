"""Direct authorized SRAM programming of the official genbit sbit + real board capture.

User instruction: program the generated bitstream directly. Functional acceptance
is the board runtime evidence itself (six-camera capture rates, C5/C6 tag advance,
model completion, real screenshots). This entry records honestly what is and is
not pre-verified; it does not fabricate a qualification manifest.
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

spec = importlib.util.spec_from_file_location(
    'preserved11_for_direct21', GOAL/'functional_delivery_execute10/runner_corrected11.py')
pres = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pres)
r = pres.r
r.HERE = HERE


def bind_direct():
    """Record exactly what is proven about the bit before it is programmed."""
    build = r.BUILD
    sbit = build/'functional_candidate01/generate_bitstream/v7_sdt_top.sbit'
    assert sbit.is_file() and sbit.stat().st_size > 0
    digest = r.c.sha(sbit)
    receipt = json.loads((build/'functional_genbit_receipt.json').read_bytes())
    assert receipt['rc'] == 0 and not receipt['errors'], 'genbit stage failed'
    assert receipt['log_sha256'] == r.c.sha(build/'functional_genbit.log'), 'genbit log changed'
    w = build/'functional_candidate01'
    rebuild = build.parent/'build04_constraint_load_fix01/rebuild03'
    hashes = json.loads((rebuild/'sourcehash.json').read_bytes())
    assert hashes['count'] == 741 and hashes['registered'] == 186
    for name, expected in hashes['hashes'].items():
        assert r.c.sha(w/name) == expected, 'source changed: ' + name

    def io_table(path):
        m = re.search(rb'<table\b[^>]*\bid="pnr_io_report"[^>]*>.*?</table>', path.read_bytes(), re.S)
        assert m, 'IO table missing: ' + str(path)
        return m[0]

    fresh = io_table(w/'place_route/prr.db')
    base = io_table(build.parent/'source_diagnostics_timing_build_01/place_route/prr.db')
    assert fresh == base, 'IO report differs from qualified baseline'
    bit = dict(path=str(sbit), sha256=digest, size=sbit.stat().st_size)
    doc = dict(
        status='DIRECT_PROGRAM_AUTHORIZED',
        user_instruction='直接烧录验证',
        bit=bit,
        verified=dict(
            official_genbit_rc=0,
            genbit_receipt_sha256=r.c.sha(build/'functional_genbit_receipt.json'),
            genbit_log_sha256=r.c.sha(build/'functional_genbit.log'),
            sources_741_byte_identical=True,
            source_binding_sha256=r.c.sha(rebuild/'sourcehash.json'),
            io_table_byte_identical_baseline=True,
            routed_db_sha256=r.c.sha(w/'place_route/v7_sdt_top_pnr.adf'),
            rtl_same_as_working_v7=True),
        limitations=[
            'production60 storage site plan is not registered in the project flow; '
            'gen_bit_stream applied only the 22 hard-IP def_inst_site constraints',
            'full dual-corner 2640-crossing acceptance was not re-run on the '
            'genbit-final database; genbit reported positive hold slack '
            '(132ps slow / 87ps fast) and no failing setup summary before bitgen',
            'functional acceptance is the real board runtime capture of this delivery'],
        flash_modified=False,
        program=True)
    r.save('direct_program21_binding.json', doc)
    return bit, doc


def wait_controller():
    """Direct mode: the bit is the genbit output; verify it exists and tools are idle."""
    assert (r.BUILD/'functional_candidate01/generate_bitstream/v7_sdt_top.sbit').is_file()
    r.save('controller_wait.json', {'utc': r.c.utc(), 'direct_program_mode': True})


r.wait_controller = wait_controller


def main():
    assert not (HERE/'direct_program21_started.json').exists(), 'Never repeat direct program21'
    bit, doc = bind_direct()
    r.save('direct_program21_started.json', {'utc': r.c.utc(), 'bit': bit,
                                             'binding_sha256': r.c.sha(HERE/'direct_program21_binding.json'),
                                             'goal_complete': False})
    digest = bit['sha256']
    print(r.c.utc(), 'Direct program binding recorded', digest, flush=True)
    k, h = r.c.tool_lease(HERE)
    try:
        r.vendor.idle()
        r.reboot()
        r.snapshot('before_sram')
        directory = HERE/'sram_program'
        directory.mkdir()
        receipt = {'status': 'blocked', 'target': 'PG2L100H', 'mode': 'sram',
                   'bit': bit['path'], 'bit_sha256': digest, 'stages': {}, 'stage_errors': [],
                   'boot_id': r.BOOT,
                   'handoff_sha256': r.c.sha(HERE/'direct_program21_binding.json'),
                   'started_utc': r.c.utc()}
        try:
            r.vendor.run(SimpleNamespace(mode='sram', timeout=300), receipt, directory, Path(bit['path']), digest)
        finally:
            receipt['ended_utc'] = r.c.utc()
            r.c.save(directory/'receipt.json', receipt)
        assert receipt['status'] == 'success' and all(receipt['stages'].values())
        r.link_driver()
        for mode in ['six-camera', 'driving']:
            r.viewer(mode, Path(bit['path']), directory/'receipt.json')
        r.snapshot('final_state')
        r.save('RESULT.json', {
            'status': 'DIRECT21_SRAM_PROGRAMMED_TWO_MODES_CAPTURED_REQUIRES_VISUAL_REVIEW',
            'utc': r.c.utc(), 'boot_id': r.BOOT,
            'bit': bit['path'], 'bit_sha256': digest,
            'vendor_receipt': str(directory/'receipt.json'),
            'vendor_receipt_sha256': r.c.sha(directory/'receipt.json'),
            'binding_sha256': r.c.sha(HERE/'direct_program21_binding.json'),
            'goal_complete': False, 'functional_pass': False,
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
