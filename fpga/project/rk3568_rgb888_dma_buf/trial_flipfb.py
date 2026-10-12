"""Original / FlipFB off / restored original, with graceful DMA retirement gates."""
import argparse,hashlib,json,re,shlex,subprocess,sys,time,uuid
import deploy_candidate as d
parser=argparse.ArgumentParser();parser.add_argument('--pid',type=int,default=24297)
parser.add_argument('--candidate-seconds',type=int,default=180)
parser.add_argument('--warmup',type=int,default=0)
parser.add_argument('--prefix',default='')
parser.add_argument('--adopt',action='store_true',help='Explicitly authorized adoption: retain none after live health check')
args=parser.parse_args()
assert 1<=args.candidate_seconds<=1800 and 0<=args.warmup<=180
assert not args.prefix or args.prefix.replace('_','').isalnum()
p=d.ROOT/('flipfb_trial_'+str(time.time_ns()));p.mkdir()
receipt=json.loads((d.ROOT/'deploy_1791613638189975800/receipt.json').read_text())
s=d.Session(p,receipt)
state={'phase':'preflight','sample_prefix':args.prefix,'warmup_seconds':args.warmup,'candidate_seconds':args.candidate_seconds,'adopt':args.adopt}
current=None;baseline=None;changed=False;pending=None;retirement_failed=False;started=False;locked=False
lock_owner=s.remote+'/'+p.name
config='/etc/X11/xorg.conf.d/20-modesetting.conf'
def save(phase,**kw):
    state.update(kw);state['phase']=phase
    (p/'trial.json').write_text(json.dumps(state,indent=2));print(phase,flush=True)
def remote(code):
    rc,o,e=s.board.run(s.client,'python3 -c '+shlex.quote(code),timeout=55,sudo=True)
    if rc:raise RuntimeError(o+e)
    return o
def check_outputs(env):
    code='import subprocess,json\n'
    code+='env='+repr({k:env[k] for k in ('DISPLAY','XAUTHORITY') if k in env})+'\n'
    code+="text=subprocess.check_output(['env',*[k+'='+v for k,v in env.items()],'xrandr','--current'],text=True)\n"
    code+="print(json.dumps([l for l in text.splitlines() if ' connected' in l]))\n"
    return json.loads(remote(code))
def retire():
    global current,retirement_failed
    run=current
    try:
        live=remote('from pathlib import Path;print(int(Path('+repr('/proc/'+str(run['identity']['pid'])+'/exe')+').exists()))').strip()=='1'
        if live:s.rpc('stop',identity=run['identity'],env=run['env'],**({'status':run['status']} if 'status' in run else {}))
        else:
            assert 'status' in run,'Missing clean exit receipt; preserve uncertain retirement'
            s.rpc('verify_retired',identity=run['identity'],status=run['status'])
    except Exception:
        retirement_failed=True
        raise
    current=None
    save('device_retired')
def write_config(expected,data):
    code='from pathlib import Path;import hashlib,os,tempfile\np=Path('+repr(config)+')\n'
    code+='assert hashlib.sha256(p.read_bytes()).hexdigest()=='+repr(expected)+'\n'
    code+='st=p.stat();fd,name=tempfile.mkstemp(prefix=".ov56401-config-",dir=str(p.parent))\n'
    code+='with os.fdopen(fd,"wb") as f:\n f.write(bytes.fromhex('+repr(data.hex())+'));f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),st.st_mode);os.fchown(f.fileno(),st.st_uid,st.st_gid)\n'
    code+='os.replace(name,p)\n'
    code+='print(hashlib.sha256(p.read_bytes()).hexdigest())'
    return remote(code).strip()
def restart():
    assert current is None
    # Retirement above is mandatory before graph restart. No forced process kills.
    code="import subprocess,time,pathlib,json,os\nsubprocess.run(['systemctl','restart','lightdm'],check=True,timeout=25)\n"
    code+='deadline=time.monotonic()+25\n'
    code+="while time.monotonic()<deadline:\n ps=[]\n for q in pathlib.Path('/proc').iterdir():\n  try:\n   if q.name.isdigit() and (q/'comm').read_text().strip()=='xfwm4':ps.append(q)\n  except (FileNotFoundError,ProcessLookupError):pass\n if len(ps)==1:\n  try:\n   assert ps[0].stat().st_uid=="+str(baseline['uid'])+"\n   env=dict(x.decode().split('=',1) for x in (ps[0]/'environ').read_bytes().split(b'\\0') if x)\n   if 'DISPLAY' in env and 'DBUS_SESSION_BUS_ADDRESS' in env:\n    import re\n    text=subprocess.check_output(['env',*[k+'='+env[k] for k in ('DISPLAY','XAUTHORITY') if k in env],'xprop','-root','_NET_SUPPORTING_WM_CHECK'],text=True,timeout=3)\n    if not re.search(r'0x[1-9a-fA-F][0-9a-fA-F]*',text):raise RuntimeError('WM not ready')\n    print(json.dumps({k:env[k] for k in ('DISPLAY','XAUTHORITY','DBUS_SESSION_BUS_ADDRESS','SESSION_MANAGER','XDG_RUNTIME_DIR') if k in env}));break\n  except (FileNotFoundError,ProcessLookupError,subprocess.CalledProcessError,subprocess.TimeoutExpired,RuntimeError):pass\n time.sleep(.5)\nelse:raise RuntimeError('Desktop did not become ready')\n"
    code=code.replace('st_uid=='+str(baseline['uid']),'st_uid=='+str(state['desktop_uid']))
    code=code.replace('0x[1-9a-fA-F]','0x0*[1-9a-fA-F]')
    return json.loads(remote(code))
def launch(session,label):
    global current,pending
    env=dict(baseline['env'])
    for key in ('DISPLAY','XAUTHORITY','DBUS_SESSION_BUS_ADDRESS','SESSION_MANAGER','XDG_RUNTIME_DIR'):
        env.pop(key,None)
    env.update(session)
    assert check_outputs(env)==state['outputs'],'Output layout changed; preserve evidence'
    run=label+'-'+uuid.uuid4().hex
    paths={k:s.remote+'/'+run+v for k,v in {'config':'.launch.json','log':'.viewer.log','supervisor_log':'.supervisor.log','identity_file':'.identity.json','status':'.exit.json'}.items()}
    pending={'env':env,**paths}
    save('launch_intent',pending_launch=pending)
    ident=s.rpc('launch',exe=baseline['identity']['exe'],sha256=d.ACTIVE,argv=baseline['argv'],env=env,cwd=baseline['cwd'],uid=baseline['uid'],gid=baseline['gid'],groups=baseline['groups'],candidate=False,**paths)
    current={'identity':ident,'env':env,**paths}
    pending=None
    save(label+'_running',**{label:current})
def sample(label,log):
    actual=(args.prefix+'_' if args.prefix else '')+label
    if args.warmup:
        subprocess.run([sys.executable,str(d.ROOT/'sample_runtime.py'),str(current['identity']['pid']),actual+'_warmup',log,'--seconds',str(args.warmup)],check=True)
    start=int(remote("from pathlib import Path\np=Path('/var/log/Xorg.0.log');print(p.stat().st_size)").strip())
    seconds=args.candidate_seconds if label=='flipfb_off' else 180
    subprocess.run([sys.executable,str(d.ROOT/'sample_runtime.py'),str(current['identity']['pid']),actual,log,'--seconds',str(seconds)],check=True)
    rc,o,e=s.board.run(s.client,'cat /var/log/Xorg.0.log',timeout=20,sudo=True)
    (p/(label+'.xorg.log')).write_text(o+e)
    assert rc==0
    with s.client.open_sftp() as f:
        with f.open('/var/log/Xorg.0.log','rb') as h:
            assert h.stat().st_size>=start,'Xorg log rotated during sample'
            h.seek(start);new=h.read()
    (p/(label+'.xorg_window.log')).write_bytes(new)
    assert check_outputs(current['env'])==state['outputs'],'Output layout drift'
    text=(d.ROOT/(actual+'_sample_window.log')).read_text()
    panes=[line for line in text.splitlines() if line.startswith('[panes]')]
    assert panes and all('have=111111' in line and 'err=0/0/0/0/0/0' in line for line in panes),'Six-camera health gate failed'
    save(label+'_sampled')
try:
    assert s.rpc('hash',path=s.helper)['sha256']==receipt['artifacts']['helper_sha256']
    remote("from pathlib import Path;import os\np=Path('/userdata/linaro/ov56401-deploy.lock')\nf=os.open(str(p),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)\nos.write(f,"+repr(lock_owner.encode())+");os.close(f)")
    locked=True
    s.rpc('verify_lock',remote=lock_owner)
    baseline=s.rpc('snapshot',pid=args.pid,active_sha=d.ACTIVE)
    current={'identity':baseline['identity'],'env':baseline['env']}
    assert 'LD_PRELOAD' not in baseline['env']
    with s.client.open_sftp() as f:
        with f.open(config,'rb') as h:original=h.read()
    (p/'20-modesetting.original.conf').write_bytes(original)
    pattern=rb'(?m)^(\s*Option\s+"FlipFB"\s+)"always"'
    candidate,n=re.subn(pattern,rb'\1"none"',original);assert n==1
    original_sha=hashlib.sha256(original).hexdigest();candidate_sha=hashlib.sha256(candidate).hexdigest()
    (p/'20-modesetting.candidate.conf').write_bytes(candidate)
    env=baseline['env'];outputs=check_outputs(env)
    assert any('HDMI' in l and '1920x1080+' in l for l in outputs)
    assert any('DSI' in l and '720x1280+' in l for l in outputs)
    log=remote('import os;print(os.readlink('+repr('/proc/'+str(args.pid)+'/fd/1')+'))').strip()
    desktop_uid=int(remote("import subprocess,pathlib\nps=subprocess.check_output(['pidof','xfwm4'],text=True).split();assert len(ps)==1;print(pathlib.Path('/proc/'+ps[0]).stat().st_uid)"))
    save('baseline_verified',baseline=baseline,desktop_uid=desktop_uid,outputs=outputs,original_sha256=original_sha,candidate_sha256=candidate_sha)
    if not args.adopt:sample('flipfb_original_before',log)
    retire()
    started=True
    # Mark intent before writing, so exception cleanup also covers ambiguous SSH completion.
    changed=True
    assert write_config(original_sha,candidate)==candidate_sha
    save('candidate_config_written')
    session=restart();launch(session,'flipfb_off')
    sample('flipfb_off',current['log'])
    if args.adopt:
        assert s.rpc('hash',path=config)['sha256']==candidate_sha
        save('adopted_flipfb_none',known_tradeoffs='Prior warmed600s CPU233.65%; Cam1 capture41.79fps vs44.98; optical tearing/latency unmeasured. User explicitly chose this version.')
    else:
        retire()
        assert write_config(candidate_sha,original)==original_sha
        changed=False
        session=restart();launch(session,'flipfb_original_restored')
        sample('flipfb_original_restored',current['log'])
        save('complete_original_restored')
    s.rpc('release_lock',remote=lock_owner);locked=False
except Exception as error:
    save('failed',error=repr(error))
    # Restore the file even if DMA is uncertain; restart only after verified retirement.
    try:
        if changed:
            text=remote('from pathlib import Path;import hashlib;print(hashlib.sha256(Path('+repr(config)+').read_bytes()).hexdigest())').strip()
            if text==candidate_sha:write_config(candidate_sha,original)
            else:assert text==original_sha,'Configuration changed externally; do not overwrite'
            save('config_restored_runtime_review_required')
        if started and not retirement_failed:
            if pending:
                # Never restart over an untracked supervisor or an unknown owner.
                code='from pathlib import Path;import json\np=Path('+repr(pending['identity_file'])+')\nassert p.exists(),"Launch identity unavailable; preserve runtime"\nprint(p.read_text())'
                ident=json.loads(remote(code));current={'identity':ident,**pending};pending=None
            if current:retire()
            s.rpc('verify_retired')
            session=restart();launch(session,'flipfb_failure_restored')
            save('failure_original_relaunched',failure=repr(error))
    except Exception as recovery:
        save('recovery_blocked',error=repr(error),recovery_error=repr(recovery))
    if locked and not started and not retirement_failed:
        s.rpc('release_lock',remote=lock_owner);locked=False
    elif locked and state['phase']=='failure_original_relaunched':
        s.rpc('release_lock',remote=lock_owner);locked=False
    raise
finally:s.client.close()
