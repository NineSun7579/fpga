# -*- coding: utf-8 -*-
"""Check cam3 liveness + raw row bytes after the driver reload."""
import os
import struct
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER, PW = "192.168.10.241", "linaro", "123456"
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project"

BODY = r'''
import ctypes, fcntl, mmap, os, signal, struct, sys, time
class TO(Exception): pass
def _al(s,f): raise TO()
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
def w32(a,v):
    o=O(); o.off=0; o.ddr=a; o.ln=16
    signal.alarm(8)
    try: fcntl.ioctl(FD,I(4),o,True)
    finally: signal.alarm(0)
def reg(a): return struct.unpack('<I', rd(a,4))[0]
print('cam3 frames 0xF0 =', reg(0x200004F0))
print('cam3 vsync  0x20 =', reg(0x20000420))
print('cam3 cam_en 0x40 =', reg(0x20000440))
print('cam1 frames 0xF0 =', reg(0x200000F0))
time.sleep(2.5)
print('cam3 frames 0xF0 =', reg(0x200004F0))
print('cam3 vsync  0x20 =', reg(0x20000420))
b = rd(0x0104B000, 1280)
w = struct.unpack('<640H', b)
print('row240 first16 =', ['%04X'%v for v in w[:16]])
print('row240 nonzero words =', sum(1 for v in w if v))
b2 = rd(0x01000000, 10240)
print('frame head nonzero bytes =', sum(1 for x in b2 if x), 'of', len(b2))
'''

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, 22, USER, PW, timeout=10, allow_agent=False, look_for_keys=False)


def mysh(cmd, t=120, show=True):
    full = "echo '%s' | sudo -S bash -c %s" % (PW, "'" + cmd.replace("'", "'\\''") + "'")
    _, o, e = c.exec_command(full, timeout=t)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    if show:
        print("$", cmd)
        print(out.rstrip())
        if err.strip() and "password for" not in err:
            print("ERR:", err.rstrip()[:400])
    return out


sftp = c.open_sftp()
with sftp.open("/tmp/_chk.py", "w") as f:
    f.write(BODY)
sftp.close()

mysh("killall -9 camview 2>/dev/null; pkill -9 -f '[r]un_camview' 2>/dev/null; sleep 4; echo stopped")
try:
    mysh("python3 /tmp/_chk.py 2>&1")
finally:
    mysh("rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh "
         "> /tmp/camview.log 2>&1 < /dev/null & sleep 2; echo restarted")
c.close()
print("DONE")
