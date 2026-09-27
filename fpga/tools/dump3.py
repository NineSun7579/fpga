# -*- coding: utf-8 -*-
"""Host-side: upload dump_cam3_frame.py, stop viewer, dump cam1/2/3 DDR frames, fetch PPMs."""
import paramiko, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HOST, USER, PW = "192.168.10.241", "linaro", "123456"
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project"
LOCAL_SCRIPT = os.path.join(ROOT, "tools", "dump_cam3_frame.py")
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, 22, USER, PW, timeout=10, banner_timeout=15, auth_timeout=15,
          allow_agent=False, look_for_keys=False)

def run(cmd, t=180):
    full = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    _, o, e = c.exec_command(full, timeout=t)
    return o.read().decode('utf-8', 'replace'), e.read().decode('utf-8', 'replace')

sftp = c.open_sftp()
sftp.put(LOCAL_SCRIPT, "/tmp/dump_cam3_frame.py")
sftp.close()

# stop viewer so the driver is idle for bulk DDR reads
out, err = run("killall -9 camview 2>/dev/null; pkill -9 -f '[r]un_camview' 2>/dev/null; sleep 2; echo stopped")
print(out.strip(), err.strip()[:200])

bases = {"c1": "0x00800000", "c2": "0x00C00000", "c3": "0x01000000", "c2p": "0x00E00000", "c3p": "0x01200000"}
for name, base in bases.items():
    out, err = run("python3 /tmp/dump_cam3_frame.py %s /tmp/%s.ppm 2>&1" % (base, name))
    print(name, base, out.strip()[-120:], err.strip()[:150])

sftp = c.open_sftp()
for name in bases:
    try:
        sftp.get("/tmp/%s.ppm" % name, os.path.join(ROOT, "%s_raw.ppm" % name))
        print("fetched", name, os.path.getsize(os.path.join(ROOT, "%s_raw.ppm" % name)))
    except Exception as e:
        print("fetch fail", name, e)
sftp.close()

# restart viewer
out, err = run("rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh > /tmp/camview.log 2>&1 < /dev/null & sleep 3; echo restarted")
print(out.strip())
c.close()
