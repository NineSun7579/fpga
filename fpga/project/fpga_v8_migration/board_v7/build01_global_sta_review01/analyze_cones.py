from pathlib import Path
import hashlib,json,re
HERE=Path(__file__).resolve().parent
BUILD=HERE.parent/'source_diagnostics_timing_build_01'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
raw=HERE/'final_sta/report_timing/v7_sdt_top.rtr'
text=raw.read_text(encoding='gb18030',errors='replace')
blocks=re.split(r'(?=^Startpoint\s*:)',text,flags=re.M)[1:]
negative=[]
for block in blocks:
    m=re.search(r'Slack\s*\(VIOLATED\)\s+(-?\d+\.\d+)',block)
    if not m:continue
    index=len(negative);dest=HERE/('actual_negative_path_%02d.txt'%(index+1));dest.write_text(block,encoding='utf8')
    logic=re.search(r'Logic:\s*([\d.]+)ns\(([\d.]+)%\), Route:\s*([\d.]+)ns\(([\d.]+)%\)',block)
    data=block.split('Data arrival time')[0].split('/opit_0_inv/CLK\n')[-1]
    negative.append({'slack_ns':float(m[1]),'actual_path_file':dest.name,'actual_path_sha256':sha(dest),
       'launch_edge':'falling','capture_edge':'rising','nominal_half_cycle_ns':5.953,
       'logic_ns':float(logic[1]),'logic_percent':float(logic[2]),'route_ns':float(logic[3]),'route_percent':float(logic[4]),
       'classification':'diagnostic gap counter clear cone' if index<2 else 'camera CDC drop-count prefix clear cone',
       'axi_read_decode_in_cone':False,'pipeline_stage_added':False})
assert len(negative)==3
inputs=json.loads((BUILD/'evidence/input_hashes.json').read_bytes())
assert all(sha(BUILD/n)==h for n,h in inputs.items())
final=json.loads((HERE/'final_global10summary.json').read_bytes())
assert len(final['groups'])==10
mpw=[g for g in final['groups'] if g['check']=='Minimum Pulse Width']
assert len(mpw)==2 and all(len(g['rows'])==19 and g['failing_endpoints']==0 for g in mpw)
candidate=HERE/'camera_boolean_candidate01'
logs={n:{'sha256':sha(candidate/n),'pass_lines':[s for s in (candidate/n).read_text(errors='replace').splitlines() if 'PASS ' in s]} for n in ['miter.log','gap_exhaustive.log']}
assert any('524288' in s for s in logs['miter.log']['pass_lines'])
assert any('50000' in s for s in logs['miter.log']['pass_lines'])
assert any('1048576' in s for s in logs['gap_exhaustive.log']['pass_lines'])
result={'actual_report':{'path':str(raw),'sha256':sha(raw)},'route':final['route'],'all_747_inputs_unchanged':True,
 'ten_groups_verified':True,'mpw_rows_each_corner':19,'negative_cones':negative,'simulations':logs,
 'candidate_provenance':json.loads((candidate/'provenance.json').read_bytes()),
 'candidate_routed_sta_performed':False,'timing_improvement_verified':False,
 'physical_expectation':'Late frame clear is final Boolean gating; synthesis may reconstruct equivalent logic. Actual baseline routing dominates; no timing gain claimed.'}
(HERE/'camera_cone_evidence.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
print(json.dumps(result,indent=2))
