"""Verify actual V5 source copies with exact byte-level instance replacements."""
import json
from run_whole import BASE, WORK, HERE, sha, replace_instances, save


def main():
    replacements = [
        ('inputs/source/ov5640/ov5640/ov5640.v', 'rtl/ov5640_tc03_binding.v', b'ov5640_cdc', b'ov5640_cdc_tc03'),
        ('inputs/source/HDMI/hdmi_loop.v', 'rtl/hdmi_loop_tc03_binding.v', b'ov5640_cdc', b'ov5640_cdc_tc03'),
        ('rtl/fpga_v8_cooperative_top_v2_rfg01.v', 'rtl/fpga_v8_cooperative_top_v2_rfg01.v', b'fpga_v8_ddr_adapter', b'fpga_v8_ddr_adapter_tc03'),
        ('rtl/motion_stream_adapter.v', 'rtl/motion_stream_adapter.v', b'block_motion_detector_tc01', b'block_motion_detector_tc03'),
    ]
    counts = {}
    for source, target, old, new in replacements:
        expected, count = replace_instances((BASE / source).read_bytes(), old, new)
        assert count > 0 and (WORK / target).read_bytes() == expected, target
        counts[target] = count
    originals = json.loads((BASE / 'inputs_before.json').read_bytes())
    frozen = {p: h for p, h in originals.items() if p.startswith('inputs')}
    assert len(frozen) == 694
    assert all(sha(WORK / p) == h for p, h in frozen.items())
    corrected = ['ov5640_cdc_tc03.v', 'fpga_v8_ddr_adapter_tc03.v', 'block_motion_detector_tc03.v']
    assert all(sha(WORK / 'rtl' / n) == sha(HERE / 'rtl' / n) for n in corrected)
    changed = {target for source, target, old, new in replacements}
    inherited = {str(p.relative_to(BASE)): sha(p) for p in (BASE / 'rtl').rglob('*') if p.is_file()}
    assert all(sha(WORK / p) == h for p, h in inherited.items()
               if p.replace('\\', '/') not in changed)
    save('exact_binding_verification.json', {'passed': True, 'frozen_inputs': len(frozen),
         'exact_instance_replacements': counts,
         'candidate_hashes': {n: sha(WORK / 'rtl' / n) for n in corrected},
         'programming_performed': False})
    print('PASS exact V5 source bindings, 694 frozen inputs and inherited RTL', flush=True)


if __name__ == '__main__':
    main()
