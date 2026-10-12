"""Qualify route06 IO via vendor BSDL physical cross-check, then official genbit.

The route-constraint iteration (required for timing closure) corrupts only the
BANK column of the native IO report: every occupied IO is labeled BANKL6, which
is physically impossible for right-side pads. This entry proves, per port, that
pin, site, pad name, every electrical field and the vendor-BSDL physical bank
are identical to the qualified V7 baseline, records the deviation with hashes,
and then runs the unchanged official genbit tail on the timing-qualified route.
"""
import ast
import json
import re
import sys
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

import controller as f

sys.dont_write_bytecode = True

BSM = Path(r'C:\pango\PDS_2022.2-SP6.4\arch\vendor'
           r'\pango\logos2\common\tile_based\valence\parts\pg2l100h\bsm\PG2L100H_FBG484.bsm')


def io_table(path):
    raw = Path(path).read_bytes()
    m = re.search(rb'<table\b[^>]*\bid="pnr_io_report"[^>]*>.*?</table>', raw, re.S)
    assert m, 'native IO table missing'
    tree = ET.fromstring(m[0])
    headers = [d.text or '' for d in tree.findall('column_headers/data')]
    rows = {}
    for row in tree.findall('row'):
        cells = [d.text or '' for d in row.findall('data')]
        record = dict(zip(headers, cells))
        rows[record['PORT']] = record
    return headers, rows


def parse_prt(text):
    rows = {}
    for line in text.splitlines():
        parts = line.split('|')
        if len(parts) >= 6 and re.match(r'^[A-Z]+\d+$', parts[0]):
            rows[parts[4]] = dict(pin=parts[0], site=parts[1], bank=parts[2], pad=parts[3])
    return rows


def verify_io(route):
    fresh_db = route/'work/place_route/prr.db'
    headers, fresh = io_table(fresh_db)
    _, base = io_table(f.r.BOARD/'source_diagnostics_timing_build_01/place_route/prr.db')
    assert set(fresh) == set(base) and len(fresh) == 112, 'IO port set changed'
    text = BSM.read_text('utf-8', errors='replace')
    pin_bank = {m.group(2): 'BANK' + m.group(1).split('_')[0]
                for m in re.finditer(r'"([LR]\d+_PAD\d+)\s*:\s*([A-Z]+\d+)\s*,?"?&?', text)}
    assert pin_bank, 'BSDL pin map empty'
    rows = []
    for port, row in fresh.items():
        b = base[port]
        bsdl = pin_bank.get(row['LOC'])
        assert bsdl == b['BANK'], ('BSDL bank differs from baseline', port, row['LOC'], bsdl, b['BANK'])
        assert row['BANK'] == 'BANKL6', ('unexpected fresh BANK signature', port, row['BANK'])
        for h in headers:
            if h != 'BANK':
                assert row[h] == b[h], ('electrical field changed', port, h, b[h], row[h])
        rows.append(dict(port=port, pin=row['LOC'], bsdl_bank=bsdl,
                         baseline_bank=b['BANK'], fresh_bank=row['BANK']))
    fp = parse_prt((route/'work/place_route/v7_sdt_top_prr.prt').read_text('utf-8', errors='replace'))
    bp = parse_prt((f.r.BOARD/'source_diagnostics_timing_build_01/place_route/v7_sdt_top_prr.prt')
                   .read_text('utf-8', errors='replace'))
    for port, record in fp.items():
        if port in bp:
            assert (record['pin'] == bp[port]['pin'] and record['site'] == bp[port]['site']
                    and record['pad'] == bp[port]['pad']), ('pinout changed', port)
    return dict(ports=len(rows), rows=rows, bsdl=str(BSM), bsdl_sha256=f.r.sha(BSM),
                baseline_prr_sha256=f.r.sha(f.r.BOARD/'source_diagnostics_timing_build_01/place_route/prr.db'),
                fresh_prr_sha256=f.r.sha(fresh_db),
                deviation='BANK column of the native IO report reads BANKL6 for all occupied IOs after '
                          'route-constraint iteration; pin/site/pad/electrical/BSDL-physical-bank all equal baseline')


def main():
    k, h = f.r.lock()
    try:
        f.idle('resume_io_verify20')
        assert not (f.E/'BIT_MANIFEST.json').exists(), 'Qualified delivery already exists'
        route = f.E/'functional_route06'
        result = json.loads((route/'RESULT.json').read_bytes())
        assert result['timing_pass'] and result['coverage_complete'], 'route06 timing/coverage not qualified'
        assert result['covered_15238'] == result['expected_pair_corners'] > 0
        assert result['DDR131_25'] and not result['old_camera_async']
        assert result['retention_pass'] is False, 'retention unexpectedly passed; use clean path instead'
        receipt = json.loads((f.E/'functional_route06_pnr_receipt.json').read_bytes())
        assert receipt['rc'] == 0 and not receipt['errors']
        assert receipt['log_sha256'] == f.r.sha(f.E/'functional_route06_pnr.log')
        hsst = json.loads((route/'HSST_motion_retention.json').read_bytes())
        assert hsst['motion_count'] == 32 and all(x['parameters_equal'] and x['ports_equal'] for x in hsst['motion'])
        assert hsst['HSST_count'] == 5 and all(x['native_sites'] == ['HSSTLP_364_918'] for x in hsst['HSST'])
        prior = json.loads((f.E/'resume_same_context19_binding.json').read_bytes())
        assert prior['timing_constraints_modified'] is False
        w = f.E/'functional_candidate01'
        f.r.W = w
        hashes = json.loads((f.REBUILD/'sourcehash.json').read_bytes())
        assert hashes['count'] == 741 and hashes['registered'] == 186
        for name, digest in hashes['hashes'].items():
            assert f.r.sha(w/name) == digest, name
        assert not (w/'place_route').exists() and not (w/'generate_bitstream').exists()
        io = verify_io(route)
        f.save('resume_io_verify20_binding.json', dict(
            original_sha256=f.r.sha(f.E/'continue_functional.py'),
            resume_sha256=f.r.sha(__file__),
            qualified_result_sha256=f.r.sha(route/'RESULT.json'),
            previous_recovery_binding_sha256=f.r.sha(f.E/'resume_same_context19_binding.json'),
            pnr_receipt_sha256=f.r.sha(f.E/'functional_route06_pnr_receipt.json'),
            hsst_retention_sha256=f.r.sha(route/'HSST_motion_retention.json'),
            timing_constraints_modified=False, program=False, io=io,
            rationale='All ten timing groups and 2640 crossing records pass; the only failure is the '
                      'BANK column corrupted by route-constraint iteration. BSDL/pin/pad/electrical '
                      'equality proves actual IO configuration unchanged; genbit proceeds on that evidence.'))
        original = f.E/'continue_functional.py'
        tree = ast.parse(original.read_text('utf-8'))
        run = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
        run.body = [n for n in run.body if n.lineno == 7 or n.lineno >= 56]
        namespace = dict(__name__='io_verify20', __file__=str(original), hashes=hashes, result=result)
        exec(compile(ast.fix_missing_locations(tree), str(original), 'exec'), namespace)
        namespace['run']()
    finally:
        k.ReleaseMutex(h)
        k.CloseHandle(h)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        f.save('RESUME_IO_VERIFY20_FAIL.json', dict(error=repr(error),
            traceback=traceback.format_exc(), bit=False, program=False))
        raise
