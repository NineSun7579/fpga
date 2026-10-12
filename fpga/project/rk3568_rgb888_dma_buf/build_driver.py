"""Compile the isolated candidate on RK3568 without loading it."""
from pathlib import Path
import hashlib
import argparse
import json
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh

root=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--source',type=Path,default=root/'candidate_driver')
args=parser.parse_args()
source=args.source.resolve()
source.relative_to(root)
evidence=root/('driver_build_'+str(time.time_ns()))
evidence.mkdir()
remote='/userdata/linaro/ov56401-rgb888-'+evidence.name
manifest={'source':str(source),'remote':remote,'scope':'compile only, no module load','sources':{}}
client=board_ssh.connect()
try:
    rc,out,err=board_ssh.run(client,'mkdir -p '+remote+'/tmp',timeout=20)
    if rc: raise RuntimeError(out+err)
    with client.open_sftp() as sftp:
        for name in ('pango_zc.c','pango_zc_uapi.h','Makefile'):
            p=source/name
            sftp.put(str(p),remote+'/'+name)
            manifest['sources'][name]=hashlib.sha256(p.read_bytes()).hexdigest()
    command='cd '+remote+' && env TMPDIR='+remote+'/tmp make KDIR=/usr/src/linux-headers-6.1-rockchip -j1 && readelf -h pango_zc.ko && readelf -p .modinfo pango_zc.ko && sha256sum pango_zc.ko'
    rc,out,err=board_ssh.run(client,command,timeout=180)
    manifest['return_code']=rc
    (evidence/'build.log').write_text(out+err,encoding='utf-8')
    if rc: raise RuntimeError('Build failed: '+str(evidence/'build.log'))
    with client.open_sftp() as sftp:
        sftp.get(remote+'/pango_zc.ko',str(evidence/'pango_zc.ko'))
    manifest['module_sha256']=hashlib.sha256((evidence/'pango_zc.ko').read_bytes()).hexdigest()
    print(json.dumps(manifest,indent=2))
finally:
    (evidence/'manifest.json').write_text(json.dumps(manifest,indent=2))
    client.close()
