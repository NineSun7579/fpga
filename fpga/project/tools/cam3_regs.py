# -*- coding: utf-8 -*-
"""Read cam3's OV5640 format/ISP registers (read-only) to check RGB565 vs RAW."""
import os
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.203", "linaro", "123456"
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project"

# (reg, name) - OV5640 output/ISP config
REGS = [
    (0x300A, "chip ID hi"),
    (0x300B, "chip ID lo"),
    (0x4300, "FORMAT (0x6x=RGB565, 0x0x=RAW)"),
    (0x501F, "ISP fmt mux (0=YUV/RGB,2=RAW,1=RGB?)"),
    (0x5001, "ISP ctrl (bit0=awb...)"),
    (0x5000, "ISP ctrl"),
    (0x503D, "test pattern (0x80=on,0=off)"),
    (0x3A00, "AEC night mode / cmd"),
    (0x3503, "AEC manual ctrl"),
    (0x350A, "AEC gain hi"),
    (0x350B, "AEC gain lo"),
    (0x3500, "exp hi"),
    (0x3501, "exp mid"),
    (0x3502, "exp lo"),
    (0x5180, "AWB ctrl"),
    (0x5035, "??"),
    (0x4740, "polarity"),
    (0x4713, "??"),
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, 22, USER, PW, timeout=10, allow_agent=False, look_for_keys=False)


def sh(cmd, t=120, show=True):
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
sftp.close()

sh("killall -9 camview 2>/dev/null; pkill -9 -f '[r]un_camview' 2>/dev/null; sleep 4; echo stopped")
try:
    body = ["import sys; sys.path.insert(0,'/tmp')",
            "import cam3_i2c_pt as m",
            "d=m.PciDriver()",
            "cam=m.CamI2c(d,0x20000400,verbose=False)"]
    for r, nm in REGS:
        body.append("print('0x%04X %-9s = 0x%%02X'%%cam.read(0x%04X))" % (r, nm, r))
    body.append("d.close()")
    s2 = c.open_sftp()
    with s2.open("/tmp/_rd.py", "w") as f:
        f.write("\n".join(body) + "\n")
    s2.close()
    sh("python3 /tmp/_rd.py 2>&1", t=180)
finally:
    sh("rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh "
       "> /tmp/camview.log 2>&1 < /dev/null & sleep 2; echo restarted")
c.close()
print("DONE")
