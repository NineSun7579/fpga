"""Check the actual functional build handoff before SRAM programming."""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


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
    require(result['status'] == 'PASS_FUNCTIONAL_ROUTE' and result['timing_pass']
            and result['retention_pass'] and result['coverage_complete']
            and result['DDR131_25'] and not result['old_camera_async'],
            'Actual route did not pass necessary checks')
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
            len({(r['start'], r['end'], r['corner']) for r in records}) == len(records)
            and all(r['slack'] >= 0 and r['MaxDelay_15_238'] for r in records),
            'Missing, repeated, negative, or unbudgeted crossing record')
    # Re-read native reports with the same preserved parser used by this actual build.
    # Compare the data, rather than relying only on RESULT.json boolean fields.
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
    return {'status': 'CHECKED_FOR_SRAM_HANDOFF', 'bit': str(path),
            'bit_sha256': bit['sha256'], 'bit_bytes': bit['size'],
            'manifest_sha256': sha(manifest), 'qualified_result': str(result_path),
            'qualified_result_sha256': sha(result_path), 'minima_ns': minima,
            'native_global_report_sha256': sha(native_global),
            'native_crossing_report_sha256': sha(native_crossing),
            'board_function_verified': False}


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
