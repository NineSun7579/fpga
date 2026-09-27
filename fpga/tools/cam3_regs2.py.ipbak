# -*- coding: utf-8 -*-
"""Read cam3's key OV5640 registers REPEATEDLY to tell real values from flaky reads."""
import os
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.241", "linaro", "123456"
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project"

# reg -> value the shared init table writes (None = table does not set it)
EXPECT = {
    0x3035: 0x11, 0x4713: 0x03, 0x460c: 0x22, 0x4837: 0x22,
    0x4300: 0x61, 0x501F: 0x01, 0x5001: 0xA3, 0x503D: 0x00,
    0x3A00: None, 0x350B: None, 0x4740: None,
}
REGS = list(EXPECT.keys())

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, 22, USER, PW, timeout=10, allow_agent=False, look_for_keys=False)


def sh(cmd, t=180, show=True):
    full = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    _, o, e = c.exec_command(full, timeout=t)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    if show:
        print("$", cmd)
        print(out.rstrip())
        if err.strip() and "password for" not in err:
            print("ERR:", err.rstrip()[:300])
    return out


sftp = c.open_sftp()
sftp.put(os.path.join(ROOT, "tools", "cam3_i2c_pt.py"), "/tmp/cam3_i2c_pt.py")

body = ["import sys; sys.path.insert(0,'/tmp')",
        "import cam3_i2c_pt as m",
        "d=m.PciDriver()",
        "cam=m.CamI2c(d,0x20000400,verbose=False)",
        "regs=%r" % (REGS,),
        "for k in range(5):",
        "    line=[]",
        "    for r in regs:",
        "        try: line.append('%04X=%02X'%(r,cam.read(r)))",
        "        except Exception: line.append('%04X=ERR'%r)",
        "    print(' '.join(line))",
        "d.close()"]
with sftp.open("/tmp/_rd2.py", "w") as f:
    f.write("\n".join(body) + "\n")
sftp.close()

sh("killall -9 camview 2>/dev/null; pkill -9 -f '[r]un_camview' 2>/dev/null; sleep 4; echo stopped")
try:
    sh("python3 /tmp/_rd2.py 2>&1")
finally:
    sh("rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh "
       "> /tmp/camview.log 2>&1 < /dev/null & sleep 2; echo restarted")
c.close()
print("DONE")
