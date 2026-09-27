# -*- coding: utf-8 -*-
"""Read the per-camera frame-completion TAG (base+0x96000) over time, to measure the
true frame rate that the display ping/pong logic sees. Viewer must be stopped for
the whole session (driver is exclusive)."""
import os
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.241", "linaro", "123456"
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project"

BOARD = r'''
import ctypes, fcntl, mmap, os, signal, struct, sys, time
def _al(s,f): raise Exception("timeout")
signal.signal(signal.SIGALRM,_al)
class O(ctypes.Structure):
    _fields_=[('cur',ctypes.c_uint32),('off',ctypes.c_uint32),('cmd',ctypes.c_uint32),
              ('ddr',ctypes.c_uint32),('ln',ctypes.c_uint32),('rb',ctypes.c_void_p),('wb',ctypes.c_void_p)]
def I(n): return 0xC0000000|(4<<16)|(0x53<<8)|n
FD=os.open('/dev/pango_pci_driver',os.O_RDWR|os.O_SYNC)
for c in (0,1):
    o=O(); o.cmd=c; o.ln=4194304
    signal.alarm(8); fcntl.ioctl(FD,I(2),o,True); signal.alarm(0)
RX=mmap.mmap(FD,4194304,prot=mmap.PROT_READ|mmap.PROT_WRITE,flags=mmap.MAP_SHARED,offset=1048576)
def rd(a,n):
    o=O(); o.off=0; o.ddr=a; o.ln=n
    signal.alarm(20)
    try: fcntl.ioctl(FD,I(5),o,True)
    finally: signal.alarm(0)
    return bytes(RX[0:n])
TAGS={'c1ping':0x00896000,'c1pong':0x00A96000,'c2ping':0x00C96000,'c2pong':0x00E96000,
      'c3ping':0x01096000,'c3pong':0x01296000}
def snap():
    d={}
    for k,a in TAGS.items():
        w=struct.unpack('<I',rd(a,4))[0]
        d[k]=w
    return d
for i in range(4):
    d=snap()
    print(i, time.time(), ' '.join('%s=0x%08X(%d)'%(k,v,v) for k,v in d.items()))
    time.sleep(3)
'''

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, 22, USER, PW, timeout=10, banner_timeout=15, auth_timeout=15,
          allow_agent=False, look_for_keys=False)


def run(cmd, t=180):
    full = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    _, o, e = c.exec_command(full, timeout=t)
    return o.read().decode("utf-8", "replace"), e.read().decode("utf-8", "replace")


print(run("killall -9 camview 2>/dev/null; pkill -9 -f '[r]un_camview' 2>/dev/null; sleep 3; echo stopped")[0].strip())

sftp = c.open_sftp()
with sftp.open("/tmp/tagprobe.py", "w") as f:
    f.write(BOARD)
sftp.close()

out, err = run("python3 /tmp/tagprobe.py 2>&1", t=120)
print(out.strip())
if err.strip():
    print("ERR", err.strip()[:400])

print(run("rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh > /tmp/camview.log 2>&1 < /dev/null & sleep 3; echo restarted")[0].strip())
c.close()
