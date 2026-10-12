import json, pathlib, difflib, hashlib
p=pathlib.Path(__file__).resolve().parent
results=[]
for first,last in [('before_selftests','after_selftests'),('before_build','final')]:
    a=json.loads((p/('all_device_owners_'+first+'.json')).read_text())
    b=json.loads((p/('all_device_owners_'+last+'.json')).read_text())
    x={r['pid']:r for r in a['owners']};y={r['pid']:r for r in b['owners']}
    for pid in sorted(x.keys() & y.keys()):
        if x[pid]['maps']!=y[pid]['maps']:
            results.append({'period':first+' to '+last,'pid':pid,'exe':x[pid]['exe'],'diff':list(difflib.unified_diff(x[pid]['maps'].splitlines(),y[pid]['maps'].splitlines()))})
(p/'mapping_delta_analysis.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results))
files={f.relative_to(p).as_posix():{'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in sorted(p.rglob('*')) if f.is_file() and f.name!='artifact_manifest.json' and '__pycache__' not in f.parts}
(p/'artifact_manifest.json').write_text(json.dumps({'excludes':['artifact_manifest.json','__pycache__'],'files':files},indent=2))
