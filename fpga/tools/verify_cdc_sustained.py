import sys,time,json,signal,fcntl
from pathlib import Path
sys.path.insert(0,'/tmp')
import cam3_i2c_pt as m
assert Path('/sys/bus/pci/devices/0002:21:00.0/driver').is_symlink()
out=Path('/tmp/cdc_sustained_evidence');out.mkdir(exist_ok=True)
d=m.PciDriver()
def snap():
    return [(time.monotonic(),[d.read32(b+x) for x in (0x10,0x20,0xf0)]) for b in (0x20000000,0x20000200,0x20000400)]
def read(a,n):
    op=m.DmaOp();op.ddr3_addr=a;op.total_length=n
    signal.alarm(8)
    try:
        assert fcntl.ioctl(d.fd,m.F2H_CMD,op,True)==0
        return bytes(d.rx[:n])
    finally:signal.alarm(0)
def stage_snapshot(base):
    for attempt in range(30):
        seq0=d.read32(base+0x1c0)
        counts=[d.read32(base+x) for x in (0x190,0x1a0,0x1b0)]
        seq1=d.read32(base+0x1c0)
        if seq0==seq1 and seq1>=2:
            return dict(seq=seq1,input=counts[0],output=counts[1],drop=counts[2])
    return dict(seq=seq1,input=counts[0],output=counts[1],drop=counts[2],unstable=True,seq_before=seq0)
last_read={}
original_read32=d.read32
def traced_read32(address):
    last_read.update(address=hex(address),t=time.monotonic())
    return original_read32(address)
d.read32=traced_read32
records=[]
try:
    rows=[]
    for sample in range(241):
        rows.append(dict(t=time.monotonic(),cams=[{hex(x):d.read32(base+x) for x in range(0,256,16)} for base in (0x20000000,0x20000200,0x20000400)]))
        rows[-1]['cdc']=[stage_snapshot(base) for base in (0x20000000,0x20000200,0x20000400)]
        time.sleep(0.5)
    (out/'registers.json').write_text(json.dumps(rows,indent=2))
    for cam in range(3):
        start=rows[0]['cams'][cam];end=rows[-1]['cams'][cam]
        dt=rows[-1]['t']-rows[0]['t']
        print('CAM',cam+1,'success/s',((end['0xf0']-start['0xf0'])&0xffffffff)/dt,
              'offered_pixels',sorted(set(r['cams'][cam]['0x30'] for r in rows)),
              'faults',sorted(set(hex(r['cams'][cam]['0x0']) for r in rows)),
              'overflow_count_delta',((end['0xa0']>>16)-(start['0xa0']>>16))&65535,
              'short_count_delta',((end['0xa0']&65535)-(start['0xa0']&65535))&65535,flush=True)
    for cam in range(3):
        print('CDC',cam+1,{key:sorted(set(row['cdc'][cam][key] for row in rows)) for key in ('input','output','drop')},flush=True)
    a=snap();time.sleep(3);b=snap()
    rates=[[(y-x)&0xffffffff for x,y in zip(u[1],v[1])] for u,v in zip(a,b)]
    rates=[[x/(v[0]-u[0]) for x in r] for r,u,v in zip(rates,a,b)]
    print('PCLK_Hz VSYNC_s FRAMES_s',rates,flush=True)
    for k in range(3):
        for cam,banks in [(1,[0x800000,0xa00000]),(2,[0xc00000,0xe00000]),(3,[0x1000000,0x1200000])]:
            for bank,addr in enumerate(banks):
                name='cam%d_bank%d_%d'%(cam,bank,k)
                before=read(addr+614400,16).hex();raw=read(addr,614400);after=read(addr+614400,16).hex()
                (out/(name+'.rgb565')).write_bytes(raw)
                records.append(dict(name=name,tag_before=before,tag_after=after))
        time.sleep(0.4)
finally:
    (out/'registers.json').write_text(json.dumps(rows,indent=2))
    (out/'last_read.json').write_text(json.dumps(last_read,indent=2))
    d.close()
(out/'capture.json').write_text(json.dumps(dict(rates=rates,frames=records),indent=2))
