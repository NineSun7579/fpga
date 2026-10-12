"""Build an isolated complete thumbnail viewer on RK3568, never install it."""
from pathlib import Path
import json
import hashlib
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh

root=Path(__file__).resolve().parent
async_candidate='--async-candidate' in sys.argv
background_candidate='--background-candidate' in sys.argv
batch='--batch' in sys.argv or async_candidate or background_candidate
six_camera='--six-camera' in sys.argv or batch
remote='/userdata/linaro/fpga-zero-copy-viewer'+('-six-background' if background_candidate else '-six-async' if async_candidate else '-six-batch' if batch else '-six' if six_camera else '')
prefix='six_background_' if background_candidate else 'six_async_' if async_candidate else 'six_batch_' if batch else 'six_' if six_camera else ''
binary='detview_six_camera_background_candidate' if background_candidate else 'detview_six_camera_async_candidate' if async_candidate else 'detview_six_camera_candidate' if six_camera else 'detview_thumbnail_candidate'
client=board_ssh.connect()
try:
    rc,out,err=board_ssh.run(client,'mkdir -p '+remote)
    if rc:
        raise RuntimeError(out+err)
    source=root/('six_camera_background_viewer_src' if background_candidate else 'six_camera_async_viewer_src' if async_candidate else 'six_camera_batch_viewer_src' if batch else 'six_camera_viewer_src' if six_camera else 'thumbnail_viewer_src')
    files=[p for p in source.rglob('*') if p.is_file() and p.suffix in ('.cpp','.h','.hpp','.pro') and not p.name.startswith('moc_')]
    with client.open_sftp() as sftp:
        for path in files:
            relative=path.relative_to(source).as_posix()
            if '/' in relative:
                rc,out,err=board_ssh.run(client,'mkdir -p '+remote+'/'+relative.rsplit('/',1)[0])
                if rc:
                    raise RuntimeError(out+err)
            sftp.put(str(path),remote+'/'+relative)
    rc,out,err=board_ssh.run(client,'cd '+remote+'; qmake detview.pro && make -j2 >build.log 2>&1',sudo=True,timeout=600)
    with client.open_sftp() as sftp:
        sftp.get(remote+'/build.log',str(root/(prefix+'viewer_build.log')))
        if rc==0:
            sftp.get(remote+'/'+binary,str(root/(prefix+'detview_thumbnail_candidate_aarch64')))
    manifest={'return_code':rc,'sources':{p.relative_to(source).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    if rc==0:
        manifest['binary_sha256']=hashlib.sha256((root/(prefix+'detview_thumbnail_candidate_aarch64')).read_bytes()).hexdigest()
    (root/(prefix+'viewer_build_manifest.json')).write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('return_code',rc,out,err)
    if rc:
        print((root/(prefix+'viewer_build.log')).read_text(errors='replace')[-6000:])
        raise SystemExit(rc)
    for flag in ('--thumbnail-selftest','--display-latency-selftest','--vision-selftest'):
        rc,out,err=board_ssh.run(client,'cd '+remote+'; QT_QPA_PLATFORM=offscreen ./'+binary+' '+flag,sudo=True,timeout=30)
        (root/(prefix+flag[2:]+'.log')).write_text(out+err,encoding='utf-8')
        print(flag,rc,out[-600:])
        if rc:
            raise SystemExit(rc)
finally:
    client.close()
