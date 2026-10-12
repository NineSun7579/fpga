"""逐拍 trace 独立核验与哈希审计，仅写候选 evidence。"""
from pathlib import Path
import csv, json, hashlib, re, base64

ROOT = Path(__file__).resolve().parent
sha = lambda b: hashlib.sha256(b).hexdigest()
manifest = json.loads((ROOT/'evidence/input_hashes.json').read_text(encoding='utf-8'))
source = Path(manifest['source']).read_bytes()
candidate = (ROOT/'rtl/ov5640_reg.v').read_bytes()
assert sha(source) == manifest['source_sha256']
assert source == (ROOT/'original/ov5640_reg.v').read_bytes()
assert (ROOT/'sim/ov5640_reg_reference.v').read_bytes() == source.replace(b'module ov5640_reg #(',b'module ov5640_reg_reference #(',1)
assert (ROOT/'sim/ov5640_reg_candidate.v').read_bytes() == candidate.replace(b'module ov5640_reg #(',b'module ov5640_reg_candidate #(',1)
patch = json.loads((ROOT/'evidence/byte_patch.json').read_text())
rebuilt = source
for edit in reversed(patch['edits']):
    pos=edit['offset']; old=base64.b64decode(edit['delete_b64']); new=base64.b64decode(edit['insert_b64'])
    assert rebuilt[pos:pos+len(old)] == old
    rebuilt = rebuilt[:pos]+new+rebuilt[pos+len(old):]
assert rebuilt == candidate and sha(candidate) == patch['candidate_sha256']
exact = Path(manifest['exact09_input_manifest']['path'])
assert sha(exact.read_bytes()) == manifest['exact09_input_manifest']['sha256']
paths_file = exact.parent/'evidence/all_reported_failing_paths.json'
paths = json.loads(paths_file.read_text())
target = [p for p in paths if '/ov5640_reg/rdata[' in p['Endpoint'] and '/ov5640_reg/raddr_reg[' in p['Startpoint']]
assert len(target)==128 and min(p['Slack'] for p in target)==-4.412
(ROOT/'evidence/exact09_camera_target_paths.json').write_text(json.dumps({'origin':str(paths_file),'origin_sha256':sha(paths_file.read_bytes()),'count':len(target),'wns_ns':min(p['Slack'] for p in target),'paths':target},indent=2),encoding='utf-8')
log = (ROOT/'evidence/modelsim_cycle_miter.log').read_text(errors='replace')
assert 'PASS ALL 6 actual-module cycle miters' in log and not re.search(r'\bFAIL\b|\*\* Fatal', log)
passes = re.findall(r'PASS pair=(\d+) width=(\d+) cycles=(\d+) reads=(\d+) writes=(\d+) stalls=(\d+) resets=(\d+) simultaneous=(\d+)',log)
assert len(passes)==6
summary=[]
for row in passes:
    pair,width,cycles,reads,writes,stalls,resets,simult=map(int,row)
    p=ROOT/f'sim/trace_{pair}.csv'
    count=0
    with p.open(newline='') as f:
        for r in csv.DictReader(f):
            count+=1
            assert int(r['cycle'])==count
            for a,b in [('ref_axi','dut_axi'),('ref_rdata','dut_rdata'),('ref_cam1','dut_cam1'),('ref_all_outputs','dut_all_outputs')]:
                assert r[a]==r[b], (pair,count,a)
    assert count==cycles
    summary.append(dict(pair=pair,width=width,cycles=cycles,reads=reads,writes=writes,stalls=stalls,resets=resets,simultaneous=simult,trace_sha256=sha(p.read_bytes())))
result={'status':'PASS','source_unchanged':True,'byte_patch_exact':True,'exact09_camera_source_match':True,'baseline_path_count':len(target),'baseline_wns_ns':-4.412,'pairs':summary,'cycles_total':sum(p['cycles'] for p in summary),'trace_all_outputs_mismatch':0,'physical_timing_verified':False}
(ROOT/'evidence/verification_summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
lines=['摄像头读预译码候选：真实周期等价回归审计', 'ModelSim SE-64 10.6e，实际原模块与实际候选模块并排',f"PASS 总比较周期={result['cycles_total']}，全部输出差异=0",'PASS 原始 RTL 与 exact09 input_hash 完全一致，route02 源哈希未变','PASS 两处字节补丁可完整重建候选，无全文件转码','PASS 6 份 CSV 独立逐行比较，包含所有输出', 'remaining：未运行 PDS，候选的综合、面积、WNS、hold、AR路径均待物理验证。']
(ROOT/'evidence/周期等价审计.log').write_text('\n'.join(lines)+'\n',encoding='utf-8')
artifacts={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in ROOT.rglob('*') if p.is_file() and not any(x in p.parts for x in ['work','__pycache__']) and p.name not in ['artifact_hashes.json','vsim.wlf','transcript']}
(ROOT/'evidence/artifact_hashes.json').write_text(json.dumps(artifacts,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
