"""Same-process fullscreen compositor-bypass hint with exact property restoration."""
import json,shlex,subprocess,sys,time
import deploy_candidate as d
p=d.ROOT/('bypass_trial_'+str(time.time_ns()));p.mkdir()
r=json.loads((d.ROOT/'deploy_1791613638189975800/receipt.json').read_text())
s=d.Session(p,r)
code=r'''
import os,re,subprocess,json
os.environ.update(DISPLAY=DISPLAY_VALUE,XAUTHORITY=AUTH_VALUE)
def prop(*a):return subprocess.check_output(['xprop',*a],text=True)
if ACTION=='inspect':
 windows=re.findall(r'0x[0-9a-fA-F]+',prop('-root','_NET_CLIENT_LIST'))
 found=[w for w in windows if re.search(r'=\s*'+str(PID)+r'\s*$',prop('-id',w,'_NET_WM_PID').strip())]
 assert len(found)==1,found
 w=found[0]
 assert '_NET_WM_STATE_FULLSCREEN' in prop('-id',w,'_NET_WM_STATE')
 before=prop('-id',w,'_NET_WM_BYPASS_COMPOSITOR')
 m=re.search(r'=\s*(\d+)\s*$',before.strip())
 print(json.dumps({'window':w,'before':int(m[1]) if m else None,'raw':before}))
else:
 assert re.search(r'=\s*'+str(PID)+r'\s*$',prop('-id',WINDOW,'_NET_WM_PID').strip())
 if VALUE is None:prop('-id',WINDOW,'-remove','_NET_WM_BYPASS_COMPOSITOR')
 else:prop('-id',WINDOW,'-f','_NET_WM_BYPASS_COMPOSITOR','32c','-set','_NET_WM_BYPASS_COMPOSITOR',str(VALUE))
 print(json.dumps({'current':prop('-id',WINDOW,'_NET_WM_BYPASS_COMPOSITOR')}))
'''
try:
 b=s.rpc('snapshot',pid=19091,active_sha=d.ACTIVE)
 def remote(action,window=None,value=None):
    header='\n'.join(k+'='+repr(v) for k,v in {'DISPLAY_VALUE':b['env']['DISPLAY'],'AUTH_VALUE':b['env']['XAUTHORITY'],'PID':b['identity']['pid'],'ACTION':action,'WINDOW':window,'VALUE':value}.items())
    rc,o,e=s.board.run(s.client,'python3 -c '+shlex.quote(header+'\n'+code),timeout=20,sudo=True)
    if rc:raise RuntimeError(e)
    return json.loads(o)
 receipt={'baseline':b,'property':remote('inspect')}
 (p/'receipt.json').write_text(json.dumps(receipt,indent=2))
 rc,log,e=s.board.run(s.client,'readlink /proc/19091/fd/1',timeout=15,sudo=True)
 assert rc==0;log=log.strip()
 def sample(label):subprocess.run([sys.executable,str(d.ROOT/'sample_runtime.py'),'19091',label,log],check=True)
 try:
    receipt['set']=remote('set',receipt['property']['window'],1)
    sample('bypass_enabled')
 finally:
    receipt['restored']=remote('restore',receipt['property']['window'],receipt['property']['before'])
    (p/'receipt.json').write_text(json.dumps(receipt,indent=2))
 sample('bypass_restored')
 print('Property restored; evidence '+str(p))
finally:s.client.close()
