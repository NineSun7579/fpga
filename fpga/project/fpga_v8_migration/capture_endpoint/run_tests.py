"""Independent planned bus/ownership oracle for the isolated control chain."""
from __future__ import annotations
from collections import defaultdict, Counter
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess

HERE=Path(__file__).resolve().parent
ART=HERE/"artifacts"
ROOT=HERE.parent.parent
BASE=0x40010000
DEPENDENCIES={
    "cooperative_endpoint/fpga_v8_coop_axi128_endpoint.v":"5ea714da5ed63168615f0f9162cb6a773a5ef5780f6fa5a33e2c3fce7cfafc1e",
    "cooperative_control/fpga_v8_coop_control_axil.v":"fec948ff58fbc4fb7f4e70483d8182d052aaa5932c1fd53c0d40930e72a6a2ae",
    "capture_lease/fpga_v8_capture_lease.v":"04e908f9be9aa10ebf4eb19604d747c7dd7d2e48bd8aa52dbe069fc6e246865c",
    "capture_lease/fpga_v8_capture_ov5640_ddr.v":"a69152c43fd67ae074c4801d778e2b0afab82b8af4c6695267a89e60d71b42d8",
}


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def xorshift(x):
    x=(x^(x<<13))&0xffffffff
    x^=x>>17
    return (x^(x<<5))&0xffffffff
def payload(word,beat):
    x=xorshift(0xd193672b^word^((beat*0x9e3779b9)&0xffffffff))
    y=xorshift(x);z=xorshift(y)
    return (x<<96)|(y<<64)|(z<<32)|((word+beat)&0xffffffff)
def merge(old,new,strb):
    mask=sum(0xff<<(8*b) for b in range(4) if strb&(1<<b))
    return (old&~mask)|(new&mask)


@dataclass
class Lease:
    bank:int
    seq:int
    gen:int
    host_claimed:bool=False
    host_done:bool=False
    coop_claimed:bool=False
    coop_done:bool=False
    @property
    def token(self): return (self.gen<<32)|self.seq
    @property
    def addr(self): return 0x01800000+self.bank*0x200000
    def descriptor(self): return (self.bank,self.seq,self.gen,614400,self.addr,4,self.token)
    def release(self): return (4,self.bank,self.seq,self.gen,self.token)


class Model:
    """Immutable identity records with independent consumer obligations/FIFO."""
    def __init__(self,emit):
        self.emit=emit
        self.reset()
    def reset(self):
        self.gen=0;self.seq=1;self.armed=False;self.fault=False;self.engine_idle=True
        self.cap=[0,0];self.records=[None,None];self.writing=None
        self.host_offer=None;self.host_last=0;self.coop_offer=None;self.hp=0;self.cp=0
        self.bound=None;self.coop_enabled=False
        self.staged=0;self.accepted_gen=0;self.ack=[0]*6
        self.rejected_claim=0;self.bad_ack=0;self.rejected_config=0
        self.accepted_config=0;self.accepted_claim=0;self.accepted_release=0
        self.published=0;self.failed=0;self.mreject=0
        self.out=[0,0];self.outrecords=[None,None];self.outfifo=[]
        self.active=None;self.outhost=None;self.outack=[0]*3
        self.outcount=dict(ack=0,claim=0,raw=0,failed=0,done=0,release=0,accepted=0)
        self.outerror=0
    def refresh(self):
        if self.host_offer is None:
            available=[b for b in (self.hp,1-self.hp) if self.cap[b]==2 and not self.records[b].host_claimed]
            if available:
                self.host_offer=available[0];self.host_last=self.host_offer
        if self.coop_offer is None:
            available=[b for b in (self.cp,1-self.cp) if self.cap[b]==2 and not self.records[b].coop_claimed]
            if available:self.coop_offer=available[0]
    def settle(self):
        self.refresh()
        if self.coop_enabled and self.coop_offer is not None and self.active is None and 0 in self.out:
            bank=self.coop_offer;rec=self.records[bank]
            rec.coop_claimed=True;self.coop_offer=None;self.cp=1-bank
            out=self.out.index(0)
            self.active=out;self.out[out]=1;self.outrecords[out]=rec
            self.outcount["accepted"]+=1
            self.emit("COOP_CLAIM",*rec.descriptor())
            self.emit("CMD",rec.addr,0x08000000+out*0x200000,rec.seq)
            self.refresh()
    def free_if_done(self,rec):
        if rec.host_done and rec.coop_done:self.cap[rec.bank]=0
    def config_ready(self): return self.cap==[0,0] and self.engine_idle
    def sof(self,bank,forced_block=False):
        blocked=forced_block or not self.armed or self.fault or self.cap[bank]!=0
        self.emit("SOF",bank,int(not blocked),int(blocked))
        if not blocked:
            self.cap[bank]=1;self.writing=bank;self.records[bank]=None;self.engine_idle=False
    def publish(self,seq):
        self.emit("PUBLISH",seq);self.engine_idle=True
        if self.writing is None or self.cap[self.writing]!=1 or seq!=self.seq or seq==0:
            self.fault=True;self.armed=False;return
        bank=self.writing
        self.cap[bank]=2;self.records[bank]=Lease(bank,seq,self.gen)
        self.seq+=1;self.published+=1
        self.settle()
    def done(self):
        out=self.active;rec=self.outrecords[out]
        self.active=None;self.out[out]=2;self.outfifo.append(out)
        self.outcount["done"]+=1;self.outcount["release"]+=1
        self.emit("COOP_RELEASE",*rec.release());rec.coop_done=True
        self.free_if_done(rec);self.settle()
    def cap_status(self,config_pending=False,release_pending=False):
        return (int(self.armed)|(1<<1)|(int(self.fault)<<2)|((self.bound is not None)<<3)|
                ((self.host_offer is not None)<<4)|(int(config_pending)<<5)|
                (int(release_pending)<<6)|(int(self.config_ready())<<7)|(1<<8)|
                ((self.host_offer==1)<<10))
    def cap_read(self,offset,status_override=None):
        fixed={0x100:0x4341504c,0x104:self.cap_status() if status_override is None else status_override,
               0x108:0x10000,0x10c:self.staged,0x110:0,0x114:self.bound.bank if self.bound else 0xffffffff,
               0x150:0,0x154:self.rejected_claim,0x158:self.bad_ack,0x15c:self.rejected_config,
               0x160:self.published,0x164:self.failed,0x168:self.mreject,
               0x16c:self.cap[0]|(self.cap[1]<<2),0x170:self.accepted_gen,
               0x174:self.accepted_config,0x178:self.accepted_release,0x17c:self.accepted_claim}
        if offset in fixed:return fixed[offset],0
        if offset in range(0x138,0x150,4):return self.ack[(offset-0x138)//4],0
        if offset in range(0x118,0x138,4):
            values=[0xffffffff]+[0]*7
            if self.bound:
                r=self.bound;values=[r.bank,r.seq,r.gen,614400,r.addr,4,r.seq,r.gen]
            return values[(offset-0x118)//4],0
        return 0,2
    def cap_write(self,offset,word,strb,delayed=False,forced_reject=False):
        trigger=bool(strb&word&1)
        if offset==0x10c:self.staged=merge(self.staged,word,strb);return 0
        if offset==0x110:
            if not trigger:return 0
            if self.bound is not None or not self.config_ready():self.rejected_config+=1;return 2
            self.emit("CONFIG",self.staged)
            good=self.staged!=0 and self.staged!=self.gen and not self.fault
            self.emit("CONFIG_ACK",int(good),int(not good))
            self.emit("CONFIG_OBS",int(good),int(not good))
            if not good:self.rejected_config+=1;return 2
            self.gen=self.staged;self.seq=1;self.armed=True;self.hp=0;self.cp=0
            self.accepted_gen=self.staged;self.accepted_config+=1
            return 0
        if offset==0x114:
            if not strb&1:return 0
            if self.bound is not None or self.host_offer is None or word!=self.host_offer:
                self.rejected_claim+=1;return 2
            bank=self.host_offer;self.bound=self.records[bank];self.bound.host_claimed=True
            self.host_offer=None;self.hp=1-bank;self.accepted_claim+=1
            self.emit("HOST_CLAIM",*self.bound.descriptor());self.refresh()
            return 0
        if offset in range(0x138,0x150,4):
            i=(offset-0x138)//4;self.ack[i]=merge(self.ack[i],word,strb);return 0
        if offset==0x150:
            if not trigger:return 0
            r=self.bound
            if r is None or self.ack!=[r.bank,r.seq,r.gen,r.seq,r.gen,4]:self.bad_ack+=1;return 2
            self.emit("HOST_RELEASE",*r.release())
            self.emit("MANAGER_HOST_RELEASE",4,r.bank,r.seq,r.gen,r.token ^ int(forced_reject))
            self.emit("RELEASE_ACK",int(not forced_reject),int(forced_reject))
            self.emit("RELEASE_OBS",int(not forced_reject),int(forced_reject))
            if forced_reject:self.mreject+=1;self.bad_ack+=1;return 2
            r.host_done=True;self.free_if_done(r)
            if not delayed:self.bound=None;self.accepted_release+=1
            return 0
        return 2
    def coop_write(self,offset,word,strb):
        if offset==0x30:
            if not strb&1:return 0
            b=word&1
            if self.outhost is None and self.outfifo and b==self.outfifo[0]:
                self.outfifo.pop(0);self.outhost=b;self.out[b]=3;return 0
            self.outcount["claim"]+=1;self.outerror=3;return 2
        if offset in (0x40,0x44,0x48):
            i=(offset-0x40)//4;self.outack[i]=merge(self.outack[i],word,strb);return 0
        if offset==0x4c:
            if not strb&word&1:return 0
            if self.outhost is not None:
                r=self.outrecords[self.outhost]
                if self.outack==[self.outhost,r.seq,r.gen]:
                    self.out[self.outhost]=0;self.outhost=None;return 0
            self.outcount["ack"]+=1;self.outerror=4;return 2
        return 2
    def coop_read(self,offset):
        fixed={0:0x434f4f50,8:0x10000,0x0c:self.outfifo[0] if self.outfifo else 0xffffffff,
               0x4c:0,0x50:self.outcount["ack"],0x54:self.outcount["claim"],0x58:self.outcount["raw"],
               0x5c:self.outcount["failed"],0x60:self.outcount["done"],0x64:self.outcount["release"],
               0x68:self.outcount["accepted"],0x6c:self.outerror}
        if offset==4:
            return (int(self.active is not None)|(bool(self.outfifo)<<2)|((self.outhost is not None)<<3)|
                    ((self.active is not None)<<5)|(bool(self.outerror)<<6)|(self.out[0]<<10)|(self.out[1]<<12)),0
        if offset in fixed:return fixed[offset],0
        if offset in (0x40,0x44,0x48):return self.outack[(offset-0x40)//4],0
        if offset in range(0x10,0x3c,4):
            values=[0xffffffff]+[0]*7+[0xffffffff,0,0]
            if self.outhost is not None:
                b=self.outhost;r=self.outrecords[b]
                values=[b,r.seq,r.gen,1228800,0x08000000+b*0x200000,4,r.bank,r.addr,b,r.seq,r.gen]
            return values[(offset-0x10)//4],0
        return 0,2
    def state(self):
        return (*self.cap,int(self.armed),int(self.fault),int(self.host_offer is not None),self.host_last,
                *self.out,int(self.active is not None))


class Suite:
    def __init__(self):
        self.ops=[];self.expected=defaultdict(list);self.labels={};self.op=0;self.nextid=0x20
        self.m=Model(self.emit)
    def ident(self):
        v=self.nextid%128;self.nextid+=1;return v
    def emit(self,ch,*values):self.expected[(self.op,ch)].append(tuple(values))
    def start(self,code,args,label):
        self.op+=1;self.ops.append((code,list(args)+[0]*(12-len(args))));self.labels[self.op]=label
    def end(self):self.m.settle();self.emit("STATE",*self.m.state())
    def reset(self):
        self.start(0,[],"coordinated reset");self.m.reset();self.emit("RESET");self.end()
    @staticmethod
    def eligible(addr,length,size,burst):
        return length==0 and size==4 and burst in (0,1) and addr%16==0 and BASE<=addr<=BASE+0xff0
    def write_events(self,addr,length,size,burst,ident,word,strb,prot,lastmode=0,delayed=False,forced_reject=False):
        self.emit("AW",ident,addr,length,size,burst,prot)
        for b in range(length+1):self.emit("W",payload(word,b),strb,int(b==length if lastmode==0 else b==0))
        if self.eligible(addr,length,size,burst):
            offset=(addr-BASE)//4;child=int(offset>=0x100)
            for level in (2,child):
                self.emit(f"L{level}AW",offset,prot);self.emit(f"L{level}W",word,strb&15)
            resp=self.m.cap_write(offset,word,strb&15,delayed,forced_reject) if child else self.m.coop_write(offset,word,strb&15)
            for level in (child,2):self.emit(f"L{level}B",resp)
        else:resp=2
        self.emit("B",ident,resp)
        return resp
    def write(self,offset,word=0,*,strb=0xffff,order=0,hold=17,addr=None,length=0,size=4,burst=1,lastmode=0,label="write"):
        addr=BASE+4*offset if addr is None else addr;ident=self.ident();prot=ident%8
        self.start(1,[addr,length,size,burst,ident,word,strb,order,prot,hold,lastmode],label)
        resp=self.write_events(addr,length,size,burst,ident,word,strb,prot,lastmode);self.end();return resp
    def read_events(self,addr,length,size,burst,ident,prot,status_override=None):
        self.emit("AR",ident,addr,length,size,burst,prot)
        if self.eligible(addr,length,size,burst):
            offset=(addr-BASE)//4;child=int(offset>=0x100)
            data,resp=self.m.cap_read(offset,status_override) if child else self.m.coop_read(offset)
            for level in (2,child):self.emit(f"L{level}AR",offset,prot)
            for level in (child,2):self.emit(f"L{level}R",data,resp)
        else:data,resp=0,2
        for b in range(length+1):self.emit("R",ident,data,resp,int(b==length))
    def read(self,offset,*,hold=13,ident=None,addr=None,length=0,size=4,burst=1,label="read"):
        addr=BASE+offset*4 if addr is None else addr;ident=self.ident() if ident is None else ident;prot=ident%8
        self.start(2,[addr,length,size,burst,ident,prot,hold],label)
        self.read_events(addr,length,size,burst,ident,prot);self.end()
    def arm_race(self):
        ident=self.ident();self.start(3,[ident,1],"ARM dispatch blocks simultaneous attempted SOF")
        self.write_events(BASE+0x440,0,4,1,ident,1,0xffff,3)
        self.m.sof(0,True);self.end()
    def sof(self,bank):
        self.start(4,[bank],"injected actual admitted source SOF contract");self.m.sof(bank);self.end()
    def publish(self,seq):
        self.start(5,[seq],"injected good tag-retirement publish contract");self.m.publish(seq);self.end()
    def enable_coop(self,value):
        self.start(6,[value],"cooperative descriptor consumer gating");self.m.coop_enabled=bool(value);self.end()
    def done(self):
        self.start(7,[],"controlled fully drained bridge completion");self.m.done();self.end()
    def idle(self,value):
        self.start(8,[value],"source engine idle");self.m.engine_idle=bool(value);self.end()
    def stage_ack(self,bank,seq,gen,token_low=None,token_high=None,camera=4):
        values=[bank,seq,gen,seq if token_low is None else token_low,gen if token_high is None else token_high,camera]
        for offset,value in zip(range(0x138,0x150,4),values):self.write(offset,value,order=(offset//4)%3)
    def descriptor(self):
        for offset in range(0x118,0x138,4):self.read(offset)
    def delayed(self,offset):
        ident=self.ident();rid=self.ident()
        self.start(10,[BASE+4*offset,ident,rid],"real manager ACK delivery delayed 80 cycles")
        resp=self.write_events(BASE+4*offset,0,4,1,ident,1,0xffff,6,delayed=offset==0x150)
        assert resp==0
        self.m.refresh()
        status=self.m.cap_status(config_pending=offset==0x110,release_pending=offset==0x150)
        self.read_events(BASE+0x410,0,4,1,rid,4,status)
        if offset==0x150:self.m.bound=None;self.m.accepted_release+=1
        self.end()
    def build(self):
        self.reset()
        for offset in range(0x100,0x180,4):self.read(offset)
        self.read(0);self.read(8)
        self.write(0x114,1,strb=0xfff0,label="high-only CLAIM strobes are a no-op")
        self.read(0x154)
        assert self.write(0x110,1,label="zero generation rejected by actual manager")==2
        self.read(0x15c)
        self.write(0x10c,0x11223344,order=1,label="generation physical 0x40010430")
        self.write(0x10c,0xdeadbeef,strb=0xfff0,label="high-only generation write cannot arm or change epoch")
        self.read(0x10c)
        self.arm_race();self.read(0x170);self.read(0x174);self.read(0x104)
        assert self.write(0x110,1,label="same generation rejected by manager")==2
        self.write(0x10c,0x11223345);self.delayed(0x110)
        self.read(0x174);self.read(0x170)
        self.idle(0)
        assert self.write(0x110,1,label="busy source ARM immediate error without deadlock")==2
        self.idle(1)
        assert self.write(0x114,0,label="claim before offered descriptor rejected")==2
        self.sof(0);self.read(0x16c);self.publish(1);self.read(0x104)
        self.stage_ack(0,1,0x11223345)
        assert self.write(0x150,1,label="offered but unclaimed RAW descriptor cannot release")==2
        self.read(0x158);self.read(0x168);self.read(0x16c)
        assert self.write(0x114,1,label="wrong offered bank claim rejected")==2
        assert self.write(0x114,0x100,label="claim high bank bits cannot truncate")==2
        self.write(0x114,0,order=2,hold=41,label="host RAW bank0 claim AW precedes W")
        self.descriptor()
        self.sof(1)
        # Bound RAW descriptor R held while bank1 publication changes live offers.
        ident=self.ident();self.start(13,[BASE+0x47c,ident,2],"bound seq snapshot across second-bank publication")
        self.read_events(BASE+0x47c,0,4,1,ident,2);self.m.publish(2);self.end()
        self.descriptor();self.read(0x104);self.read(0x160)
        assert self.m.bound.bank==0 and self.m.cap==[2,2]
        assert self.write(0x114,1,label="only one bound host RAW context")==2
        self.write(0x10c,0x22334455)
        assert self.write(0x110,1,label="ARM with host bound is immediate error")==2
        self.stage_ack(0,1,0x11223345)
        ident=self.ident();self.start(15,[ident],"actual manager rejects downstream corrupted release token")
        resp=self.write_events(BASE+0x540,0,4,1,ident,1,0xffff,7,forced_reject=True)
        assert resp==2 and self.m.bound is not None
        self.end();self.read(0x158);self.read(0x168);self.descriptor()
        wrongs=[(0x138,1),(0x138,0x100),(0x13c,2),(0x140,0x11223344),
                (0x144,2),(0x148,0x11223344),(0x14c,5),(0x14c,0x104)]
        correct={0x138:0,0x13c:1,0x140:0x11223345,0x144:1,0x148:0x11223345,0x14c:4}
        for offset,value in wrongs:
            self.write(offset,value)
            assert self.write(0x150,1,label="wrong full RAW ACK key cannot release")==2
            self.read(0x158);self.read(0x16c);self.descriptor()
            self.write(offset,correct[offset])
        assert self.m.bad_ack==10 and self.m.mreject==1 and self.m.cap==[2,2]
        self.write(0x150,1,strb=0xfff0,label="high-only strobes do not ring RAWACK")
        self.write(0x150,0,label="zero doorbell does not release")
        self.write(0x144,0xfeedcafe,strb=0xfff0);self.read(0x144)
        self.write(0x140,0x11220045,strb=5);self.read(0x140)
        self.write(0x140,0x11223345)
        self.write(0x150,1,order=1,label="host-first exact ACK retains bank for cooperative")
        assert self.m.bound is None and self.m.cap==[2,2]
        assert self.write(0x110,1,label="ARM after host release but cooperative obligation retained")==2
        self.write(0x114,1);self.descriptor()
        self.enable_coop(1);self.read(0x16c);self.read(4)
        self.done();self.read(0x16c);self.read(4)
        assert self.m.cap==[0,2] and self.m.active==1
        self.done();self.read(0x16c);self.descriptor()
        assert self.m.cap==[0,2] and self.m.records[1].coop_done
        self.stage_ack(1,2,0x11223345);self.delayed(0x150)
        assert self.m.cap==[0,0] and self.m.bound is None
        self.read(0x16c);self.read(0x178);self.read(0x17c)
        assert self.write(0x150,1,label="duplicate release rejected locally")==2
        # Genuine existing cooperative CLAIM/ACK still works through route0.
        self.read(0x0c);self.write(0x30,0,order=1)
        for offset in range(0x10,0x3c,4):self.read(offset)
        for off,val in ((0x40,0),(0x44,1),(0x48,0x11223345),(0x4c,1)):self.write(off,val)
        self.write(0x30,1)
        for off,val in ((0x40,1),(0x44,2),(0x48,0x11223345),(0x4c,1)):self.write(off,val)
        assert self.m.out==[0,0]
        # Each route owns B and R independently through stalls and input changes.
        for woff,word,roff in ((0x10c,0x22334455,0),(0x40,0x12345678,0x100)):
            wid=self.ident();rid=self.ident()
            self.start(9,[BASE+4*woff,word,BASE+4*roff,0,wid,rid],"concurrent opposite child routes")
            self.write_events(BASE+4*woff,0,4,1,wid,word,0xffff,2)
            self.read_events(BASE+4*roff,0,4,1,rid,5);self.end()
        self.start(11,[BASE+0x430,BASE+0x100,0x33445566,0x89abcdef,0x48],"pending next AW/W changes route after held B")
        self.write_events(BASE+0x430,0,4,1,0x48,0x33445566,0xffff,3)
        self.write_events(BASE+0x100,0,4,0,0x49,0x89abcdef,0xffff,7);self.end()
        self.read(0x10c);self.read(0x40)
        for offset in (0x100,0x104,0x108,0x118,0x154,0x160,0x17c,0x180,0x1fc,0x200,0x3fc):
            assert self.write(offset,0xffffffff,label="RO or unknown child1 write error")==2
            self.read(offset)
        for ident in range(128):self.read(0x100 if ident&1 else 0,ident=ident,hold=5,label="all full routed IDs")
        for addr in (BASE+0x434,BASE-16,BASE+0x1000):
            self.write(0,1,addr=addr);self.read(0,addr=addr)
        self.write(0x150,1,length=255,lastmode=1,label="existing endpoint rejects/drains max burst before router")
        self.read(0x118,length=255,hold=1)
        self.write(0x110,1,size=2);self.read(0x100,size=2)
        # Fresh arm after both consumer obligations completed.
        self.write(0x110,1);self.read(0x170);self.sof(0)
        self.start(12,[],"retired source error counter");self.emit("RETIRED_ERROR")
        self.m.cap[self.m.writing]=0;self.m.engine_idle=True;self.m.failed+=1;self.end();self.read(0x164)
        # Common reset discards held full B and all source/output contexts.
        self.start(14,[],"reset with full downstream ARM B held")
        # Current generation is staged, so actual manager rejects; B is held
        # at the child gate before resetting every participant.
        self.emit("AW",0x70,BASE+0x440,0,4,1,1);self.emit("W",payload(1,0),0xffff,1)
        for lev in (2,1):self.emit(f"L{lev}AW",0x110,1);self.emit(f"L{lev}W",1,15)
        self.m.cap_write(0x110,1,15)
        # Dedicated child response gating keeps this actual B unconsumed.
        self.m.reset();self.emit("RESET");self.end()
        for off in (0x104,0x170,0x174,0x178,0x17c,0x160,0x164,0x154,0x158):self.read(off)
        self.write(0x10c,0x44556677);self.write(0x110,1);self.sof(0);self.publish(1)
        self.write(0x114,0);self.descriptor()
        self.stage_ack(0,1,0x11223345)
        assert self.write(0x150,1,label="old generation key after reset fails")==2
        self.stage_ack(0,1,0x44556677);self.write(0x150,1)
        self.enable_coop(1);self.done();self.read(0x16c)
        assert self.m.cap==[0,0] and self.m.bad_ack==1
        # Bad publish identity exposes manager protocol fault and disarms.
        self.sof(1);self.publish(99);self.read(0x104);self.read(0x16c)
        assert self.m.fault and not self.m.armed
        self.reset();self.read(0x104)
        return self


def manifest():
    files=list((HERE.parent/"cooperative_endpoint").rglob("*"))
    files.extend(HERE.parent/name for name in DEPENDENCIES)
    return {str(p.relative_to(HERE.parent)).replace("\\","/"):sha(p) for p in files if p.is_file()}


def main():
    ART.mkdir(exist_ok=True)
    mapping=json.loads((HERE/"register_map.json").read_text())
    assert mapping["shared_axi128_base"]=="0x40010000" and mapping["shared_window_bytes"]==4096
    assert len(mapping["registers"])==32
    for i,item in enumerate(mapping["registers"]):
        assert int(item["local_offset"],16)==0x100+i*4
        assert int(item["physical_address"],16)==BASE+4*(0x100+i*4)
    api=json.loads((HERE/"port_api.json").read_text())
    manager_bytes=(HERE.parent/"capture_lease/fpga_v8_capture_lease.v").read_bytes()
    control_bytes=(HERE/"fpga_v8_capture_control_axil.v").read_bytes()
    def check_port(data,name,width,direction):
        declaration=re.search(rb"\b(input|output)\s+(?:(?:wire|reg)\s+)?(?:\[(\d+):(\d+)\]\s+)?"+name.encode()+rb"\b",data)
        assert declaration and declaration[1].decode()==direction,(name,direction)
        actual_width=abs(int(declaration[2])-int(declaration[3]))+1 if declaration[2] else 1
        assert actual_width==width,(name,width,actual_width)
    for group in ("capture_control_to_manager","manager_to_capture_control"):
        for name,width in api[group].items():
            check_port(control_bytes,name,width,"output" if group=="capture_control_to_manager" else "input")
            check_port(manager_bytes,name,width,"input" if group=="capture_control_to_manager" else "output")
    router_bytes=(HERE/"fpga_v8_coop_axil_router.v").read_bytes()
    upstream_inputs={"awaddr","awprot","awvalid","wdata","wstrb","wvalid","bready","araddr","arprot","arvalid","rready"}
    for signal,width in api["axil_signal_widths"].items():
        direction="input" if signal in upstream_inputs else "output"
        check_port(control_bytes,"s_axil_"+signal,width,direction)
        check_port(router_bytes,"s_axil_"+signal,width,direction)
        for child in (0,1):check_port(router_bytes,f"m{child}_axil_"+signal,width,"output" if direction=="input" else "input")
    before=manifest()
    for name,value in DEPENDENCIES.items():assert before[name]==value,(name,before[name])
    baseline=ART/"source_hashes_initial.json"
    if baseline.exists():assert json.loads(baseline.read_text())==before,"parent dependencies changed since first run"
    else:baseline.write_text(json.dumps(before,indent=2)+"\n")
    (ART/"source_hashes_before.json").write_text(json.dumps(before,indent=2)+"\n")
    names={b"fpga_v8_capture_control_axil":[],b"fpga_v8_coop_axil_router":[],b"tb_fpga_v8_capture_endpoint":[]}
    for p in ROOT.rglob("*"):
        if p.suffix.lower() in (".v",".sv",".vh"):
            for m in re.finditer(rb"\bmodule\s+(\w+)",p.read_bytes()):
                if m[1] in names:names[m[1]].append(str(p))
    assert all(len(hits)==1 for hits in names.values()),names
    suite=Suite().build()
    (ART/"stimulus.txt").write_text("".join(str(code)+" "+" ".join(f"{v:x}" for v in args)+"\n" for code,args in suite.ops),encoding="ascii")
    (ART/"expected.trace").write_text("".join(f"{op} {ch}"+"".join(f" {v:x}" for v in event)+"\n"
        for (op,ch),events in suite.expected.items() for event in events),encoding="ascii")
    sim=Path(os.environ.get("MODELSIM_BIN",r"C:\modeltech64_10.6e\win64"))
    rtl=[HERE.parent/name for name in list(DEPENDENCIES)[:3]]
    rtl.extend([HERE/"fpga_v8_capture_control_axil.v",HERE/"fpga_v8_coop_axil_router.v"])
    commands=[[str(sim/"vlib.exe"),"work_capture_control"],
              [str(sim/"vlog.exe"),"-work","work_capture_control",*map(str,rtl)],
              [str(sim/"vlog.exe"),"-sv","-work","work_capture_control",str(HERE/"tb_fpga_v8_capture_endpoint.sv")],
              [str(sim/"vsim.exe"),"-c","-onfinish","stop","work_capture_control.tb_fpga_v8_capture_endpoint",
               "-do","run -all; quit -f"]]
    logs=[]
    for i,command in enumerate(commands):
        p=subprocess.run(command,cwd=ART,capture_output=True,text=True,timeout=120)
        text=p.stdout+p.stderr;logs.append(text);(ART/f"tool_{i}.log").write_text(text,encoding="utf-8")
        if p.returncode or "** Error" in text or "** Fatal" in text:raise RuntimeError(text)
    assert "CAPTURE_ENDPOINT_PASS" in logs[-1],logs[-1]
    actual=defaultdict(list)
    for line in (ART/"actual.trace").read_text().splitlines():
        fields=line.split();actual[(int(fields[0]),fields[1])].append(tuple(int(v,16) for v in fields[2:]))
    failures=[]
    for key in sorted(set(actual)|set(suite.expected)):
        if actual[key]!=suite.expected[key]:failures.append(f"op {key[0]} ({suite.labels[key[0]]}) {key[1]} expected {suite.expected[key][:5]} got {actual[key][:5]} counts {len(suite.expected[key])}/{len(actual[key])}")
    (ART/"comparison.txt").write_text("\n".join(failures) if failures else "PASS: every planned public transaction and ownership state matched.\n")
    assert not failures,"\n".join(failures[:30])
    after=manifest();(ART/"source_hashes_after.json").write_text(json.dumps(after,indent=2)+"\n")
    assert before==after,"modified dependency or finalized cooperative endpoint files"
    coverage=re.search(r"ops=(\d+) cycles=(\d+) child_AW_first=(\d+) child_W_first=(\d+) router_AW_first=(\d+) router_W_first=(\d+)",logs[-1])
    assert coverage and all(int(coverage[i])>0 for i in range(3,7))
    report=dict(status="PASS",scope="isolated injected source-event control chain; no physical source validation",
                operations=len(suite.ops),events=sum(map(len,actual.values())),cycles=int(coverage[2]),
                coverage=dict(zip(["child_aw_first","child_w_first","router_aw_first","router_w_first"],map(int,coverage.groups()[2:]))),
                channel_counts=dict(Counter({ch:sum(len(v) for (op,c),v in actual.items() if c==ch) for op,ch in actual})),
                preserved_files=len(before),source_hashes_unchanged=True,commands=commands,
                candidate_hashes={p.name:sha(p) for p in HERE.iterdir() if p.is_file()},
                actual_sha256=sha(ART/"actual.trace"),expected_sha256=sha(ART/"expected.trace"),
                module_scan={k.decode():v for k,v in names.items()})
    (ART/"results.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:report[k] for k in ("status","operations","events","cycles","coverage","channel_counts","preserved_files")},indent=2))


if __name__=="__main__":main()
