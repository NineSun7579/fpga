"""Bounded same-viewer EGL diagnostic, then exact baseline environment restore."""
import json,time,uuid,subprocess,sys,argparse
import deploy_candidate as d
parser=argparse.ArgumentParser();parser.add_argument('--pid',type=int,default=9992)
parser.add_argument('--interval',type=int,choices=(0,1));parser.add_argument('--label',default='egl_probe')
parser.add_argument('--texture-ring',type=int,choices=(1,2,3))
parser.add_argument('--xcb-build',help='Local manifest path for an optional XCB timing probe')
args=parser.parse_args()
assert args.label.replace('_','').isalnum()
folder=d.ROOT/('egl_probe_trial_'+str(time.time_ns()));folder.mkdir()
old=json.loads((d.ROOT/'deploy_1791613638189975800/receipt.json').read_text())
build=json.loads((d.ROOT/'egl_probe_build_1791618116956610000/manifest.json').read_text())
xcb=None
if args.xcb_build:
    path=(d.ROOT/args.xcb_build).resolve();path.relative_to(d.ROOT)
    xcb=json.loads(path.read_text())
s=d.Session(folder,old)
trial={'build':build,'xcb_build':xcb,'phase':'preflight','requested_interval_override':args.interval,'texture_ring_override':args.texture_ring}
def save(phase,**fields):
    trial.update(fields);trial['phase']=phase
    (folder/'trial.json').write_text(json.dumps(trial,indent=2),encoding='utf-8')
def launch(baseline,env,label):
    run=label+'-'+uuid.uuid4().hex
    paths={k:s.remote+'/'+run+v for k,v in {'config':'.launch.json','log':'.viewer.log','supervisor_log':'.supervisor.log','identity_file':'.identity.json','status':'.exit.json'}.items()}
    identity=s.rpc('launch',exe=baseline['identity']['exe'],sha256=d.ACTIVE,argv=baseline['argv'],env=env,cwd=baseline['cwd'],uid=baseline['uid'],gid=baseline['gid'],groups=baseline['groups'],candidate=False,**paths)
    return {'identity':identity,'env':env,**paths}
def sample(run,label):
    subprocess.run([sys.executable,str(d.ROOT/'sample_runtime.py'),str(run['identity']['pid']),label,run['log']],check=True)
try:
    assert s.rpc('hash',path=s.helper)['sha256']==old['artifacts']['helper_sha256']
    baseline=s.rpc('snapshot',pid=args.pid,active_sha=d.ACTIVE)
    assert s.rpc('hash',path=build['library'])['sha256']==build['sha256']
    if xcb:assert s.rpc('hash',path=xcb['library'])['sha256']==xcb['sha256']
    assert 'LD_PRELOAD' not in baseline['env'],'Preserve existing preload; review before combining'
    save('baseline_verified',baseline=baseline)
    s.rpc('stop',identity=baseline['identity'],env=baseline['env'])
    save('baseline_retired')
    env=dict(baseline['env']);env.update(LD_PRELOAD=build['library'],DETVIEW_EGL_SWAP_PROBE='1')
    if xcb:
        env['LD_PRELOAD']=xcb['library']+':'+build['library']
        env[xcb.get('flag','DETVIEW_XCB_REPLY_PROBE')]='1'
    if args.interval is not None:env['DETVIEW_SWAP_INTERVAL']=str(args.interval)
    if args.texture_ring is not None:env['DETVIEW_TEXTURE_RING']=str(args.texture_ring)
    probe=launch(baseline,env,'egl-probe')
    save('probe_running',probe=probe)
    print(str(folder),flush=True)
    sampling_error=None
    try:sample(probe,args.label+'_active')
    except Exception as error:sampling_error=repr(error)
    s.rpc('stop',identity=probe['identity'],env=probe['env'],status=probe['status'])
    save('probe_retired',sampling_error=sampling_error)
    restored=launch(baseline,dict(baseline['env']),'egl-probe-restored')
    save('original_running',restored=restored)
    sample(restored,args.label+'_restored')
    save('original_sampled')
    if sampling_error:raise RuntimeError(sampling_error)
    print('Original environment restored; evidence '+str(folder),flush=True)
except Exception as error:
    save('stopped_for_review',error=repr(error))
    raise
finally:s.client.close()
