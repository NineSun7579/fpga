import hashlib
import json
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parent
artifacts=root/'artifacts_02'
artifacts.mkdir(exist_ok=False)
fixtures=root.parent/'capture_core_contract/artifacts/full_640x480'
metadata=fixtures/'checker.json'
frames=json.loads(metadata.read_text())['frames']
dependencies=[root/'paired_input_guard.hpp',root/'check_pair.cpp',root/'build.cmd',Path(__file__),
    root.parent/'capture_host/capture_host_protocol.hpp',
    root.parent/'cooperative_host/coop_host_protocol.hpp',
    root.parent/'raw_preprocess/raw_input_reference.h',metadata]
for frame in frames:
    for name,expected in [(frame['raw_file'],frame['raw_sha256']),
                          (frame['prepared_file'],frame['output_sha256'])]:
        path=fixtures/name
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise RuntimeError('fixture identity differs')
        dependencies.append(path)
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in dependencies}
build=subprocess.run(['cmd','/c','build.cmd',str(artifacts)],cwd=root,capture_output=True,text=True,timeout=45)
(artifacts/'build.txt').write_text(build.stdout+build.stderr,encoding='utf-8')
if build.returncode: raise RuntimeError('build failed')
rows=[]
for frame in frames:
    command=[str(artifacts/'check_pair.exe'),str(fixtures/frame['raw_file']),
        str(fixtures/frame['prepared_file']),str(frame['sequence']),str(frame['generation']),
        str(frame['source_bank']),frame['token64'],str(frame['output_bank']),str(frame['camera'])]
    result=subprocess.run(command,capture_output=True,text=True,timeout=20)
    rows.append({'command':command,'return_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
    if result.returncode or 'PAIR_GUARD_PASS bytes=1228800 rejected=16' not in result.stdout:
        raise RuntimeError('paired guard failed: '+result.stdout+result.stderr)
unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
if not unchanged: raise RuntimeError('source/fixture changed')
report={'status':'pass','pairs':len(rows),'certified_bytes':len(rows)*1228800,
    'negative_checks':len(rows)*16,'inputs_unchanged':unchanged,'hashes':hashes,'runs':rows,
    'limits':['Simulation fixture provenance only; descriptors supplied from retained checker metadata',
              'No host DMA, lease release, inference, board access or FPS measurement']}
(artifacts/'results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(f"PAIR_GUARD_PASS pairs={len(rows)} bytes={len(rows)*1228800} negative_checks={len(rows)*16}")
