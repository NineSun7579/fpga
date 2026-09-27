"""One driver open, F2H only. No camera register writes or SCCB transactions."""
import sys, time, json, signal, fcntl, hashlib
from pathlib import Path
sys.path.insert(0, '/tmp')
import cam3_i2c_pt as m

assert Path('/sys/bus/pci/devices/0002:21:00.0/driver').is_symlink(), 'probe unbound: no ioctl permitted'
out=Path('/tmp/cam2_raw_evidence'); out.mkdir(exist_ok=True)
d=m.PciDriver()
records=[]
def read(addr,n):
    op=m.DmaOp(); op.ddr3_addr=addr; op.total_length=n
    signal.alarm(8)
    try:
        rc=fcntl.ioctl(d.fd,m.F2H_CMD,op,True)
        if rc != 0: raise IOError('F2H rc='+str(rc))
        return bytes(d.rx[:n])
    finally: signal.alarm(0)
try:
    for sample in range(3):
        for bank,addr in [('ping',0x00c00000),('pong',0x00e00000)]:
            name='cam2_%s_%d'%(bank,sample)
            before=read(addr+614400,16).hex()
            start=time.monotonic()
            raw=read(addr,614400)
            duration=time.monotonic()-start
            after=read(addr+614400,16).hex()
            (out/(name+'.rgb565')).write_bytes(raw)
            rec=dict(name=name,address=hex(addr),bytes=len(raw),seconds=duration,tag_before=before,tag_after=after,sha256=hashlib.sha256(raw).hexdigest())
            records.append(rec); print(json.dumps(rec),flush=True)
        time.sleep(0.3)
finally:
    d.close()
    (out/'capture.json').write_text(json.dumps(records,indent=2))
