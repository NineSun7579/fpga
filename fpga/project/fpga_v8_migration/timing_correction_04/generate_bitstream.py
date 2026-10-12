"""Generate V6 locally after routed and regression gates; never program hardware."""
import json
from pathlib import Path
from run_whole import HERE, M, WORK, sha


def verify_regressions():
    receipt = json.loads((HERE / 'regression_acceptance.json').read_bytes())
    assert receipt['passed']
    assert all(sha(Path(p)) == h for p, h in receipt['file_sha256'].items())
    assert all(sha(WORK / 'rtl' / (name + '.v')) == digest
               for name, digest in receipt['candidate_sha256'].items())
    adapter = json.loads((M / 'timing_correction_03/adapter_artifacts/adapter_results.json').read_bytes())
    assert adapter['status'] == 'PASS'
    assert all(sha(M.parent / p) == h for p, h in adapter['source_sha256'].items())
    assert all(sha(M / 'timing_correction_03/adapter_artifacts' / p) == h
               for p, h in adapter['artifact_sha256'].items())
    assert sha(WORK / 'rtl/fpga_v8_ddr_adapter_tc03.v') == adapter['source_sha256']['fpga_v8_migration/timing_correction_03/rtl/fpga_v8_ddr_adapter_tc03.v']
    motion = json.loads((M / 'timing_correction_03/motion_acceptance.json').read_bytes())
    assert motion['passed'] and motion['four_camera_integration_passed']
    assert all(sha(Path(p)) == h for p, h in motion['file_sha256'].items())
    assert sha(WORK / 'rtl/block_motion_detector_tc03.v') == motion['file_sha256'][str(M / 'timing_correction_03/rtl/block_motion_detector_tc03.v')]
    return receipt


def main():
    from audit_binding import main as audit_binding
    audit_binding()
    verify_regressions()
    # Retain the original timing, physical, FIFO and reset generation gates.
    original = M / 'timing_correction_02/generate_bitstream.py'
    source = original.read_bytes()
    replacements = [
        (b"tests=Path(__file__).resolve().parent", b"tests=M/'timing_correction_02'"),
        (b"dma=json.loads((tests/'dma_artifacts/results.json').read_bytes())\n    assert dma['cases']==160 and dma['wait_for_data_modes']==[0,1] and dma['public_outputs_and_internal_beat_count_match']\n    assert sha(WORK/'rtl/axi_dma_write_tc02.v')==dma['candidate_sha256']",
         b"dma=json.loads((M/'timing_correction_04/receipts/dma/results.json').read_bytes())\n    assert dma['status']=='PASS' and dma['original_cases']==160\n    assert sha(WORK/'rtl/axi_dma_write_tc04.v')==dma['candidate_sha256']"),
        (b"'dma.json':tests/'dma_artifacts/results.json'", b"'dma.json':M/'timing_correction_04/receipts/dma/results.json'"),
    ]
    for old, new in replacements:
        assert source.count(old) == 1, old
        source = source.replace(old, new)
    scope = {'__name__': 'v6_generator', '__file__': str(original)}
    exec(compile(source, str(original), 'exec'), scope)
    scope['main']()
    manifest_path = WORK / 'delivery_manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    copies = {
        'tc04_acceptance.json': HERE / 'regression_acceptance.json',
        'camera.json': HERE / 'camera_artifacts/results.json',
        'lease.json': HERE / 'receipts/lease/results.json',
        'stream_capture.json': HERE / 'receipts/stream_capture/results.json',
        'stream_capture_audit.json': HERE / 'receipts/stream_capture/final_audit.json',
        'cam6.json': HERE / 'receipts/cam6/results.json',
        'cam6_audit.json': HERE / 'receipts/cam6/final_audit.json',
        'dma_audit.json': HERE / 'receipts/dma/final_audit.json',
        'adapter_tc03.json': M / 'timing_correction_03/adapter_artifacts/adapter_results.json',
        'motion_tc03.json': M / 'timing_correction_03/motion_acceptance.json',
    }
    for name, path in copies.items():
        target = WORK / 'regression_receipts' / name
        target.write_bytes(path.read_bytes())
        manifest['evidence'][str(target.relative_to(WORK))] = sha(target)
    for name in ['exact_binding_verification.json', 'evidence/stage_tables.json', 'exporter_reuse.json', 'project.pds']:
        manifest['evidence'][name] = sha(WORK / name)
    manifest['candidate_revision'] = 'V6'
    manifest_path.write_text(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
