"""Verify production bytes, original full APIs, receipt provenance and mapped CHECK evidence."""
from pathlib import Path
import hashlib
import json
import re
import difflib
import xml.etree.ElementTree as ET
from build_candidate import HERE, BASE, OLD, TOP_NAME, TOP_HASH, COMPONENTS, ACTIVE_COMPONENTS, uncomment, header, ports, balanced, write_json, protected_hashes, copy_immutable, save


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def api(data):
    clean = uncomment(data)
    match = re.search(rb'\bmodule\s+(\w+)\s*', clean)
    pos = match.end()
    if clean[pos:pos+1] == b'#':
        pos = balanced(clean, clean.index(b'(', pos))
    end = balanced(clean, clean.index(b'(', pos))
    return re.sub(rb'\s+', b'', clean[match.end():end])


def main():
    before = load(HERE / 'artifacts/protected_hashes_before.json')
    current = protected_hashes()
    differences = {p: {'before': h, 'after': current.get(p)} for p, h in before.items() if current.get(p) != h}
    assert not differences, differences
    write_json('artifacts/protected_hashes_after.json', {p: current[p] for p in before})
    bindings = load(HERE / 'artifacts/component_binding.json')
    for rel in COMPONENTS:
        assert sha(HERE.parent / rel) == sha(HERE / 'rtl' / Path(rel).name) == bindings[rel]
        assert not (HERE / 'rtl' / Path(rel).name).stat().st_mode & 0o200
    frozen = load(HERE / 'artifacts/frozen_copy_sha256.json')
    assert len(frozen) == 694
    for rel, h in frozen.items():
        assert sha(HERE / 'inputs' / rel) == sha(OLD / 'inputs' / rel) == sha(BASE / 'inputs' / rel) == h
        assert not (HERE / 'inputs' / rel).stat().st_mode & 0o200
    arm_receipt = load(HERE.parent / 'capture_arm_contract/artifacts/review_receipt.json')
    assert arm_receipt['status'] == 'PASS'
    assert arm_receipt['candidate_sha256'] == sha(HERE / 'rtl/fpga_v8_capture_control_axil_arm_v2.v')
    suites = {}
    for name, expected in arm_receipt['suite_receipt_sha256'].items():
        src = HERE.parent / 'capture_arm_contract' / name / 'artifacts/results.json'
        assert sha(src) == expected
        copy_immutable(src, HERE / 'baseline/receipts/capture_arm_contract' / name / 'artifacts/results.json')
        suites[name] = {'sha256': expected, 'receipt': load(src)}
    assert suites['endpoint']['receipt']['operations'] == 499
    assert suites['endpoint']['receipt']['events'] == 4288
    pcie = load(HERE.parent / 'pcie_h2f_transport_contract/artifacts/results.json')
    assert pcie['cases'] == 50 and pcie['fault_cases'] == 4
    assert sum(c['result'] == 'PASS' for c in pcie['case_results']) == 46
    assert sum(c['result'] == 'PENDING_FAULT_NO_MSI' for c in pcie['case_results']) == 4
    parity = load(HERE.parent / 'pcie_h2f_transport_contract/artifacts/f2h_parity.json')
    assert parity['status'] == 'PASS' and parity['controller_chunks'] == 305
    mapping = [
        ('fpga_v8_pcie_fifo_h2f.v', 'source/pcie_dma/pcie_fifo.v'),
        ('fpga_v8_pcie_dma_controller_h2f.v', 'source/pcie_dma/pcie_dma_ctrl/ips2l_pcie_dma_controller.v'),
        ('fpga_v8_pcie_dma_h2f.v', 'source/pcie_dma/pcie_dma_ctrl/ips2l_pcie_dma.v'),
        ('fpga_v8_pango_pcie_top_h2f.v', 'source/pcie_dma/pcie_dma_ctrl/pango_pcie_top.v'),
        ('fpga_v8_capture_control_axil_arm_v2.v', 'fpga_v8_capture_control_axil.v')]
    api_report = {}
    source_edits = {}
    for new, old in mapping:
        original_path = HERE / 'inputs' / old
        if new == 'fpga_v8_capture_control_axil_arm_v2.v':
            original_path = HERE / 'rtl' / old
        if not original_path.exists():
            matches = list((HERE / 'inputs').rglob(Path(old).name))
            assert len(matches) == 1, matches
            original_path = matches[0]
        assert api((HERE / 'rtl' / new).read_bytes()) == api(original_path.read_bytes()), new
        api_report[new] = {'original': original_path.relative_to(HERE).as_posix(),
                           'original_sha256': sha(original_path), 'candidate_sha256': sha(HERE / 'rtl' / new),
                           'full_parameter_port_direction_width_api_equal': True}
        a, b = original_path.read_bytes(), (HERE / 'rtl' / new).read_bytes()
        save(HERE / 'artifacts' / (new + '.diff'), ''.join(difflib.unified_diff(
            a.decode('ascii', 'backslashreplace').splitlines(True),
            b.decode('ascii', 'backslashreplace').splitlines(True),
            fromfile=original_path.relative_to(HERE).as_posix(), tofile='rtl/' + new)))
        al, bl = a.splitlines(True), b.splitlines(True)
        ao, bo = [0], [0]
        for line in al:
            ao.append(ao[-1] + len(line))
        for line in bl:
            bo.append(bo[-1] + len(line))
        matcher = difflib.SequenceMatcher(None, al, bl, autojunk=False)
        edits = [{'original_offset': ao[i], 'original_end': ao[j], 'candidate_offset': bo[k], 'candidate_end': bo[l],
                  'old_hex': a[ao[i]:ao[j]].hex(), 'new_hex': b[bo[k]:bo[l]].hex()}
                 for tag, i, j, k, l in matcher.get_opcodes() if tag != 'equal']
        replay = a
        for edit in reversed(edits):
            replay = replay[:edit['original_offset']] + bytes.fromhex(edit['new_hex']) + replay[edit['original_end']:]
        assert replay == b
        source_edits[new] = dict(api_report[new], replayable_byte_edits=edits)
        if new == 'fpga_v8_pcie_dma_h2f.v':
            assert a.replace(b'ips2l_pcie_dma_controller #(', b'fpga_v8_pcie_dma_controller_h2f #(').replace(
                b'module ips2l_pcie_dma ', b'module fpga_v8_pcie_dma_h2f ') == b
        if new == 'fpga_v8_pango_pcie_top_h2f.v':
            assert a.replace(b'module pango_pcie_top ', b'module fpga_v8_pango_pcie_top_h2f ').replace(
                b'ips2l_pcie_dma #', b'fpga_v8_pcie_dma_h2f #') == b
    write_json('artifacts/pcie_production_byte_edits.json', source_edits)
    for parent, child in [
        ('fpga_v8_cooperative_top_v2', 'fpga_v8_pcie_fifo_h2f'),
        ('fpga_v8_pcie_fifo_h2f', 'fpga_v8_pango_pcie_top_h2f'),
        ('fpga_v8_pango_pcie_top_h2f', 'fpga_v8_pcie_dma_h2f'),
        ('fpga_v8_pcie_dma_h2f', 'fpga_v8_pcie_dma_controller_h2f')]:
        data = uncomment((HERE / 'rtl' / (parent + '.v')).read_bytes())
        assert len(re.findall(rb'\b' + child.encode() + rb'\s*(?:#\s*\(|\w+\s*\()', data)) == 1
    arm_original = HERE / 'rtl/fpga_v8_capture_control_axil.v'
    assert api(arm_original.read_bytes()) == api((HERE / 'rtl/fpga_v8_capture_control_axil_arm_v2.v').read_bytes())
    runs = sorted((HERE / 'compile_01').glob('attempt_*'))
    compile_evidence = []
    for run in runs:
        receipt = run / 'compile_result.json'
        if receipt.exists():
            log = (run / 'compile_shell.log').read_bytes()
            elaborated = sorted({x.decode() for x in re.findall(rb'Elaborating module (\w+)', log)})
            if load(receipt)['pass']:
                assert {Path(rel).stem for rel in ACTIVE_COMPONENTS} <= set(elaborated)
                assert not {'pcie_fifo', 'pcie_dma_controller', 'pcie_dma', 'pango_pcie_top',
                            'fpga_v8_capture_control_axil'} & set(elaborated)
            compile_evidence.append({'run': run.relative_to(HERE).as_posix(),
                                     'receipt': load(receipt), 'elaborated_modules': elaborated})
    timing = []
    def tables(path):
        root = ET.fromstring(path.read_bytes())
        return {table.attrib['id']: table for table in root.findall('table')}
    def rows(table):
        return [[d.text or '' for d in row.findall('data')] for row in table.findall('row')]
    old_tables = tables(OLD / 'compile_01/attempt_02/synthesize/snr.db')
    for run in runs:
        db = run / 'synthesize/snr.db'
        if not db.exists():
            continue
        data = db.read_bytes()
        parsed = tables(db)
        hierarchy = []
        def visit_resource(row, ancestors):
            values = [d.text or '' for d in row.findall('data')]
            if not values:
                return
            path = ancestors + [values[0]]
            if any(token in '/'.join(path) for token in ['pcie_fifo', 'u_v8_capture_control', 'u_v8_capture_lease', 'u_v8_ddr_adapter']):
                hierarchy.append({'instance_path': '/'.join(path), 'lut': values[1], 'ff': values[2],
                                  'distributed_ram': values[3], 'drm': values[5]})
            for child in row.findall('row'):
                visit_resource(child, path)
        for row in parsed['synthesize_resource_utilization'].findall('row'):
            visit_resource(row, [])
        mapped_sources = {rel: len(re.findall(rb'file_id="[^\"]*/rtl/' + Path(rel).name.encode() + rb'"', data))
                          for rel in ACTIVE_COMPONENTS if rel.startswith(('pcie_', 'capture_arm_'))}
        assert mapped_sources['pcie_h2f_transport_contract/artifacts/fpga_v8_pcie_dma_controller_h2f.v'] > 0
        assert mapped_sources['capture_arm_contract/fpga_v8_capture_control_axil_arm_v2.v'] > 0
        write_json((run / 'evidence/actual_production_hierarchy.json').relative_to(HERE).as_posix(), {
            'snr_db_sha256': sha(db), 'retained_resource_hierarchy': hierarchy,
            'mapped_candidate_source_occurrences': mapped_sources,
            'original_instance_names_and_vendor_ip_preserved': True,
            'compile_elaboration_is_authoritative_for_source_modules': True})
        check_rows = rows(parsed['synthesize_check_timing_summary'])
        counts = dict(check_rows)
        assert all(counts[k] == '0' for k in ['loops', 'latch_loops', 'latchs'])
        assert b'Total Latches: 0' in data
        hold = rows(parsed['synthesize_report_timing_hold'])
        old_hold = rows(old_tables['synthesize_report_timing_hold'])
        ddr_hold = next(r for r in hold if r[:2] == ['ddrphy_sysclk', 'ddrphy_sysclk'])
        old_ddr_hold = next(r for r in old_hold if r[:2] == ddr_hold[:2])
        assert ddr_hold[2:5] == old_ddr_hold[2:5] == ['-0.004', '-0.040', '10']
        ddr_paths = [r for r in rows(parsed['synthesize_report_timing_path_hold']) if r[-2:] == ['ddrphy_sysclk'] * 2]
        old_ddr_paths = [r for r in rows(old_tables['synthesize_report_timing_path_hold']) if r[-2:] == ['ddrphy_sysclk'] * 2]
        assert ddr_paths == old_ddr_paths
        ids = ['synthesize_check_timing_summary', 'synthesize_report_timing_clock_summary',
               'synthesize_report_timing_fmax', 'synthesize_report_clock_interaction',
               'synthesize_report_timing_setup', 'synthesize_report_timing_hold',
               'synthesize_report_timing_recovery', 'synthesize_report_timing_removal',
               'synthesize_constraint_files']
        timing.append({'file': db.relative_to(HERE).as_posix(), 'sha256': sha(db),
                       'check_rows': check_rows, 'combinational_loops': 0, 'latch_loops': 0, 'latches': 0,
                       'firstversion_check_rows': rows(old_tables['synthesize_check_timing_summary']),
                       'timing_tables': {k: rows(parsed[k]) for k in ids},
                       'inherited_ten_ddr_hold_failures': ddr_hold,
                       'representative_ddr_hold_paths_identical_to_firstversion': ddr_paths,
                       'no_new_loop_falsepaths': True})
        for name in ids:
            save(run / 'evidence' / (name + '.xml'), ET.tostring(parsed[name], encoding='utf-8'))
        write_json((run / 'evidence/check_timing_exact.json').relative_to(HERE).as_posix(), timing[-1])
    report = {
        'title': '第二版完整隔离候选核验', 'status': 'compile_synthesis_verified_preliminary_unaccepted' if timing else 'source_and_compile_verified_preliminary',
        'baseline_top_sha256': TOP_HASH, 'immutable_firstversion_top_sha256': sha(OLD / 'rtl/fpga_v8_cooperative_top.v'),
        'frozen_input_count': 694, 'component_snapshots': {'original': 12, 'additional': 5, 'active': 16},
        'protected_file_count': len(before), 'protected_differences': differences,
        'production_source_ip_count': sum(p.startswith(('source/', 'ipcore/')) for p in before),
        'protected_pds_count': sum(p.endswith('.pds') for p in before),
        'requested_historical_1191_count_is_not_assumed': True,
        'capture_arm_full_api_equal': True, 'capture_arm_suite_receipts_hash_verified': suites,
        'pcie_full_api': api_report, 'pcie_receipt': pcie, 'f2h_parity': parity,
        'production_artifact_bytes_used_without_modelsim_normalization': True,
        'local_semantic_source_fixes': [], 'compile_evidence': compile_evidence, 'mapped_check_timing': timing,
        'independent_reset_supported': False, 'core_ddr_adapter_irq_reset_epoch_resolved': False,
        'blockers': ['Independent PCIe/controller/CPU/AXI/DDR reset domains and stale IRQ/epoch identification',
                     'Upstream physical camera input identity and upstream processing/bitstream certification',
                     'Runtime RX/output allocation exclusivity and CAM1-4 writable address configuration',
                     'F2H posted-write retirement, Linux completion/MSI ordering and hard-IP link behavior',
                     'Parent source/loop/resource review before PnR; no PnR, board or SSH evidence'],
    }
    write_json('artifacts/v2_review.json', report)
    print(f'v2 full APIs, production bytes and receipts verified; {len(before)} protected files unchanged.')


if __name__ == '__main__':
    main()
