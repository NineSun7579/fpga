"""Complete dependency capture, preserving first attempt; no PDS/tool launch."""
import json, shutil, subprocess, sys
from prepare_offline import HERE, B04, sha, save
sys.dont_write_bytecode=True
analysis=HERE/'offline_fresh_synthesis/analysis'
deps={}
for n in ['endpoint_logic.py','endpoint_detail.py','endpoints.py']:
    src=B04/'runtime/libraries'/n;dst=analysis/n
    if dst.exists(): raise RuntimeError('Refuse overwrite '+str(dst))
    deps[str(src)]=sha(src);shutil.copy2(src,dst)
save('additional_dependency_binding.json',deps)
commands=[[sys.executable,'-B',str(analysis/'classify_paths.py')],
          [sys.executable,'-B',str(analysis/'derive_new_constraints.py'),
           '--compile-graph',str(B04/'evidence/runtime/compile/analysis/graph.json'),
           '--synthesis-graph',str(analysis/'graph.json'),
           '--mapping-manifest',str(analysis/'manifest.json'),
           '--frozen-clock',str(B04/'inputs/source/constraints/clock.fdc'),
           '--output',str(HERE/'derived_logical_DRAFT')]]
results=[]
for i,cmd in enumerate(commands):
    res=subprocess.run(cmd,cwd=analysis,capture_output=True)
    p=HERE/('offline_dependency_complete_step'+str(i)+'.log')
    with p.open('xb') as f:f.write(res.stdout+res.stderr)
    results.append({'command':cmd,'exit_code':res.returncode})
    if res.returncode:break
save('offline_derivation_receipt.json',{'status':'DRAFT_DERIVED_OFFLINE' if len(results)==2 and all(x['exit_code']==0 for x in results) else 'OFFLINE_DERIVATION_BLOCKED',
     'steps':results,'constraints_qualified':False,'mapping_pass':False,'physical_signoff':False,'pds_started':False,'device_operations':False})
