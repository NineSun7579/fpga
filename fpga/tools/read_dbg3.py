# -*- coding: utf-8 -*-
"""Host: read per-camera debug counters through board_peek.py (driver must be idle)."""
import paramiko, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HOST, USER, PW = "192.168.10.203", "linaro", "123456"
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project"
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, 22, USER, PW, timeout=10, banner_timeout=15, auth_timeout=15,
          allow_agent=False, look_for_keys=False)
def run(cmd, t=120):
    full = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    _, o, e = c.exec_command(full, timeout=t)
    return o.read().decode('utf-8','replace'), e.read().decode('utf-8','replace')

sftp=c.open_sftp(); sftp.put(os.path.join(ROOT,'tools','board_peek.py'),'/tmp/board_peek.py'); sftp.close()

out,err=run("killall -9 camview 2>/dev/null; pkill -9 -f '[r]un_camview' 2>/dev/null; sleep 2; echo stopped")
print(out.strip(), err.strip()[:150])

offs=[('pclk',0x10),('vsyncs',0x20),('cam_words',0x30),('i2c_stat',0x50),('i2cid',0x60),
      ('aw/b',0x70),('href_raw',0x90),('beat_cnt',0xa0),('sys',0xd0),('beat_last',0xf0)]
bases={'cam1':0x20000000,'cam2':0x20000200,'cam3':0x20000400}
labels=['pclk','vsyncs','cam_words','i2c_stat','i2cid','aw/b','href_raw','beat_cnt','sys','beat_last']
for cam,base in bases.items():
    addrs=' '.join('0x%08X'%(base+o) for _,o in offs)
    out,err=run("python3 /tmp/board_peek.py %s 2>&1"%addrs)
    print('==',cam)
    for ln in out.splitlines():
        if '=' in ln: print('   ',ln.strip())
    if err.strip(): print('   ERR',err.strip()[:150])

out,err=run("rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh > /tmp/camview.log 2>&1 < /dev/null & sleep 2; echo restarted")
print(out.strip())
c.close()
