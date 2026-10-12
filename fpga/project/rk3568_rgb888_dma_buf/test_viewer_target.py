"""Run device-free viewer regression checks using userdata temporary storage."""
from pathlib import Path
import argparse
import json
import shlex
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh

root=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('build',type=Path)
args=parser.parse_args()
folder=args.build.resolve()
folder.relative_to(root)
manifest_path=folder/'manifest.json'
manifest=json.loads(manifest_path.read_text())
assert manifest['build_return_code']==0
client=board_ssh.connect()
results={}
try:
    for name in ('camera-dma','frame-metrics','hdmi','mvp-round1','mvp','vision'):
        command='env TMPDIR='+shlex.quote(manifest['remote']+'/tmp')+' QT_QPA_PLATFORM=offscreen '+shlex.quote(manifest['executable'])+' --'+name+'-selftest'
        rc,out,err=board_ssh.run(client,command,timeout=45)
        (folder/(name+'.selftest.log')).write_text(out+err,encoding='utf-8')
        results[name]=rc
        print(name,rc,flush=True)
finally:
    manifest['selftests']=results
    manifest_path.write_text(json.dumps(manifest,indent=2))
    client.close()
if len(results)!=6 or any(results.values()):
    raise RuntimeError('Target selftest failure; inspect '+str(folder))
