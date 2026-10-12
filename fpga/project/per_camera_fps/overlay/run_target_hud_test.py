import argparse
import json
from pathlib import Path
import shlex
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'project/tools'))
from board_host import ssh_connect
p=argparse.ArgumentParser()
p.add_argument('--build-receipt',required=True,type=Path)
a=p.parse_args()
r=json.loads(a.build_receipt.read_text())
assert r['status']=='built'
base=r['remote_directory']
client=ssh_connect()
try:
    command='cd '+shlex.quote(base+'/src')+' && python3 gpu_hud_test_generate.py '+shlex.quote(base+'/hud_test')+' && cd '+shlex.quote(base+'/hud_test')+' && qmake gpu_hud_test.pro && make -j2'
    _,out,err=client.exec_command(command+' 2>&1',timeout=60)
    text=out.read().decode(errors='replace');code=out.channel.recv_exit_status()
    Path(__file__).with_name('target_hud_build.log').write_text(text,encoding='utf-8')
    assert code==0,text[-3000:]
    command="sudo -S -p '' env DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 QT_QPA_PLATFORM=xcb QT_XCB_GL_INTEGRATION=xcb_egl QT_OPENGL=es2 "+shlex.quote(base+'/hud_test/gpu_hud_test')
    inp,out,err=client.exec_command(command+' 2>&1',timeout=60)
    inp.write('123456\n');inp.flush();inp.channel.shutdown_write()
    text=out.read().decode(errors='replace');code=out.channel.recv_exit_status()
    Path(__file__).with_name('target_hud_test.log').write_text(text,encoding='utf-8')
    print(text);assert code==0
finally:
    client.close()
