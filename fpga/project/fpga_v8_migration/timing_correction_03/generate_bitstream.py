"""V5 local generation, requiring all inherited and new regression evidence."""
from pathlib import Path
import json
import hashlib
from run_whole import M, HERE, WORK, sha


def main():
    camera = json.loads((HERE / 'camera_artifacts/results.json').read_bytes())
    adapter = json.loads((HERE / 'adapter_artifacts/adapter_results.json').read_bytes())
    motion = json.loads((HERE / 'motion_acceptance.json').read_bytes())
    assert camera['passed'] and len(camera['runs']) == 12
    assert adapter['status'] == 'PASS'
    assert motion['passed'] and motion['four_camera_integration_passed']
    assert all(sha(Path(p)) == h for p, h in camera['file_sha256'].items())
    assert all(sha(M.parent / p) == h for p, h in adapter['source_sha256'].items())
    assert all(sha(HERE / 'adapter_artifacts' / p) == h for p, h in adapter['artifact_sha256'].items())
    assert all(sha(Path(p)) == h for p, h in motion['file_sha256'].items())
    for name, digest in [
        ('ov5640_cdc_tc03.v', camera['file_sha256'][str(HERE / 'rtl/ov5640_cdc_tc03.v')]),
        ('fpga_v8_ddr_adapter_tc03.v', adapter['source_sha256']['fpga_v8_migration/timing_correction_03/rtl/fpga_v8_ddr_adapter_tc03.v']),
        ('block_motion_detector_tc03.v', motion['file_sha256'][str(HERE / 'rtl/block_motion_detector_tc03.v')]),
    ]:
        assert sha(WORK / 'rtl' / name) == digest, name
    original = M / 'timing_correction_02/generate_bitstream.py'
    source = original.read_bytes()
    old = b"tests=Path(__file__).resolve().parent"
    assert source.count(old) == 1
    source = source.replace(old, b"tests=M/'timing_correction_02'")
    scope = {'__name__': 'v5_generator', '__file__': str(original)}
    exec(compile(source, str(original), 'exec'), scope)
    scope['main']()
    receipts = {'camera.json': HERE / 'camera_artifacts/results.json',
                'adapter.json': HERE / 'adapter_artifacts/adapter_results.json',
                'motion.json': HERE / 'motion_acceptance.json'}
    manifest_path = WORK / 'delivery_manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    for name, path in receipts.items():
        target = WORK / 'regression_receipts' / name
        target.write_bytes(path.read_bytes())
        manifest['evidence'][str(target.relative_to(WORK))] = sha(target)
    manifest['evidence']['exact_binding_verification.json'] = sha(WORK / 'exact_binding_verification.json')
    manifest['candidate_revision'] = 'V5'
    manifest['generator_reuse'] = {'source': str(original), 'source_sha256': sha(original),
                                  'executed_sha256': hashlib.sha256(source).hexdigest()}
    manifest_path.write_text(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
