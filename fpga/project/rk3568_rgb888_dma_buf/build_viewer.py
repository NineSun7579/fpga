"""Build an isolated ARM64 viewer; never install or stop the running viewer."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shlex
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh

root=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--source',type=Path,required=True)
args=parser.parse_args()
source=args.source.resolve()
source.relative_to(root)
assert (source/'detview.pro').is_file()
targets=re.findall(r'^\s*TARGET\s*=\s*([A-Za-z0-9_-]+)\s*$',(source/'detview.pro').read_text(),re.M)
if len(targets)!=1: raise RuntimeError('Expected one explicit viewer target')
target=targets[0]
evidence=root/('viewer_build_'+str(time.time_ns()))
evidence.mkdir()
remote='/userdata/linaro/ov56401-rgb888-'+evidence.name
manifest={'source':str(source),'remote':remote,'scope':'isolated build only','sources':{}}
client=board_ssh.connect()
try:
    rc,out,err=board_ssh.run(client,'mkdir -p '+shlex.quote(remote+'/tmp'),timeout=20)
    if rc: raise RuntimeError(out+err)
    with client.open_sftp() as sftp:
        directories={remote}
        for path in sorted(source.rglob('*')):
            if not path.is_file(): continue
            relative=path.relative_to(source)
            if 'local_build' in relative.parts or '__pycache__' in relative.parts: continue
            dest=remote+'/'+relative.as_posix()
            parent=Path(relative).parent
            ancestors=list(parent.parents)[::-1]+[parent]
            for ancestor in ancestors:
                directory=remote+'/'+ancestor.as_posix()
                if directory not in directories:
                    try: sftp.mkdir(directory)
                    except OSError:
                        sftp.stat(directory)
                    directories.add(directory)
            sftp.put(str(path),dest)
            manifest['sources'][relative.as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    cmd='cd '+shlex.quote(remote)+' && env TMPDIR='+shlex.quote(remote+'/tmp')+' qmake detview.pro && env TMPDIR='+shlex.quote(remote+'/tmp')+' make -j1'
    rc,out,err=board_ssh.run(client,cmd,timeout=600)
    (evidence/'build.log').write_text(out+err,encoding='utf-8')
    manifest['build_return_code']=rc
    if rc: raise RuntimeError('Build failed: '+str(evidence/'build.log'))
    rc,out,err=board_ssh.run(client,'sha256sum '+shlex.quote(remote+'/'+target),timeout=20)
    if rc: raise RuntimeError(out+err)
    manifest['executable_sha256']=out.split()[0]
    manifest['executable']=remote+'/'+target
    print(json.dumps(manifest,indent=2))
finally:
    (evidence/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    client.close()
