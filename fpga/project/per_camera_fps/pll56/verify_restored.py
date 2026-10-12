"""Final identity-bound 120-second observation without programming or viewer changes."""
import base64
import json
import os
from pathlib import Path
import struct
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'fpga'))
import verify_rollback_current as verify
r=verify.rollback
directory=r.LOG/'pll56_optimized_1182d414dcc7436f841bb2170ae93960'
pause=r.board.load(directory/'pause_current.json')
saved=next(e for e in pause['events'] if e['state']=='snapshot_saved')
target=r.board.load(directory/'current_restore.json')['events'][-1]
token=r.board.load(directory/'receipt.json')['operation']
common=dict(snapshot=saved['snapshot'],snapshot_sha256=saved['snapshot_sha256'],start_operation=token,target=target)
lock=r.LOG/'board_session.lock'
client=None
with lock.open('x') as f:
    json.dump(dict(operation=token,pid=os.getpid(),action='final_restored_observe'),f)
try:
    client=r.deploy.ssh_connect(timeout=8)
    def run(request,name):
        result=dict(schema=1,action=request['action'],operation=token,status='running',events=[])
        def event(v):
            result['events'].append(v)
            r.motion.viewer.atomic_json(directory/(name+'.json'),result)
            if v['state']!='log_chunk':
                print(time.strftime('%Y-%m-%d %H:%M:%S')+' '+v['state'],flush=True)
        r.motion.remote_run(client,request,event)
        result['status']='success'
        r.motion.viewer.atomic_json(directory/(name+'.json'),result)
        return result
    observed=run(dict(common,action='observe',operation=token,seconds=120,timeout=180),'final_restored_observe')
    text=''.join(e['text'] for e in observed['events'] if e['state']=='log_chunk')
    (directory/'final_restored_observation.log').write_text(text,encoding='utf-8')
    health=verify.health_summary(text,observed['events'][-1])
    r.motion.viewer.atomic_json(directory/'final_restored_health.json',health)
    shot=run(dict(common,action='rollback_screenshot',timeout=60),'final_restored_screenshot')
    raw=base64.b64decode(next(e for e in shot['events'] if e['state']=='screenshot')['xwd'])
    (directory/'final_restored_screen.xwd').write_bytes(raw)
    f=struct.unpack('>25I',raw[:100])
    if (f[1],f[11],f[7],*f[14:17])!=(7,32,0,0xff0000,0xff00,0xff):
        raise RuntimeError('Unexpected screenshot format')
    verify.Image.frombytes('RGB',(f[4],f[5]),raw[f[0]+f[19]*12:],'raw','BGRX',f[12],1).save(directory/'final_restored_screen.png')
    print(json.dumps(health,indent=2),flush=True)
finally:
    if client:
        client.close()
    if r.board.load(lock).get('operation')==token:
        lock.unlink()
