from pathlib import Path
import json, hashlib, re
HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
result=json.loads((HERE/'evidence/results.json').read_text())
assert result['status']=='PASS'
assert (result['original_cases'],result['edge_cycles'],result['edge_vectors'],result['priority_vectors'])==(800,162253,67116,3072)
proof_by_id={r['id']:r for r in result['boundary_proof']}
assert proof_by_id[0]['binary']==1048576
assert proof_by_id[0]['credit']==196608
assert len(result['boundary_proof'])==12
assert result['candidate_sha256']==sha(HERE/'rtl/axi_dma_write_dma_sc_v2.v')
raw=(HERE/'original/axi_dma_write_tc04.v').read_bytes()
candidate=(HERE/'rtl/axi_dma_write_dma_sc_v2.v').read_bytes()
assert raw.split(b');',1)[0].replace(b'module axi_dma_write_tc04',b'module axi_dma_write_dma_sc_v2',1)==candidate.split(b');',1)[0]
registers=lambda b:re.findall(rb'\breg\s+[^;]+;',re.sub(rb'//[^\r\n]*|/\*.*?\*/',b'',b,flags=re.S))
assert registers(raw)==registers(candidate)
assert len(re.findall(rb'\balways\s*@',raw))==len(re.findall(rb'\balways\s*@',candidate))
(HERE/'evidence/packaging_audit.json').write_text(json.dumps(dict(status='PASS',interface_parameters_byte_identical_except_module_name=True,
    all_reg_declarations_identical=True,reg_declarations=len(registers(raw)),always_blocks=len(re.findall(rb'\balways\s*@',candidate)),no_new_state_or_clock_blocks=True),indent=2))
for p,h in json.loads((HERE/'evidence/protected_sha256.json').read_text()).items():assert sha(Path(p))==h,p
manifest=json.loads((HERE/'evidence/artifact_sha256.json').read_text())
for p,h in manifest.items():
    if Path(p).suffix in ['.v','.sv','.log']:assert sha(Path(p))==h,p
artifacts=[p for p in HERE.rglob('*') if p.is_file() and p.suffix in ['.py','.v','.sv','.svh','.json','.patch','.log','.md'] and p.name!='artifact_sha256.json']
manifest.update({str(p):sha(p) for p in artifacts})
(HERE/'evidence/artifact_sha256.json').write_text(json.dumps(manifest,indent=2))
print('FINAL PASS candidate_sha256='+result['candidate_sha256']+' artifacts='+str(len(artifacts)))
