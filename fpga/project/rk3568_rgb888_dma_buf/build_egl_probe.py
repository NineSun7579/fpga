"""Isolated native ARM build, including an explicit existing Mali dependency."""
import json,shlex,time,sys,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh
root=Path(__file__).resolve().parent
evidence=root/('egl_probe_build_'+str(time.time_ns()));evidence.mkdir()
remote='/userdata/linaro/ov56401-'+evidence.name
c=board_ssh.connect()
try:
    rc,o,e=board_ssh.run(c,'mkdir -p '+shlex.quote(remote),timeout=20,sudo=False)
    if rc:raise RuntimeError(e)
    with c.open_sftp() as s:
        for name in ('egl_swap_probe.c','egl_abi.h'):
            s.put(str(root/'egl_swap_probe'/name),remote+'/'+name)
    command='gcc -O2 -std=c11 -Wall -Wextra -Werror -fPIC -shared '+shlex.quote(remote+'/egl_swap_probe.c')+' -o '+shlex.quote(remote+'/libegl_swap_probe.so')+' -ldl -pthread -Wl,--no-as-needed /lib/aarch64-linux-gnu/libmali.so.1 -Wl,--as-needed'
    rc,o,e=board_ssh.run(c,command,timeout=40,sudo=True)
    (evidence/'build.log').write_text(o+e)
    if rc:raise RuntimeError(e)
    rc,o,e=board_ssh.run(c,'readelf -d '+shlex.quote(remote+'/libegl_swap_probe.so')+'; sha256sum '+shlex.quote(remote+'/libegl_swap_probe.so'),timeout=20,sudo=True)
    (evidence/'elf.log').write_text(o+e)
    assert 'libmali.so.1' in o
    sha=o.splitlines()[-1].split()[0]
    manifest={'remote':remote,'library':remote+'/libegl_swap_probe.so','sha256':sha,'source_sha256':hashlib.sha256((root/'egl_swap_probe/egl_swap_probe.c').read_bytes()).hexdigest(),'command':command}
    (evidence/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps(manifest,indent=2))
finally:c.close()
