"""Audit TC05 scope, unchanged RAM/pipeline and frozen resource evidence."""
from pathlib import Path
import hashlib
import json
import re

HERE = Path(__file__).resolve().parents[1]
MIG = HERE.parent


def main():
    baseline = MIG / 'timing_correction_03/rtl/block_motion_detector_tc03.v'
    candidate = HERE / 'rtl/block_motion_detector_tc05.v'
    a, b = baseline.read_bytes(), candidate.read_bytes()
    anchors = [
        (b'    reg [7:0] history [', b'    reg compare_pending'),
        (b'    reg compare_pending', b'    integer i;'),
        (b'            result_strobe<=0;\n            result_valid<=0;\n            end_pending<=0;', b'endmodule')]
    unchanged = {}
    for left, right in anchors:
        old = a[a.index(left):a.index(right)]
        new = b[b.index(left):b.index(right)]
        assert old == new
        unchanged[left.decode().strip()] = hashlib.sha256(new).hexdigest()
    sample = re.search(rb'wire accept_sample=([^;]+);', b)[1]
    assert b'accept_pixel' not in sample and b'history_eligible' in sample
    assert b'if (rst_n && accept_sample)' in b
    declarations = [str(p) for base in (HERE / 'rtl', MIG.parent / 'source')
                    for p in base.rglob('*.v')
                    if re.search(rb'\bmodule\s+block_motion_detector_tc05\b', p.read_bytes())]
    assert declarations == [str(candidate)]
    v6 = MIG / 'whole_candidate_v6_route_01'
    proof_file = v6 / 'evidence/motion_routed_resource_proof.json'
    proof = json.loads(proof_file.read_bytes())
    assert proof['routed_history_DRM36K_total'] == 32
    assert proof['logical_total_bits'] == 614400
    assert len(proof['histories']) == 4
    assert all(h['logical_depth'] == 19200 and h['logical_width'] == 8 and
               h['mode'] == 'read_first' and h['routed_DRM36K_instances'] == 8
               for h in proof['histories'])
    adapter_a = MIG / 'timing_correction_04/rtl/motion_stream_adapter_tc04.v'
    adapter_b = v6 / 'rtl/motion_stream_adapter_tc04.v'
    assert adapter_a.read_bytes() == adapter_b.read_bytes()
    result = {'status': 'PASS', 'candidate_sha256': hashlib.sha256(b).hexdigest(),
              'unique_candidate_module': declarations, 'unchanged_regions_sha256': unchanged,
              'accept_sample_does_not_depend_on_accept_pixel': True,
              'v6_adapter_exactly_matches_tc04': True,
              'baseline_resource_proof_sha256': hashlib.sha256(proof_file.read_bytes()).hexdigest(),
              'baseline_history_drm36k': 32, 'baseline_logical_history_bits': 614400,
              'tc05_mapped_resource_count_measured': False, 'pds_invoked': False}
    out = HERE / 'receipts/structure.json'
    out.write_bytes((json.dumps(result, indent=2) + '\n').encode('ascii'))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
