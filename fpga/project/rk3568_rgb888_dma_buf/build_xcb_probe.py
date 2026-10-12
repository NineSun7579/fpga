"""Native ARM XCB probe build and a real checked no-op smoke test."""
import json,shlex,time,sys,hashlib,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh
root=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--classify',action='store_true');args=parser.parse_args()
kind='xcb_request_probe' if args.classify else 'xcb_reply_probe'
p=root/(kind+'_build_'+str(time.time_ns()));p.mkdir()
remote='/userdata/linaro/ov56401-'+p.name
c=board_ssh.connect()
try:
    rc,o,e=board_ssh.run(c,'mkdir -p '+shlex.quote(remote),timeout=15,sudo=False)
    if rc:raise RuntimeError(e)
    with c.open_sftp() as s:
        for name in (kind+'.c','xcb_abi.h'):s.put(str(root/kind/name),remote+'/'+name)
    lib=remote+'/lib'+kind+'.so'
    cmd='gcc -O2 -std=c11 -Wall -Wextra -Werror -fPIC -shared '+shlex.quote(remote+'/'+kind+'.c')+' -o '+shlex.quote(lib)+' -ldl -Wl,--no-as-needed -lxcb -Wl,--as-needed'
    rc,o,e=board_ssh.run(c,cmd,timeout=40,sudo=True);(p/'build.log').write_text(o+e)
    if rc:raise RuntimeError(e)
    rc,o,e=board_ssh.run(c,'readelf -d '+shlex.quote(lib)+'; sha256sum '+shlex.quote(lib),timeout=15,sudo=True)
    (p/'elf.log').write_text(o+e);assert 'libxcb.so.1' in o
    sha=o.splitlines()[-1].split()[0]
    code='''import ctypes as C
class Cookie(C.Structure):_fields_=[('sequence',C.c_uint)]
x=C.CDLL(None)
x.xcb_connect.argtypes=[C.c_char_p,C.c_void_p];x.xcb_connect.restype=C.c_void_p
x.xcb_connection_has_error.argtypes=[C.c_void_p]
x.xcb_no_operation_checked.argtypes=[C.c_void_p];x.xcb_no_operation_checked.restype=Cookie
x.xcb_request_check.argtypes=[C.c_void_p,Cookie];x.xcb_request_check.restype=C.c_void_p
x.xcb_disconnect.argtypes=[C.c_void_p]
connection=x.xcb_connect(b':0',None)
assert connection and x.xcb_connection_has_error(connection)==0
try:assert x.xcb_request_check(connection,x.xcb_no_operation_checked(connection)) is None
finally:x.xcb_disconnect(connection)
print('Real XCB checked no-op forwarding PASS')
'''
    flag='DETVIEW_XCB_REQUEST_PROBE' if args.classify else 'DETVIEW_XCB_REPLY_PROBE'
    rc,o,e=board_ssh.run(c,'env DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 '+flag+'=1 LD_PRELOAD='+shlex.quote(lib)+' python3 -c '+shlex.quote(code),timeout=20,sudo=True)
    (p/'smoke.log').write_text(o+e)
    if rc:raise RuntimeError(e)
    manifest={'library':lib,'sha256':sha,'remote':remote,'flag':flag,'source_sha256':hashlib.sha256((root/kind/(kind+'.c')).read_bytes()).hexdigest(),'command':cmd}
    (p/'manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest,indent=2));print(o)
finally:c.close()
