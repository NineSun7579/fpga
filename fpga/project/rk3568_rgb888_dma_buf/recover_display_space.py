from pathlib import Path
import shlex,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh
code=r'''
import subprocess,pathlib,shutil,hashlib,time
subprocess.run(['systemctl','stop','syslog.socket','rsyslog.service'],check=True)
dest=pathlib.Path('/userdata/linaro/ov56401-recovery-logs-'+str(time.time_ns()))
dest.mkdir()
try:
    for name in ('syslog','kern.log'):
        source=pathlib.Path('/var/log')/name
        target=dest/name
        shutil.copy2(source,target)
        assert hashlib.sha256(source.read_bytes()).digest()==hashlib.sha256(target.read_bytes()).digest()
        with source.open('wb'):pass
finally:subprocess.run(['systemctl','start','syslog.socket','rsyslog.service'],check=True)
print('Logs preserved:',dest)
subprocess.run(['df','-h','/'],check=True)
subprocess.run(['systemctl','restart','lightdm'],check=True)
'''
client=board_ssh.connect()
try:
    rc,out,err=board_ssh.run(client,'python3 -c '+shlex.quote(code),timeout=90,sudo=True)
    print(out+err)
    if rc:raise RuntimeError('Display recovery failed')
finally:client.close()
