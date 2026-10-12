"""Exact, count-checked TC04 adaptations; no global version replacement."""
import hashlib
from run_whole import M, save

TC04 = M / 'timing_correction_04'
CONTEXT = (b'from run_whole import HERE, M, WORK, sha',
           b'from run_whole import HERE, M, WORK, sha\nHERE = M / "timing_correction_04"\nfrom accept_regressions import verify_detector')
OLD_DETECTOR_HASH = b"assert sha(WORK / 'rtl/block_motion_detector_tc03.v') == motion['file_sha256'][str(M / 'timing_correction_03/rtl/block_motion_detector_tc03.v')]"
EDITS = {
    'export_whole.py': [
        (b"'block_motion_detector_tc03','ovreg_axil_decode_tc01'", b"'block_motion_detector_tc05','ovreg_axil_decode_tc01'"),
        (b"'block_motion_detector_tc01','ov5640_cdc'", b"'block_motion_detector_tc01','block_motion_detector_tc03','block_motion_detector','ov5640_cdc'"),
    ],
    'generate_bitstream.py': [
        CONTEXT,
        (OLD_DETECTOR_HASH, b'verify_detector(WORK)'),
        (b"manifest['candidate_revision'] = 'V6'", b"manifest['candidate_revision'] = 'V7'"),
    ],
    'verify_delivery.py': [
        (b'from run_whole import HERE, M, WORK, BASE, MODULES, sha',
         b'from run_whole import HERE, M, WORK, BASE, MODULES, sha, REQUIRED, FORBIDDEN\nHERE = M / "timing_correction_04"\nfrom accept_regressions import verify_detector'),
        (b"expected = {new for new, oldpath in MODULES.values()} | {\n        'block_motion_detector_tc03', 'fpga_v8_ddr_adapter_tc03',\n        'fpga_v8_pcie_fifo_h2f_tc02', 'fpga_v8_reset_fault_guard_02'}",
         b'expected = REQUIRED'),
        (b'assert expected <= actual and not set(MODULES) & actual', b'assert expected <= actual and not FORBIDDEN & actual'),
        (OLD_DETECTOR_HASH, b'verify_detector(WORK)'),
        (b"b'# FPGA cooperative V6 bitstream'", b"b'# FPGA cooperative V7 bitstream'"),
        (b"print('V6 delivery and independent acceptance verified'", b"print('V7 delivery and independent acceptance verified'"),
    ],
}


def transformed(name):
    path = TC04 / name
    source = path.read_bytes()
    for old, new in EDITS[name]:
        assert source.count(old) == 1, (name, old, source.count(old))
        source = source.replace(old, new)
    compile(source, str(path), 'exec')
    return path, source


def load(name, record=False):
    path, source = transformed(name)
    if record:
        save('reuse_' + name + '.json', {'original': str(path),
             'original_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
             'executed_sha256': hashlib.sha256(source).hexdigest(),
             'exact_edits': [old.decode('ascii') for old, new in EDITS[name]],
             'programming_performed': False})
    scope = {'__name__': 'tc05_reuse_' + name, '__file__': str(path)}
    exec(compile(source, str(path), 'exec'), scope)
    return scope
