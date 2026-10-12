"""Isolated ModelSim regression. Golden state comes from host/producer intent."""
from __future__ import annotations
from collections import defaultdict, Counter
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
CONTROLLER = HERE.parent / "cooperative_control" / "fpga_v8_coop_control_axil.v"
CONTROLLER_SHA256 = "fec948ff58fbc4fb7f4e70483d8182d052aaa5932c1fd53c0d40930e72a6a2ae"
BASE = 0x40010000


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def xorshift(x):
    x = (x ^ (x << 13)) & 0xffffffff
    x ^= x >> 17
    return (x ^ (x << 5)) & 0xffffffff


def payload(word, beat):
    x = xorshift(0xb71c249d ^ word ^ ((beat * 0x9e3779b9) & 0xffffffff))
    y = xorshift(x)
    z = xorshift(y)
    return (x << 96) | (y << 64) | (z << 32) | ((word + beat) & 0xffffffff)


class Oracle:
    """Ownership model uses a FIFO and immutable producer records, no DUT state."""
    def __init__(self):
        self.reset()

    def reset(self):
        self.banks = [0, 0]
        self.records = [None, None]
        self.ready = []
        self.host = None
        self.active = None
        self.ack = [0, 0, 0]
        self.counts = dict(ack=0, claim=0, raw=0, failed=0, done=0, release=0, accepted=0)
        self.error = 0

    def descriptor(self, src, seq, gen, camera, bank, token, raw):
        if not raw:
            self.counts["raw"] += 1
            self.error = 1
            return None
        out = self.banks.index(0)
        self.records[out] = (src, seq, gen, camera, bank, token)
        self.banks[out] = 1
        self.active = out
        self.counts["accepted"] += 1
        return out

    def done(self):
        bank = self.active
        self.banks[bank] = 2
        self.ready.append(bank)
        self.active = None
        self.counts["done"] += 1
        self.counts["release"] += 1
        return self.records[bank]

    def write(self, offset, data, strb):
        if offset == 0x30:
            if not strb & 1:
                return 0
            bank = data & 1
            if self.host is None and self.ready and self.ready[0] == bank:
                self.ready.pop(0)
                self.host = bank
                self.banks[bank] = 3
                return 0
            self.counts["claim"] += 1
            self.error = 3
            return 2
        if offset in (0x40, 0x44, 0x48):
            i = (offset - 0x40) // 4
            mask = sum(0xff << (8*b) for b in range(4) if strb & (1 << b))
            self.ack[i] = (self.ack[i] & ~mask) | (data & mask)
            return 0
        if offset == 0x4c:
            if not strb & data & 1:
                return 0
            if self.host is not None:
                rec = self.records[self.host]
                if self.ack == [self.host, rec[1], rec[2]]:
                    self.banks[self.host] = 0
                    self.host = None
                    return 0
            self.counts["ack"] += 1
            self.error = 4
            return 2
        return 2

    def read(self, offset):
        fixed = {0: 0x434f4f50, 8: 0x10000, 0x0c: self.ready[0] if self.ready else 0xffffffff,
                 0x4c: 0, 0x50: self.counts["ack"], 0x54: self.counts["claim"],
                 0x58: self.counts["raw"], 0x5c: self.counts["failed"],
                 0x60: self.counts["done"], 0x64: self.counts["release"],
                 0x68: self.counts["accepted"], 0x6c: self.error}
        if offset == 4:
            return (int(self.active is not None) | (bool(self.ready) << 2) |
                    ((self.host is not None) << 3) | ((self.active is not None) << 5) |
                    (bool(self.error) << 6) | (self.banks[0] << 10) | (self.banks[1] << 12)), 0
        if offset in fixed:
            return fixed[offset], 0
        if offset in (0x40, 0x44, 0x48):
            return self.ack[(offset-0x40)//4], 0
        if offset in range(0x10, 0x3c, 4):
            values = [0xffffffff] + [0]*7 + [0xffffffff, 0, 0]
            if self.host is not None:
                src, seq, gen, cam, cam_bank, token = self.records[self.host]
                values = [self.host, seq, gen, 1228800, 0x08000000+self.host*0x200000,
                          cam, cam_bank, src, self.host, token & 0xffffffff, token >> 32]
            return values[(offset-0x10)//4], 0
        return 0, 2

    def state(self):
        return (*self.banks, int(self.active is not None),
                int(self.active is None and 0 in self.banks))


class Suite:
    def __init__(self):
        self.ops = []
        self.expected = defaultdict(list)
        self.model = Oracle()
        self.op = 0
        self.nextid = 0
        self.labels = {}

    def ident(self):
        value = self.nextid % 128
        self.nextid += 1
        return value

    def emit(self, channel, *values):
        self.expected[(self.op, channel)].append(tuple(values))

    def start(self, code, args, label):
        self.op += 1
        self.ops.append((code, list(args)+[0]*(12-len(args))))
        self.labels[self.op] = label

    def end(self):
        self.emit("STATE", *self.model.state())

    def reset(self):
        self.start(0, [], "common reset")
        self.model.reset()
        self.emit("RESET")
        self.end()

    @staticmethod
    def eligible(addr, length, size, burst):
        return (length == 0 and size == 4 and burst in (0, 1) and addr % 16 == 0 and
                BASE <= addr and addr+16 <= BASE+0x1000 and addr % 4096 <= 0xff0)

    def write_events(self, addr, length, size, burst, ident, word, strb, lastmode, prot):
        self.emit("AW", ident, addr, length, size, burst, prot, ident & 1)
        for beat in range(length+1):
            last = beat == length if lastmode == 0 else (False if lastmode == 1 else beat == 0)
            self.emit("W", payload(word, beat), strb, int(last))
        if self.eligible(addr, length, size, burst) and lastmode != 1:
            offset = (addr-BASE)//4
            self.emit("CAW", offset, prot)
            self.emit("CW", word, strb & 15)
            resp = self.model.write(offset, word, strb & 15)
            self.emit("CB", resp)
        else:
            resp = 2
        self.emit("B", ident, resp)

    def write(self, offset, word=0, *, addr=None, length=0, size=4, burst=1, strb=0xffff,
              order=0, lastmode=0, hold=9, label="write"):
        addr = BASE+offset*4 if addr is None else addr
        ident = self.ident()
        prot = ident % 8
        self.start(1, [addr,length,size,burst,ident,word,strb,order,lastmode,prot,hold], label)
        self.write_events(addr,length,size,burst,ident,word,strb,lastmode,prot)
        self.end()

    def read_events(self, addr, length, size, burst, ident, prot):
        self.emit("AR", ident, addr, length, size, burst, prot, ident & 1)
        if self.eligible(addr,length,size,burst):
            offset = (addr-BASE)//4
            data, resp = self.model.read(offset)
            self.emit("CAR",offset,prot)
            self.emit("CR",data,resp)
        else:
            data, resp = 0, 2
        for beat in range(length+1):
            self.emit("R",ident,data,resp,int(beat == length))

    def read(self, offset, *, addr=None, length=0, size=4, burst=1, hold=7, ident=None, label="read"):
        addr = BASE+offset*4 if addr is None else addr
        ident = self.ident() if ident is None else ident
        prot = ident % 8
        self.start(2,[addr,length,size,burst,ident,prot,hold],label)
        self.read_events(addr,length,size,burst,ident,prot)
        self.end()

    def desc(self, src, seq, gen, cam, bank, token, raw=1):
        self.start(3,[src,seq,gen,cam,bank,token & 0xffffffff,token >> 32,raw],"external certified RAW producer")
        self.emit("DESC",raw,src,seq,gen,cam,bank,token)
        out = self.model.descriptor(src,seq,gen,cam,bank,token,raw)
        if out is not None:
            self.emit("CMD",src,0x08000000+out*0x200000,seq)
        self.end()

    def done(self):
        self.start(4,[],"controlled successful bridge completion")
        self.emit("RELEASE",*self.model.done())
        self.end()

    def partial_reset(self, kind):
        self.start(7,[kind],f"reset at pending phase {kind}")
        if kind == 0:
            self.emit("W",payload(0xcafebabe,0),0xffff,1)
        elif kind in (1,2,5):
            ident,prot,word = (0x23,2,0x12345678) if kind == 5 else (0x21,6,0xabcdef01)
            self.emit("AW",ident,BASE+0x100,0,4,1,prot,ident & 1)
            self.emit("W",payload(word,0),0xffff,1)
            self.emit("CAW",0x40,prot)
            if kind != 5:
                self.emit("CW",word,15)
            if kind == 1:
                self.emit("CB",0)
        elif kind in (3,4):
            self.emit("AR",0x22,BASE,0,4,1,4,0)
            self.emit("CAR",0,4)
            if kind == 4:
                self.emit("CR",0x434f4f50,0)
        elif kind == 6:
            self.emit("AW",0x24,BASE+0x130,255,4,1,1,0)
            for beat in range(32): self.emit("W",payload(1,beat),0xffff,int(beat==0))
        elif kind == 7:
            self.emit("AW",0x25,BASE+0x100,0,4,1,3,1)
        self.model.reset()
        self.emit("RESET")
        self.end()

    def build(self):
        self.reset()
        # First transactions assert exact identity/counters and route 010xxxx IDs.
        for offset in (0,8,4,0x0c,*range(0x10,0x3c,4),*range(0x50,0x70,4)):
            self.read(offset)
        self.nextid = 0x20
        self.write(0x30,1,order=1,label="CLAIM empty rejected; W precedes AW")
        self.read(0x54); self.read(0x6c)
        self.desc(0x01000000,0x10203040,0x11223344,2,0,0x0123456789abcdef,raw=0)
        self.read(0x58)
        self.desc(0x01000000,0x10203040,0x11223344,2,0,0x0123456789abcdef)
        self.read(4);self.done();self.read(0x0c)
        self.write(0x30,1,order=2,label="wrong bank CLAIM preserves READY bank0")
        self.write(0x30,0,order=1,hold=31,label="real 16-byte all-strobe CLAIM bank0")
        assert self.model.host == 0 and self.model.banks == [3,0]
        for offset in range(0x10,0x3c,4): self.read(offset)
        self.desc(0x01200000,0xa1b2c3d4,0x55667788,5,1,0xfedcba9876543210)
        for offset in range(0x10,0x3c,4): self.read(offset,label="bank0 descriptor while bank1 WRITING")
        self.start(11,[BASE+0x10,0x29,7],"stalled STATUS snapshot across other-bank completion")
        self.read_events(BASE+0x10,0,4,1,0x29,7)
        self.emit("RELEASE",*self.model.done());self.end()
        for offset in range(0x10,0x3c,4): self.read(offset,label="bank0 immutable after bank1 completion")
        self.read(4);self.read(0x0c)
        self.write(0x30,1,label="duplicate host claim rejected")
        # Two precise ACK rejection causes; neither releases either bank.
        for offset,word in ((0x40,1),(0x44,0x10203040),(0x48,0x11223344),(0x4c,1)):
            self.write(offset,word,order=(offset//4)%3)
        self.read(0x50);self.read(4)
        for offset,word in ((0x40,0),(0x48,0x11223343),(0x4c,1)):
            self.write(offset,word)
        self.read(0x50,label="two rejected ACKs exactly");self.read(4)
        assert self.model.counts["ack"] == 2 and self.model.banks == [3,2]
        for offset in range(0x10,0x3c,4): self.read(offset)
        # Rejected full AXI traffic must have zero downstream handshakes/counters.
        for addr in (BASE-16,BASE+0x1000,BASE+4,BASE+0xc4,BASE+0xff8,0xfffffff0):
            self.write(0,1,addr=addr,label="invalid window/alignment/no alias")
            self.read(0,addr=addr)
        for size in (0,1,2,3,5,7):
            self.write(0x4c,1,size=size,order=1);self.read(0x10,size=size)
        for burst in (2,3):
            self.write(0x4c,1,burst=burst);self.read(0x10,burst=burst)
        self.write(0x4c,1,lastmode=1,label="singleton missing LAST cannot ring doorbell")
        for length in (1,2,15,16,255):
            for lastmode in (0,1,2):
                self.write(0x4c,1,length=length,lastmode=lastmode,order=length%3,
                           label=f"drain {length+1} W beats LAST mode {lastmode}")
            self.read(0x10,length=length,hold=1,label=f"exact {length+1} zero error R beats")
        for offset in (0,4,8,0x10,0x34,0x38,0x3c,0x3fc):
            self.write(offset,0xffffffff,label="RO or unimplemented local register")
            self.read(offset)
        self.read(0x50);self.read(0x54)
        self.start(10,[],"invalid max drain with persistent next AW/W")
        self.write_events(BASE+0x130,255,4,1,0x30,1,0xffff,2,4)
        self.write_events(BASE+0x100,0,4,1,0x31,0x13572468,0xffff,0,2)
        self.end();self.read(0x40)
        self.write(0x40,0,label="restore exact bank0 ACK key after pending-next-write check")
        self.read(0,burst=0,label="FIXED singleton read")
        self.start(12,[],"persistent next AR during max 256-beat error response")
        self.read_events(BASE+0xc0,255,4,1,0x32,3)
        self.read_events(BASE,0,4,0,0x33,5);self.end()
        # Low-byte strobes and high-only strobes do not alias adjacent slots.
        self.write(0x48,0xdeadbeef,strb=0xfff0)
        self.read(0x48)
        self.write(0x48,0x11220044,strb=5);self.read(0x48)
        self.write(0x48,0x11223344)
        self.write(0x4c,1,hold=25,label="matching ACK frees only HOST_READING bank0")
        assert self.model.host is None and self.model.banks == [0,2]
        assert self.model.counts["ack"] == 2 and self.model.counts["claim"] == 3
        self.read(4);self.read(0x0c);self.read(0x10)
        self.write(0x30,1,burst=0,label="FIXED singleton CLAIM bank1")
        for offset in range(0x10,0x3c,4): self.read(offset)
        for offset,word in ((0x40,1),(0x44,0xa1b2c3d4),(0x48,0x55667788),(0x4c,1)):
            self.write(offset,word)
        assert self.model.banks == [0,0]
        self.read(4)
        # Persistent next metadata and data while first B remains stalled.
        self.start(6,[BASE+0x100,BASE+0x110,0x87654321,0xabcdef12,0x2a],"back-to-back pending AW/W metadata")
        self.write_events(BASE+0x100,0,4,1,0x2a,0x87654321,0xffff,0,3)
        self.write_events(BASE+0x110,0,4,0,0x2b,0xabcdef12,0xffff,0,5)
        self.end();self.read(0x40);self.read(0x44)
        self.start(8,[BASE+0x120,0x99aabbcc,BASE,0,0x2c,0x2d],"concurrent real controller read/write")
        self.write_events(BASE+0x120,0,4,1,0x2c,0x99aabbcc,0xffff,0,2)
        self.read_events(BASE,0,4,1,0x2d,6);self.end()
        self.start(9,[0x2e,0x99887766,0x2f],"80-cycle real controller B/R hold; no timeout")
        self.write_events(BASE+0x110,0,4,1,0x2e,0x99887766,0xffff,0,7)
        self.read_events(BASE+0x20,0,4,1,0x2f,1);self.end()
        for ident in range(128): self.read(0,ident=ident,hold=2,label="all seven routed ID bits")
        for kind in range(8):
            self.partial_reset(kind)
            for offset in (0,4,0x40,0x44,0x48,0x50,0x54,0x60,0x68): self.read(offset)
        # Same bank/sequence after common reset; stale generation must reject.
        self.desc(0x01000000,0x10203040,0x11223345,2,0,0x1111222233334444)
        self.done();self.write(0x30,0)
        for offset,word in ((0x40,0),(0x44,0x10203040),(0x48,0x11223344),(0x4c,1)):
            self.write(offset,word)
        self.read(0x50);self.read(4);self.read(0x18)
        assert self.model.counts["ack"] == 1 and self.model.host == 0 and self.model.banks == [3,0]
        self.write(0x48,0x11223345);self.write(0x4c,1);self.read(4)
        assert self.model.host is None and self.model.banks == [0,0]
        return self


def main():
    ART.mkdir(exist_ok=True)
    before = sha(CONTROLLER)
    if before != CONTROLLER_SHA256:
        raise AssertionError(f"controller baseline changed: {before}")
    mapping = json.loads((HERE/"register_map.json").read_text())
    assert mapping["base_address"] == "0x40010000"
    assert mapping["window_bytes"] == 4096
    for item in mapping["registers"]:
        assert int(item["physical_address"],16) == BASE+4*int(item["local_offset"],16)
    # Byte-level module collision check includes production RTL, excludes tool artifacts.
    names = {b"fpga_v8_coop_axi128_endpoint": [], b"tb_fpga_v8_coop_axi128_endpoint": []}
    for path in HERE.parent.parent.rglob("*"):
        if path.suffix.lower() in (".v", ".sv", ".vh"):
            for match in re.finditer(rb"\bmodule\s+(\w+)",path.read_bytes()):
                if match[1] in names: names[match[1]].append(str(path))
    assert all(len(hits)==1 for hits in names.values()), names
    suite = Suite().build()
    (ART/"stimulus.txt").write_text("".join(str(code)+" "+" ".join(f"{v:x}" for v in args)+"\n"
                                              for code,args in suite.ops),encoding="ascii")
    (ART/"expected.trace").write_text("".join(f"{op} {channel}"+
        "".join(f" {value:x}" for value in event)+"\n"
        for (op,channel),events in suite.expected.items() for event in events),encoding="ascii")
    sim = Path(os.environ.get("MODELSIM_BIN",r"C:\modeltech64_10.6e\win64"))
    commands = [
        [str(sim/"vlib.exe"),"work"],
        [str(sim/"vlog.exe"),"-work","work",str(CONTROLLER),str(HERE/"fpga_v8_coop_axi128_endpoint.v")],
        [str(sim/"vlog.exe"),"-sv","-work","work",str(HERE/"tb_fpga_v8_coop_axi128_endpoint.sv")],
        [str(sim/"vsim.exe"),"-c","-onfinish","stop","work.tb_fpga_v8_coop_axi128_endpoint",
         "-do","run -all; quit -f"],
    ]
    logs=[]
    for i,command in enumerate(commands):
        completed=subprocess.run(command,cwd=ART,capture_output=True,text=True,timeout=120)
        text=completed.stdout+completed.stderr
        (ART/f"tool_{i}.log").write_text(text,encoding="utf-8")
        logs.append(text)
        if completed.returncode or "** Error" in text or "** Fatal" in text:
            raise RuntimeError(f"tool failed: {command}\n{text}")
    assert "ENDPOINT_TB_PASS" in logs[-1], logs[-1]
    coverage = re.search(r"ops=(\d+) cycles=(\d+) ctrl_AW_first=(\d+) ctrl_W_first=(\d+)", logs[-1])
    assert coverage and int(coverage[3]) and int(coverage[4]), logs[-1]
    actual=defaultdict(list)
    for line in (ART/"actual.trace").read_text().splitlines():
        fields=line.split()
        actual[(int(fields[0]),fields[1])].append(tuple(int(v,16) for v in fields[2:]))
    failures=[]
    for key in sorted(set(actual)|set(suite.expected)):
        if actual[key] != suite.expected[key]:
            failures.append(f"op {key[0]} ({suite.labels[key[0]]}) {key[1]}: "
                            f"expected {suite.expected[key][:6]}, got {actual[key][:6]} "
                            f"counts {len(suite.expected[key])}/{len(actual[key])}")
    (ART/"comparison.txt").write_text("\n".join(failures) if failures else "PASS: all planned public transactions and bank states match.\n")
    assert not failures, "\n".join(failures[:20])
    after=sha(CONTROLLER)
    assert before==after==CONTROLLER_SHA256
    report=dict(status="PASS",scope="isolated endpoint plus unchanged real controller",
                operations=len(suite.ops),events=sum(map(len,actual.values())),
                channel_counts=dict(Counter({ch:sum(len(v) for (op,c),v in actual.items() if c==ch)
                                             for op,ch in actual})),
                controller_sha256_before=before,controller_sha256_after=after,
                endpoint_sha256=sha(HERE/"fpga_v8_coop_axi128_endpoint.v"),
                cycles=int(coverage[2]),ctrl_aw_first=int(coverage[3]),ctrl_w_first=int(coverage[4]),
                tb_sha256=sha(HERE/"tb_fpga_v8_coop_axi128_endpoint.sv"),
                actual_sha256=sha(ART/"actual.trace"),expected_sha256=sha(ART/"expected.trace"),
                commands=commands,module_collision_scan={k.decode():v for k,v in names.items()})
    (ART/"results.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:report[k] for k in ("status","operations","events","channel_counts")},indent=2))


if __name__ == "__main__":
    main()
