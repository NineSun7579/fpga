"""Read or temporarily set the current desktop compositor through its actual session bus."""
import argparse,json,shlex,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh
parser=argparse.ArgumentParser();parser.add_argument('--set',choices=['true','false']);args=parser.parse_args()
code=r'''
import pathlib,subprocess,os,json
pids=[p for p in pathlib.Path('/proc').iterdir() if p.name.isdigit() and (p/'comm').exists() and (p/'comm').read_text().strip()=='xfwm4']
assert len(pids)==1
p=pids[0]
env=dict(x.decode().split('=',1) for x in (p/'environ').read_bytes().split(b'\0') if x)
uid=int(next(x for x in (p/'status').read_text().splitlines() if x.startswith('Uid:')).split()[1])
query=['xfconf-query','-c','xfwm4','-p','/general/use_compositing']
def run(argv):
 return subprocess.check_output(['sudo','-u','#'+str(uid),'env',*[k+'='+env[k] for k in ('DISPLAY','DBUS_SESSION_BUS_ADDRESS','XAUTHORITY') if k in env],*argv],text=True).strip()
before=run(query)
if SET is not None:run(query+['-s',SET])
print(json.dumps({'pid':int(p.name),'before':before,'after':run(query),'vblank_mode':run(['xfconf-query','-c','xfwm4','-p','/general/vblank_mode'])}))
'''
c=board_ssh.connect()
try:
 rc,out,err=board_ssh.run(c,'python3 -c '+shlex.quote('SET='+repr(args.set)+'\n'+code),timeout=25,sudo=True)
 print(out+err)
 if rc:raise RuntimeError('Compositor query failed')
finally:c.close()
