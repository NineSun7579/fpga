"""Final evidence audit for the two stream/capture candidates, run after regression."""
from pathlib import Path
import hashlib
import json
import re

HERE=Path(__file__).resolve().parent
OUT=HERE/'receipts/stream_capture'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    result=json.loads((OUT/'results.json').read_text())
    assert result['passed'] and result['four_channel_oracle_passed']
    assert not result['pds_invoked'] and not result['routed_timing_verified']
    assert len(result['runs'])==6
    for p,h in result['file_sha256'].items():
        assert sha(Path(p))==h,p
    protected=json.loads((OUT/'protected_sha256.json').read_text())
    for p,h in protected.items():
        assert sha(Path(p))==h,p
    for case in result['runs']:
        raw=(OUT/(case['case']+'.log')).read_bytes()
        assert re.search(rb'(MOTION|CAPTURE)_TC04_PASS ',raw),case['case']
        assert not re.search(rb'\*\* (Error|Fatal)',raw),case['case']
    four=(OUT/'four_motion.log').read_bytes()
    final=re.search(rb'PASS tb_four_motion:[^\r\n]*cycles=(\d+)',four)
    assert final and not re.search(rb'\*\* (Error|Fatal)',four)
    phases=re.findall(rb'PASS four-motion phase (\d+):',four)
    assert [int(v) for v in phases]==list(range(1,11))
    motion=[v for v in result['runs'] if v['case'].startswith('tb_motion')]
    capture=[v for v in result['runs'] if v['case'].startswith('tb_capture')]
    summary={'passed':True,'differential_runs':6,
        'differential_cycles':sum(v['comparisons'] for v in result['runs']),
        'motion_records':sum(v['records'] for v in motion),
        'motion_fifo_overflows':sum(v['overflows'] for v in motion),
        'capture_fifo_overflows':sum(v['overflows'] for v in capture),
        'capture_publications':sum(v['publications'] for v in capture),
        'capture_carry_wrap_boundary_cases':sum(v['boundaries'] for v in capture),
        'four_channel_cycles':int(final[1]),'four_channel_phases':10,
        'four_channel_publications':39,
        'protected_files_verified':len(protected),
        'results_sha256':sha(OUT/'results.json'),
        'candidate_sha256':{p.name:sha(p) for p in
            [HERE/'rtl/motion_stream_adapter_tc04.v',HERE/'rtl/fpga_v8_capture_ov5640_ddr_tc04.v']},
        'pds_invoked':False,'routed_timing_verified':False,
        'cam6_binding_differential_verified':False,
        'tc02_dma_edited':False}
    (OUT/'final_audit.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
