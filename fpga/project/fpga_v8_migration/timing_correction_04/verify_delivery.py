"""Independent V6 delivery verification, raw STA audit and regression binding."""
import json
import re
from pathlib import Path
from run_whole import HERE, M, WORK, BASE, MODULES, sha
from generate_bitstream import verify_regressions


def main():
    reviewed = verify_regressions()
    elaboration = json.loads((WORK / 'actual_elaboration.json').read_bytes())
    compile_log = WORK / 'compile/run.log'
    assert elaboration['passed'] and sha(compile_log) == elaboration['compile_log_sha256']
    actual = {name.decode('ascii') for name in re.findall(rb'Elaborating module (\w+)', compile_log.read_bytes())}
    expected = {new for new, oldpath in MODULES.values()} | {
        'block_motion_detector_tc03', 'fpga_v8_ddr_adapter_tc03',
        'fpga_v8_pcie_fifo_h2f_tc02', 'fpga_v8_reset_fault_guard_02'}
    assert expected <= actual and not set(MODULES) & actual
    assert actual == set(elaboration['elaborated'])
    assert json.loads((WORK / 'regression_receipts/tc04_acceptance.json').read_bytes()) == reviewed
    manifest = json.loads((WORK / 'delivery_manifest.json').read_bytes())
    required = {'exact_binding_verification.json', 'evidence/stage_tables.json', 'exporter_reuse.json',
                'project.pds', 'parent_handoff.json', 'actual_elaboration.json', 'binding_audit.json',
                'flow_result.json', 'structural_gate.json', 'baseline_guard.json',
                'evidence/final_sta_summary.json', 'evidence/all_reported_failing_paths.json',
                'evidence/hsst_actual_phy_audit.json', 'evidence/motion_routed_resource_proof.json',
                'final_export_result.json', 'bitstream_result.json', str(Path('bitstream_01') / 'bitgen.log')}
    required |= {str(Path('regression_receipts') / name) for name in [
        'tc04_acceptance.json', 'camera.json', 'lease.json', 'stream_capture.json',
        'stream_capture_audit.json', 'cam6.json', 'cam6_audit.json', 'dma.json', 'dma_audit.json',
        'adapter_tc03.json', 'motion_tc03.json', 'transport.json', 'fifo_binding.json',
        'guarded_fifo.json', 'reset_guard.json']}
    assert {p.replace('\\', '/') for p in required} <= {
        p.replace('\\', '/') for p in manifest['evidence']}, 'Missing V6 evidence'
    originals = {
        'camera.json': HERE / 'camera_artifacts/results.json',
        'lease.json': HERE / 'receipts/lease/results.json',
        'stream_capture.json': HERE / 'receipts/stream_capture/results.json',
        'stream_capture_audit.json': HERE / 'receipts/stream_capture/final_audit.json',
        'cam6.json': HERE / 'receipts/cam6/results.json',
        'cam6_audit.json': HERE / 'receipts/cam6/final_audit.json',
        'dma.json': HERE / 'receipts/dma/results.json',
        'dma_audit.json': HERE / 'receipts/dma/final_audit.json',
        'adapter_tc03.json': M / 'timing_correction_03/adapter_artifacts/adapter_results.json',
        'motion_tc03.json': M / 'timing_correction_03/motion_acceptance.json',
    }
    for name, original in originals.items():
        assert (WORK / 'regression_receipts' / name).read_bytes() == original.read_bytes(), name
    from audit_binding import main as audit_binding
    audit_binding()
    adapter = json.loads((WORK / 'regression_receipts/adapter_tc03.json').read_bytes())
    assert adapter['status'] == 'PASS'
    assert all(sha(M.parent / p) == h for p, h in adapter['source_sha256'].items())
    assert all(sha(M / 'timing_correction_03/adapter_artifacts' / p) == h
               for p, h in adapter['artifact_sha256'].items())
    adapter_hash = adapter['source_sha256']['fpga_v8_migration/timing_correction_03/rtl/fpga_v8_ddr_adapter_tc03.v']
    assert sha(WORK / 'rtl/fpga_v8_ddr_adapter_tc03.v') == adapter_hash
    motion = json.loads((WORK / 'regression_receipts/motion_tc03.json').read_bytes())
    assert motion['passed'] and motion['four_camera_integration_passed']
    assert all(sha(Path(p)) == h for p, h in motion['file_sha256'].items())
    assert sha(WORK / 'rtl/block_motion_detector_tc03.v') == motion['file_sha256'][str(M / 'timing_correction_03/rtl/block_motion_detector_tc03.v')]
    original = M / 'timing_correction_02/verify_delivery.py'
    source = original.read_bytes().replace(b'# FPGA cooperative V4 bitstream', b'# FPGA cooperative V6 bitstream')
    scope = {'__name__': 'v6_verifier', '__file__': str(original)}
    exec(compile(source, str(original), 'exec'), scope)
    scope['main']()
    original = M / 'timing_correction_02/audit_acceptance.py'
    source = original.read_bytes()
    replacements = [
        (b"binding[key], key", b"json.loads((WORK/'exact_binding_verification.json').read_bytes()).get(key, binding.get(key)), key"),
        (b"'exact_top_instance_replacements_only'", b"'exact_instance_replacements_only'"),
        (b"BASE / 'evidence_02/stage_tables.json'", b"BASE / 'evidence/stage_tables.json'"),
        (b"baseline['place_route']['tables']['pnr_io_report']['rows']", b"baseline['place_route']['pnr_io_report']['rows']"),
        (b"assert dma['cases'] == 160 and dma['wait_for_data_modes'] == [0, 1]\n    assert dma['public_outputs_and_internal_beat_count_match']\n    assert sha(WORK / 'rtl/axi_dma_write_tc02.v') == dma['candidate_sha256']",
         b"assert dma['status'] == 'PASS' and dma['original_cases'] == 160\n    assert dma['all_public_outputs_including_invalid_payloads']\n    assert sha(WORK / 'rtl/axi_dma_write_tc04.v') == dma['candidate_sha256']"),
    ]
    for old, new in replacements:
        assert source.count(old) == 1, old
        source = source.replace(old, new)
    scope = {'__name__': 'v6_acceptance_auditor', '__file__': str(original)}
    exec(compile(source, str(original), 'exec'), scope)
    scope['main']()
    print('V6 delivery and independent acceptance verified', flush=True)


if __name__ == '__main__':
    main()
