"""Audit raw delivery evidence independently, after verify_delivery succeeds."""
import json
import re
from pathlib import Path
from run_whole import WORK, BASE, sha, inventory


def read(name):
    return json.loads((WORK / name).read_bytes())


def main():
    assert read('delivery_verification.json')['verified']
    manifest = read('delivery_manifest.json')
    assert manifest['sources'] == inventory() == read('inputs_before.json') == read('inputs_after.json')
    assert read('baseline_guard.json')['unchanged']
    assert all(s['exit_code'] == 0 for s in read('flow_result.json')['stages'])
    binding = read('binding_audit.json')
    assert binding['unchanged_input_files'] == 694
    for key in ['exact_top_instance_replacements_only', 'external_top_api_unchanged',
                'six_camera_connections_unchanged', 'motion_connections_unchanged']:
        assert binding[key], key
    for name, digest in binding['unchanged_constraints'].items():
        assert sha(WORK / name) == digest, name

    # Compare the physical pin rows themselves, not only a recorded pass flag.
    pins = read('evidence/stage_tables.json')['place_route']['pnr_io_report']['rows']
    baseline = json.loads((BASE / 'evidence_02/stage_tables.json').read_bytes())
    assert pins and pins == baseline['place_route']['tables']['pnr_io_report']['rows']

    # Reparse the original PDS report and check every scored clock-pair row.
    sta = read('evidence/final_sta_summary.json')
    report_path = Path(sta['report'])
    assert sha(report_path) == sta['report_sha256']
    report = report_path.read_bytes().decode('ascii', 'backslashreplace')
    groups = {}
    pattern = r'(Setup|Hold|Recovery|Removal|Minimum Pulse Width) Summary\((Slow|Fast) Corner\):(.*?)(?=^=+)'
    for match in re.finditer(pattern, report, re.M | re.S):
        kind, corner, block = match.groups()
        key = (kind, corner)
        assert key not in groups
        rows = []
        for line in block.splitlines():
            cols = line.split()
            pos = 1 if kind == 'Minimum Pulse Width' else 2
            if len(cols) == pos + 4 and re.fullmatch(r'-?\d+\.\d+', cols[pos]):
                slack, tns = map(float, cols[pos:pos + 2])
                failures, endpoints = map(int, cols[pos + 2:pos + 4])
                assert slack >= 0 and tns == 0 and failures == 0 and endpoints > 0, line
                rows.append(cols)
        assert rows, key
        groups[key] = rows
    expected = {(kind, corner) for kind in ['Setup', 'Hold', 'Recovery', 'Removal', 'Minimum Pulse Width']
                for corner in ['Slow', 'Fast']}
    assert set(groups) == expected
    assert not re.search(r'Slack \(VIOLATED\)\s+-[0-9.]+', report)
    assert all(len(groups[(s['section'], s['corner'])]) == len(s['rows'])
               for s in sta['all_corner_summaries'])

    transport = read('regression_receipts/transport.json')
    cases = transport['case_results']
    assert transport['cases'] == len(cases) == 50
    assert sum(c['result'] == 'PASS' for c in cases) == 46
    faults = [c for c in cases if c['result'] == 'PENDING_FAULT_NO_MSI']
    assert len(faults) == transport['fault_cases'] == 4
    assert all(c['msi'] == 0 and c['final_b_credits'] == 0 for c in faults)
    fifo = read('regression_receipts/fifo_binding.json')
    assert sha(WORK / 'rtl/fpga_v8_pcie_fifo_h2f_tc02.v') == fifo['candidate_sha256']
    dma = read('regression_receipts/dma.json')
    assert dma['cases'] == 160 and dma['wait_for_data_modes'] == [0, 1]
    assert dma['public_outputs_and_internal_beat_count_match']
    assert sha(WORK / 'rtl/axi_dma_write_tc02.v') == dma['candidate_sha256']
    guard = read('regression_receipts/reset_guard.json')
    assert guard['passed_cases'] == 9
    assert sha(WORK / 'rtl/fpga_v8_reset_fault_guard_02.v') == guard['source_sha256']
    integrated = read('regression_receipts/guarded_fifo.json')
    assert len(set(integrated['passed'])) == 5 and integrated['source_unchanged']
    assert all(sha(Path(p)) == h for p, h in integrated['source_hashes'].items())
    assert manifest['programming_performed'] is False and manifest['board_verified'] is False
    result = {'passed': True, 'raw_timing_groups': len(groups), 'physical_pin_rows': len(pins),
              'transport_cases': 50, 'dma_cases': 160, 'reset_cases': 9, 'integration_cases': 5,
              'programming_performed': False, 'board_operation_verified': False,
              'evidence_hashes': {name: sha(WORK / name) for name in
                  ['delivery_verification.json', 'delivery_manifest.json', 'evidence/stage_tables.json']},
              'raw_report_sha256': sha(report_path), 'audit_script_sha256': sha(Path(__file__))}
    (WORK / 'acceptance_audit.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
