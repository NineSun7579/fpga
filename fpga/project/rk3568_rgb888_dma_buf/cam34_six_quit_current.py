from pathlib import Path
import importlib.util,json,shlex
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh
root=Path(__file__).resolve().parent
known=json.loads((root/'viewer_build_1791627094983637700/manifest.json').read_bytes())
client=board_ssh.connect();remote='/userdata/linaro/ov56401-cam34-six-lifecycle.py'
try:
 with client.open_sftp() as s:s.put(str(root/'deploy_remote_helper.py'),remote)
 code="""import importlib.util,json
spec=importlib.util.spec_from_file_location('lifecycle',REMOTE);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
ids=m.owners()
assert len(ids)==1,ids
identity=m.identity(ids[0])
assert identity['exe']==KNOWN['executable'] and identity['sha256']==KNOWN['executable_sha256'],identity
print(json.dumps(m.stop({'identity':identity,'env':{'DISPLAY':':0','XAUTHORITY':'/var/run/lightdm/root/:0'},'timeout':30})))
"""
 payload='REMOTE='+repr(remote)+chr(10)+'KNOWN='+repr(known)+chr(10)+code
 rc,o,e=board_ssh.run(client,'python3 -c '+shlex.quote(payload),timeout=45,sudo=True)
 (root/'cam34_six_retirement.log').write_text(o+e,encoding='utf-8');print('RETIRE_RC',rc,o,e[-800:]);assert rc==0
finally:client.close()
