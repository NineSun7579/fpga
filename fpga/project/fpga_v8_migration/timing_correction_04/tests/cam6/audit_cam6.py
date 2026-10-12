"""Audit completed actual-cam6 receipts; never starts simulation or PDS."""
from pathlib import Path
import hashlib
import json
import re

HERE = Path(__file__).resolve().parents[2]
OUT = HERE/'receipts/cam6'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    result = json.loads((OUT/'results.json').read_bytes())
    assert result['passed'] and not result['pds_invoked'] and not result['routed_timing_verified']
    assert len(result['runs']) == 3
    assert result['public_output_ports_compared']==20 and result['public_output_bits_compared']==566
    for case in result['runs']:
        log = (OUT/(case['case']+'.log')).read_bytes()
        assert not re.search(rb'\*\* (?:Error|Fatal)', log)
        m = re.search(rb'CAM6_TC04_PASS ([^\r\n]+)', log)
        assert m
        actual = {k.decode():int(v) for k,v in re.findall(rb'(\w+)=(\d+)', m[1])}
        assert actual == {k:v for k,v in case.items() if k!='case'}
        assert case['boundaries']==96 and case['dynamic_cases']==6 and case['zero_rejects']==1
        assert all(case[k]>0 for k in ('admissions','complete','overflows','publications','beats','stalls','short_faults'))
        # Check loaded hierarchy: actual child modules and actual vendor RAM primitive.
        for module in ('ov5640_ddr','ov5640_ddr_tc04','ov5640_ddr_w_en','ov5640_ddr_w',
                       'ov5640_ddr_w_ctrl','ov5640_ddr_fifo','ov5640_ddr_fifo_DRM','GTP_DRM36K_E1'):
            assert re.search(rb'Loading work\.'+module.encode()+rb'(?:\s|\()', log), module
    assert all(sha(Path(p))==h for p,h in result['file_sha256'].items())
    protected = json.loads((OUT/'protected_sha256.json').read_bytes())
    assert all(sha(Path(p))==h for p,h in protected.items())
    bindings = json.loads((OUT/'parent_bindings.json').read_bytes())
    assert sum(len(p['instances']) for p in bindings['parents'])==7
    for p in bindings['parents']:
        src, dst = Path(p['source']), Path(p['isolated_copy'])
        assert sha(src)==p['original_sha256'] and sha(dst)==p['bound_sha256']
        assert dst.read_bytes().replace(b'ov5640_ddr_tc04',b'ov5640_ddr')==src.read_bytes()
    paths = json.loads((OUT/'v5_paths_23_24_full_detail.json').read_bytes())
    assert [p['number'] for p in paths]==[23,24]
    assert all(p['Slack']==-0.005 and
               sum('td' in line and '/CECO' in line for line in p['full_detail'].splitlines())==7
               for p in paths)
    audit = {'passed':True, 'simulated_comparisons':sum(c['comparisons'] for c in result['runs']),
        'natural_overflow_cycles':sum(c['overflows'] for c in result['runs']),
        'publications':sum(c['publications'] for c in result['runs']),
        'boundary_cases':sum(c['boundaries'] for c in result['runs']),
        'protected_files_verified':len(protected), 'all_parent_instances_byte_verified':7,
        'actual_fifo_and_w_modules_loaded':True, 'results_sha256':sha(OUT/'results.json'),
        'candidate_sha256':sha(HERE/'rtl/ov5640_ddr_tc04.v'),
        'pds_invoked':False, 'routed_timing_verified':False}
    (OUT/'final_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    print(json.dumps(audit,indent=2))

if __name__=='__main__':
    main()
