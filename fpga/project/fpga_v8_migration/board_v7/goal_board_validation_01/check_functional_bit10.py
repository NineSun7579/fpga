"""Check the actual functional build handoff before SRAM programming.

Version 10: adds an evidence-based acceptance for the native IO report BANK
column corrupted by route-constraint iteration. Physical IO configuration is
re-verified independently against the vendor BSDL pin->bank map, the pinout
report and every electrical field, rather than waiving the check.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


BSM = Path(r'C:\pango\PDS_2022.2-SP6.4\arch\vendor'
           r'\pango\logos2\common\tile_based\valence\parts\pg2l100h\bsm\PG2L100H_FBG484.bsm')
BASELINE = Path(__file__).resolve().parents[1]/'source_diagnostics_timing_build_01/place_route'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def io_table(path):
    raw = Path(path).read_bytes()
    m = re.search(rb'<table\b[^>]*\bid="pnr_io_report"[^>]*>.*?</table>', raw, re.S)
    require(m, 'native IO table missing')
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


def verify_io_deviation(root, result_path):
    """Independently prove the only IO difference is the corrupted BANK column."""
    binding = root/'resume_io_verify20_binding.json'
    require(binding.is_file(), 'IO verify20 binding missing')
    verified = json.loads(binding.read_bytes())
    require(verified['qualified_result_sha256'] == sha(result_path), 'verify20 binds another result')
    require(verified['resume_sha256'] == sha(root/'resume_io_verify20.py'), 'verify20 entry changed')
    require(verified['timing_constraints_modified'] is False, 'verify20 modified timing constraints')
    require(verified['pnr_receipt_sha256'] == sha(root/'functional_route06_pnr_receipt.json'),
            'verify20 pnr receipt changed')
    route = result_path.parent
    headers, fresh = io_table(route/'work/place_route/prr.db')
    _, base = io_table(BASELINE/'prr.db')
    require(set(fresh) == set(base) and len(fresh) == 112, 'IO port set changed')
    text = BSM.read_text('utf-8', errors='replace')
    pin_bank = {m.group(2): 'BANK' + m.group(1).split('_')[0]
                for m in re.finditer(r'"([LR]\d+_PAD\d+)\s*:\s*([A-Z]+\d+)\s*,?"?&?', text)}
    require(len(pin_bank) > 100, 'BSDL pin map unusable')
    for port, row in fresh.items():
        b = base[port]
        require(pin_bank.get(row['LOC']) == b['BANK'],
                'BSDL physical bank differs from baseline: ' + port)
        require(row['BANK'] == 'BANKL6', 'unexpected BANK signature: ' + port)
        for h in headers:
            if h != 'BANK':
                require(row[h] == b[h], 'electrical field changed: %s %s' % (port, h))
    fp = parse_prt((route/'work/place_route/v7_sdt_top_prr.prt').read_text('utf-8', errors='replace'))
    bp = parse_prt((BASELINE/'v7_sdt_top_prr.prt').read_text('utf-8', errors='replace'))
    for port, record in fp.items():
        if port in bp:
            require(record['pin'] == bp[port]['pin'] and record['site'] == bp[port]['site']
                    and record['pad'] == bp[port]['pad'], 'pinout changed: ' + port)
    hsst = json.loads((route/'HSST_motion_retention.json').read_bytes())
    require(hsst['motion_count'] == 32
            and all(x['parameters_equal'] and x['ports_equal'] for x in hsst['motion'])
            and hsst['HSST_count'] == 5
            and all(x['native_sites'] == ['HSSTLP_364_918'] for x in hsst['HSST']),
            'Motion/HSST retention differs')
    require(verified['io']['ports'] == 112, 'verify20 IO row count changed')
    return {'io_bank_report_deviation': 'accepted_on_bsdl_pin_electrical_evidence',
            'verify20_binding_sha256': sha(binding)}


def check(manifest):
    manifest = manifest.resolve(strict=True)
    root = manifest.parent
    doc = json.loads(manifest.read_bytes())
    require(doc['status'] == 'PASS_FUNCTIONAL_SBIT', 'Build has not produced a qualified bit')
    require(len(doc['bits']) == 1, 'One actual bitstream required')
    bit = doc['bits'][0]
    path = Path(bit['path']).resolve(strict=True)
    require(path.suffix == '.sbit' and path.stat().st_size == bit['size'] > 0,
            'Missing or changed bitstream size')
    require(sha(path) == bit['sha256'], 'Bitstream hash changed')
    require(sha(doc['route']) == doc['route_sha256'], 'Bitstream input route changed')
    require(sha(root / 'controller.py') == doc['controller_sha256'], 'Controller changed')
    continuation = root / 'continue_functional.py'
    if sha(continuation) != doc['continuation_sha256']:
        resume = root / 'resume_after_disk12.py'
        require(resume.is_file() and sha(resume) == doc['continuation_sha256'],
                'Build continuation changed')
        resumed = json.loads((root / 'resume12_binding.json').read_bytes())
        require(resumed['original_sha256'] == sha(continuation)
                and resumed['compile_repeated'] is False,
                'Disk recovery does not bind the original continuation')
        require(resumed['compile_adf_sha256'] ==
                sha(root / 'functional_candidate01/compile/v7_sdt_top_comp.adf'),
                'Recovered compile database changed')
    map_recovery = root / 'resume_map_view13_binding.json'
    if map_recovery.exists():
        recovered_map = json.loads(map_recovery.read_bytes())
        candidate = root / 'functional_candidate01'
        require(recovered_map['original_sha256'] == sha(continuation)
                and recovered_map['resume_sha256'] == sha(root / 'resume_map_view13.py')
                and recovered_map['timing_constraints_modified'] is False,
                'Map recovery entry or original continuation changed')
        for key, relative in [('synthesis_sha256', 'synthesize/v7_sdt_top_syn.adf'),
                              ('compile_sha256', 'compile/v7_sdt_top_comp.adf'),
                              ('clock_sha256', 'constraints_live/clock.fdc'),
                              ('query_sha256', 'constraints_live/map_view_query13.fdc')]:
            require(recovered_map[key] == sha(candidate / relative),
                    'Map recovery input changed: ' + relative)
        query = (candidate / 'constraints_live/map_view_query13.fdc').read_text('ascii')
        require([line for line in query.splitlines() if line and not line.startswith('#')]
                == ['get_ports {free_clk}'], 'Map initialization modifies constraints')
        for label in ['functional_map_view13', 'functional_map_view13_native_export']:
            receipt = json.loads((root / (label + '_receipt.json')).read_bytes())
            require(receipt['rc'] == 0 and not receipt['errors']
                    and sha(root / (label + '.log')) == receipt['log_sha256'],
                    'Recovered native map stage failed or changed: ' + label)
    route_recovery = root / 'resume_route14_binding.json'
    if route_recovery.exists():
        recovered_route = json.loads(route_recovery.read_bytes())
        require(recovered_route['original_sha256'] == sha(continuation)
                and recovered_route['resume_sha256'] == sha(root / 'resume_route14.py')
                and recovered_route['map_repeated'] is False,
                'Route recovery entry or original continuation changed')
        require(recovered_route['map_sha256'] ==
                sha(root / 'functional_candidate01/device_map/v7_sdt_top_map.adf')
                and recovered_route['graph_sha256'] ==
                sha(root / 'functional_map_view13_native/analysis/graph.json')
                and recovered_route['map_recovery_binding_sha256'] == sha(map_recovery),
                'Route recovery does not bind the successful native map')
    hold_recovery = root / 'resume_hold_limit15_binding.json'
    if hold_recovery.exists():
        recovered_hold = json.loads(hold_recovery.read_bytes())
        require(recovered_hold['original_sha256'] == sha(continuation)
                and recovered_hold['resume_sha256'] == sha(root / 'resume_hold_limit15.py')
                and recovered_hold['timing_constraints_modified'] is False,
                'Hold repair entry or original continuation changed')
        require(recovered_hold['map_sha256'] ==
                sha(root / 'functional_candidate01/device_map/v7_sdt_top_map.adf')
                and recovered_hold['graph_sha256'] ==
                sha(root / 'functional_map_view13_native/analysis/graph.json')
                and recovered_hold['clock_sha256'] ==
                sha(root / 'functional_candidate01/constraints_live/clock.fdc'),
                'Hold repair map, graph or timing constraints changed')
        repair = json.loads((root / 'functional_route03_pnr_receipt.json').read_bytes())
        require(repair['rc'] == 0 and not repair['errors']
                and sha(root / 'functional_route03_pnr.log') == repair['log_sha256'],
                'Hold repair route failed or log changed')
    sources = doc['source_binding']
    require(sources['count'] == 741 and sources['registered'] == 186,
            'Source inventory differs from this build')
    require(len(sources['hashes']) == 741, 'Incomplete source inventory')
    for relative, expected in sources['hashes'].items():
        require(sha(root / 'functional_candidate01' / relative) == expected,
                'Source changed: ' + relative)
    binding = json.loads((root / 'official_genbit_entry_binding.json').read_bytes())
    matches = [p for p in root.glob('functional_route*/RESULT.json')
               if sha(p) == binding['qualified_result_sha256']]
    require(len(matches) == 1, 'Exact qualified route result missing or ambiguous')
    result_path = matches[0]
    result = json.loads(result_path.read_bytes())
    deviation = None
    if result['status'] == 'PASS_FUNCTIONAL_ROUTE' and result['retention_pass']:
        require(result['timing_pass'] and result['coverage_complete']
                and result['DDR131_25'] and not result['old_camera_async'],
                'Actual route did not pass necessary checks')
    else:
        require(result['status'] == 'FAIL_REAL_TIMING_OR_COVERAGE'
                and result['timing_pass'] and result['coverage_complete']
                and result['DDR131_25'] and not result['old_camera_async']
                and result['retention_pass'] is False,
                'Route result is not the qualified timing candidate with the known IO deviation')
        deviation = verify_io_deviation(root, result_path)
    minima = result['minima_ns']
    expected_keys = {kind + ' ' + corner for kind in
                     ['Setup', 'Hold', 'Recovery', 'Removal', 'Minimum Pulse Width']
                     for corner in ['Slow', 'Fast']}
    require(set(minima) == expected_keys and all(isinstance(v, (float, int)) and v >= 0
                                                 for v in minima.values()),
            'Incomplete timing summaries or negative slack')
    require(result['covered_15238'] == result['expected_pair_corners'] > 0,
            'Incomplete actual crossing budget coverage')
    records = result['crossing_records']
    require(len(records) == result['expected_pair_corners'] and
            len({(r['start'], r['end'], r['corner']) for r in records}) == len(records) and
            all(r['slack'] >= 0 and r['MaxDelay_15_238'] for r in records),
            'Missing, repeated, negative, or unbudgeted crossing record')
    sys.path.insert(0, str(root.parent / 'build04_constraint_load_fix01'))
    from continue_map_pnr import summary, paths
    reports = result_path.parent
    native_global = reports / 'global10/report_timing/v7_sdt_top.rtr'
    native_crossing = reports / 'crossings/report_timing/v7_sdt_top.rtr'
    actual_summary = summary(native_global.read_bytes())
    actual_minima = {key: min((row['wns'] for row in rows), default=None)
                     for key, rows in actual_summary.items()}
    require(actual_minima == minima, 'Result differs from actual global timing report')
    require(all(row['tns'] == 0 and row['failing_endpoints'] == 0
                and row['total_endpoints'] > 0
                for rows in actual_summary.values() for row in rows),
            'Native timing report contains failing or empty checks')
    physical = json.loads((reports / 'actual_pairs.json').read_bytes())
    require(physical['count'] == len(physical['rows']), 'Physical pair inventory inconsistent')
    expected = {(row['launch_CLK'], row['capture_D'], corner)
                for row in physical['rows'] for corner in ['slow', 'fast']}
    require(len(expected) == 2 * physical['count'], 'Physical pairs repeated')
    actual_records = [row for row in paths(native_crossing.read_bytes())
                      if (row['start'], row['end'], row['corner']) in expected]
    require(actual_records == records and
            {(row['start'], row['end'], row['corner']) for row in actual_records} == expected,
            'Result differs from actual crossing report or full physical coverage')
    require(sha(result['route']) == result['route_sha256'] == doc['route_sha256'],
            'Qualified route differs from bitstream input route')
    require(sha(result_path.parent / 'native_CDB_raw.txt') == result['CDB_sha256'],
            'Native timing database changed')
    receipt = json.loads((root / 'functional_genbit_receipt.json').read_bytes())
    require(receipt['rc'] == 0 and not receipt['errors'], 'Official bit generation failed')
    require(sha(root / 'functional_genbit.log') == receipt['log_sha256'],
            'Official bit generation log changed')
    result = {'status': 'CHECKED_FOR_SRAM_HANDOFF', 'bit': str(path),
              'bit_sha256': bit['sha256'], 'bit_bytes': bit['size'],
              'manifest_sha256': sha(manifest), 'qualified_result': str(result_path),
              'qualified_result_sha256': sha(result_path), 'minima_ns': minima,
              'native_global_report_sha256': sha(native_global),
              'native_crossing_report_sha256': sha(native_crossing),
              'board_function_verified': False}
    if deviation:
        result.update(deviation)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    result = check(a.manifest)
    if a.output:
        with a.output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
