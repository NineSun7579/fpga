"""V5 verification uses the same routed/source/physical acceptance gates."""
import json
from pathlib import Path
from run_whole import M, WORK, HERE, sha


def main():
    from audit_binding import main as audit_binding
    # Read-only source validation also refreshes its deterministic receipt.
    audit_binding()
    camera = json.loads((WORK / 'regression_receipts/camera.json').read_bytes())
    adapter = json.loads((WORK / 'regression_receipts/adapter.json').read_bytes())
    motion = json.loads((WORK / 'regression_receipts/motion.json').read_bytes())
    assert camera['passed'] and len(camera['runs']) == 12
    assert adapter['status'] == 'PASS'
    assert motion['passed'] and motion['four_camera_integration_passed']
    assert all(sha(Path(p)) == h for p, h in camera['file_sha256'].items())
    assert all(sha(Path(p)) == h for p, h in motion['file_sha256'].items())
    assert all(sha(M.parent / p) == h for p, h in adapter['source_sha256'].items())
    assert all(sha(HERE / 'adapter_artifacts' / p) == h for p, h in adapter['artifact_sha256'].items())
    manifest = json.loads((WORK / 'delivery_manifest.json').read_bytes())
    required = {'exact_binding_verification.json'} | {
        str(Path('regression_receipts') / name) for name in ['camera.json', 'adapter.json', 'motion.json']}
    assert required <= manifest['evidence'].keys(), 'Missing TC03 delivery evidence'
    for name, receipt, field in [
        ('ov5640_cdc_tc03.v', camera, 'file_sha256'),
        ('fpga_v8_ddr_adapter_tc03.v', adapter, 'source_sha256'),
        ('block_motion_detector_tc03.v', motion, 'file_sha256'),
    ]:
        hashes = [h for p, h in receipt[field].items() if p.replace('\\', '/').endswith('/rtl/' + name)]
        assert len(hashes) == 1 and sha(WORK / 'rtl' / name) == hashes[0], name
    original = M / 'timing_correction_02/verify_delivery.py'
    source = original.read_bytes()
    old = b'# FPGA cooperative V4 bitstream'
    assert source.count(old) == 1
    source = source.replace(old, b'# FPGA cooperative V5 bitstream')
    scope = {'__name__': 'v5_verifier', '__file__': str(original)}
    exec(compile(source, str(original), 'exec'), scope)
    scope['main']()
    # Audit uses V4's actual exported pin rows rather than V3's table wrapper.
    original = M / 'timing_correction_02/audit_acceptance.py'
    source = original.read_bytes()
    for old, new in [
        (b"BASE / 'evidence_02/stage_tables.json'", b"BASE / 'evidence/stage_tables.json'"),
        (b"baseline['place_route']['tables']['pnr_io_report']['rows']", b"baseline['place_route']['pnr_io_report']['rows']"),
    ]:
        assert source.count(old) == 1
        source = source.replace(old, new)
    scope = {'__name__': 'v5_acceptance_auditor', '__file__': str(original)}
    exec(compile(source, str(original), 'exec'), scope)
    scope['main']()
    print('V5 delivery and independent acceptance verified', flush=True)


if __name__ == '__main__':
    main()
