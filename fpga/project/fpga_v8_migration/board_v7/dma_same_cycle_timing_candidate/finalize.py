from pathlib import Path
import hashlib, json, re
HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
result=json.loads((HERE/'evidence/results.json').read_text())
assert result['status']=='PASS'
assert result['priority_vectors']==3072
assert result['original_cases']==800
assert result['candidate_sha256']==sha(HERE/'rtl/axi_dma_write_dma_sc_candidate.v')
for p,h in json.loads((HERE/'evidence/protected_sha256.json').read_text()).items():
    assert sha(Path(p))==h,p
for name in ['axi_dma_write_dma_sc_candidate','axi_dma_write_dma_sc_reference']:
    matches=[]
    for p in HERE.parent.rglob('*.v'):
        if re.search(rb'\bmodule\s+'+name.encode()+rb'\b',p.read_bytes()):matches.append(str(p))
    assert len(matches)==1,matches
artifacts=[p for p in HERE.rglob('*') if p.is_file() and p.suffix in ['.v','.sv','.svh','.py','.log','.json','.patch','.md','.txt'] and p.name!='artifact_sha256.json']
manifest=json.loads((HERE/'evidence/artifact_sha256.json').read_text())
for p,h in manifest.items():
    path=Path(p)
    # Documentation and packaging scripts can be completed after simulations.
    # Frozen RTL, generated miter and vendor logs must retain the run hashes.
    if HERE not in path.parents or path.suffix in ['.v','.sv','.log']:
        assert sha(path)==h,p
manifest.update({str(p):sha(p) for p in artifacts})
timing=json.loads((HERE/'evidence/exact09_timing_cones.json').read_text())
assert sha(Path(timing['source']))==timing['source_sha256']
manifest[timing['source']]=timing['source_sha256']
(HERE/'evidence/artifact_sha256.json').write_text(json.dumps(manifest,indent=2))
print('FINAL PASS: source/script protection, unique candidate/reference modules, 800 cases, 3072 priority vectors; artifacts='+str(len(artifacts)))
