"""Exact Boolean cone proof from unmodified PDS LUT INITs, across both maps.

Uses the vendor LUT/carry semantics, flattens connected modules, and asks Z3
whether any address/LEN/SIZE/BURST differs from the independent range rule.
This proves decision cones under stated endpoint FSM fixtures, not whole RTL.
"""
import hashlib
import json
from pathlib import Path
import re
import sys

WORK = Path(__file__).resolve().parent
sys.path.insert(0, str(WORK / "solver_packages"))
import z3


def group(data, start):
    depth=0
    for n in range(start,len(data)):
        if data[n]=="(": depth+=1
        elif data[n]==")":
            depth-=1
            if depth==0:return data[start+1:n],n+1
    raise RuntimeError("Unbalanced group")


def normalize(name):
    return name.strip().removeprefix("\\").strip()


def literal(text):
    m=re.fullmatch(r"(?:\d+)?'([bhd])([0-9a-fA-F_]+)",text.strip())
    if m:return int(m[2].replace("_",""),{"b":2,"h":16,"d":10}[m[1]])
    return int(text)


class Circuit:
    def __init__(self,path,top):
        self.path=path; self.parent={};self.drivers={};self.flops={};self.cache={};self.variables={}
        self.module={};self.raw=[];self.instances=[];self.unknown_index=0
        data=path.read_text(encoding="ascii")
        data=re.sub(r"//[^\r\n]*|/\*.*?\*/","",data,flags=re.S)
        for m in re.finditer(r"\bmodule\s+(\w+)(.*?)\bendmodule",data,re.S):
            name=m[1]; body=m[2];header,end=group(body,body.index("("));widths={};ports={}
            for field in header.split(","):
                field=field.strip();p=re.match(r"(input|output)(?:\s+wire)?\s*(?:\[(\d+):(\d+)\])?\s*(.+)$",field)
                assert p,field
                port=normalize(p[4]); hi,lo=(int(p[2]),int(p[3])) if p[2] else (0,0)
                widths[port]=(hi,lo);ports[port]=p[1]
            for d in re.finditer(r"\bwire\s*(?:\[(\d+):(\d+)\])?\s*([^;]+);",body[end:]):
                if "," in d[3]:raise RuntimeError("Unexpected multiwire")
                widths[normalize(d[3])]=(int(d[1]),int(d[2])) if d[1] else (0,0)
            inst=[]
            pattern=r"\b(GTP_\w+|"+"|".join(re.findall(r"\bmodule\s+(\w+)",data))+r")\s*"
            for found in re.finditer(pattern,body[end:]):
                pos=end+found.end();parameters={}
                if body[pos:pos+1]=="#":
                    par,pos=group(body,body.index("(",pos))
                    parameters=self.named(par)
                tail=re.match(r"\s*(\\[^\s]+|\w+)\s*\(",body[pos:])
                if not tail:continue
                connection,_=group(body,pos+tail.end()-1)
                inst.append((found[1],normalize(tail[1]),parameters,self.named(connection)))
            self.module[name]=(widths,ports,inst)
        self.flatten(top,"dut",{})
        for kind,name,params,ports in self.raw:
            outnames=["Q"] if kind.startswith("GTP_DFF") else (["COUT","Z"] if kind=="GTP_LUT6CARRY" else
                ["Z","Z5"] if kind=="GTP_LUT6D" else ["O"] if kind in ["GTP_INBUF","GTP_OUTBUF"] else ["Z"])
            if kind=="GTP_GRS":continue
            ports={p:[self.find(s) for s in sigs] for p,sigs in ports.items()}
            for port in outnames:
                if not ports.get(port):continue
                assert len(ports[port])==1,(kind,port)
                signal=ports[port][0]
                if signal in self.drivers:raise RuntimeError("Multiple drivers "+signal)
                self.drivers[signal]=(kind,name,params,ports,port)
                if port=="Q":self.flops[signal]=(kind,name,params,ports)

    def named(self,text):
        result={}
        for m in re.finditer(r"\.(\\[^\s]+|\w+)\s*\(",text):
            value,_=group(text,m.end()-1);result[normalize(m[1])]=value.strip()
        return result

    def find(self,signal):
        if signal in ["0","1"]:return signal
        self.parent.setdefault(signal,signal)
        if self.parent[signal]!=signal:self.parent[signal]=self.find(self.parent[signal])
        return self.parent[signal]

    def unite(self,a,b):
        a,b=self.find(a),self.find(b)
        if a==b:return
        if a in ["0","1"]:self.parent[b]=a
        else:self.parent[a]=b

    def expand(self,text,prefix,widths):
        text=text.strip()
        if not text:return []
        if text.startswith("{"):
            return [bit for field in reversed(text[1:-1].split(",")) for bit in self.expand(field,prefix,widths)]
        if re.fullmatch(r"\d+'b[xzXZ]+",text):
            self.unknown_index+=1
            return [f"{prefix}/UNKNOWN_{self.unknown_index}_{i}" for i in range(int(text.split("'")[0]))]
        m=re.fullmatch(r"(\d+)'([bhd])([0-9a-fA-F_]+)",text)
        if m:
            val=literal(text);return [str((val>>i)&1) for i in range(int(m[1]))]
        if text.startswith("\\"):
            escaped=re.fullmatch(r"\\([^\s]+)\s*(?:\[(\d+)(?::(\d+))?\])?\s*",text)
            assert escaped,text
            name=escaped[1]
            if escaped[2]:
                hi=int(escaped[2]);lo=int(escaped[3]) if escaped[3] else hi
                return [prefix+"/"+name+f"[{i}]" for i in range(lo,hi+1)]
            hi,lo=widths.get(name,(0,0))
            return [prefix+"/"+name+(f"[{i}]" if hi!=lo else "") for i in range(lo,hi+1)]
        m=re.fullmatch(r"(\w+)\[(\d+)(?::(\d+))?\]",text)
        if m:
            hi=int(m[2]);lo=int(m[3]) if m[3] else hi
            return [prefix+"/"+m[1]+f"[{i}]" for i in range(lo,hi+1)]
        name=normalize(text);hi,lo=widths.get(name,(0,0))
        return [prefix+"/"+name+(f"[{i}]" if hi!=lo else "") for i in range(lo,hi+1)]

    def flatten(self,module,prefix,connections):
        widths,ports,instances=self.module[module]
        for port,signals in connections.items():
            local=self.expand("\\"+port if "/" in port or "[" in port else port,prefix,widths)
            assert len(local)==len(signals),(module,port,len(local),len(signals))
            for a,b in zip(local,signals):self.unite(a,b)
        for kind,name,params,connection in instances:
            expanded={port:self.expand(value,prefix,widths) for port,value in connection.items()}
            if kind in self.module:self.flatten(kind,prefix+"/"+name,expanded)
            else:self.raw.append((kind,prefix+"/"+name,params,expanded))

    def variable(self,signal):
        signal=self.find(signal)
        self.variables.setdefault(signal,z3.Bool(signal))
        return self.variables[signal]

    def bit(self,signal):
        signal=self.find(signal)
        if signal=="0":return z3.BoolVal(False)
        if signal=="1":return z3.BoolVal(True)
        if signal in self.cache:return self.cache[signal]
        if signal not in self.drivers or signal in self.flops:return self.variable(signal)
        kind,name,params,ports,out=self.drivers[signal]
        def pin(port):
            sig=ports.get(port,[])
            return self.bit(sig[0]) if sig else self.variable(name+"/OPEN_"+port)
        def table(value,bits):
            if value==0:return z3.BoolVal(False)
            if value==(1<<(1<<len(bits)))-1:return z3.BoolVal(True)
            if not bits:return z3.BoolVal(bool(value))
            half=1<<(len(bits)-1);mask=(1<<half)-1
            low=value&mask;high=value>>half
            if low==high:return table(low,bits[:-1])
            return z3.If(bits[-1],table(high,bits[:-1]),table(low,bits[:-1]))
        if kind in ["GTP_INBUF","GTP_OUTBUF"]:value=pin("I")
        elif kind=="GTP_INV":value=z3.Not(pin("I"))
        elif kind=="GTP_BUF":value=pin("I")
        elif kind.startswith("GTP_LUT"):
            init=literal(params["INIT"]);bits=[pin(f"I{i}") for i in range(int(kind[7]))]
            if kind=="GTP_LUT6D":value=table(init,bits) if out=="Z" else table(init&0xffffffff,bits[:5])
            elif kind=="GTP_LUT6CARRY":
                low,high=table(init&0xffffffff,bits[:5]),table(init>>32,bits[:5])
                carry=bits[5] if params["I5_TO_CARRY"]=='"TRUE"' else high
                select=bits[5] if params["I5_TO_LUT"]=='"TRUE"' else pin("CIN")
                value=z3.If(low,pin("CIN"),carry) if out=="COUT" else z3.If(select,high,low)
            else:value=table(init,bits)
        else:raise RuntimeError("Unsupported cell "+kind)
        self.cache[signal]=z3.simplify(value)
        return self.cache[signal]

    def next_q(self,signal):
        signal=self.find(signal);kind,name,params,ports=self.flops[signal]
        value=self.bit(ports["D"][0])
        if "CE" in ports:value=z3.If(self.bit(ports["CE"][0]),value,self.variable(signal))
        if "C" in ports:value=z3.If(self.bit(ports["C"][0]),z3.BoolVal(False),value)
        if "P" in ports:value=z3.If(self.bit(ports["P"][0]),z3.BoolVal(True),value)
        return z3.simplify(value)

    def vector(self,prefix,name,width):
        return z3.Concat(*[z3.If(self.bit(prefix+"/"+name+f"[{i}]"),z3.BitVecVal(1,1),z3.BitVecVal(0,1))
            for i in reversed(range(width))])


def prove(path,top,prefix,label):
    circuit=Circuit(path,top)
    answers=[]
    for channel in ["AR","AW"]:
        constraints=[circuit.bit("dut/rst_n")]
        for state,width in [("wr_state_reg",4),("rd_state_reg",5)]:
            for i in range(width):constraints.append(circuit.bit(prefix+"/"+state+f"[{i}]")==z3.BoolVal(i==0))
        if channel=="AR":
            constraints.append(circuit.bit("dut/s_axi_arvalid"))
            addr=circuit.vector("dut","s_axi_araddr",32)
            length=circuit.vector("dut","s_axi_arlen",8)
            size=circuit.vector("dut","s_axi_arsize",3)
            burst=circuit.vector("dut","s_axi_arburst",2)
            actual=circuit.next_q(prefix+"/rd_state_reg[1]")
            terminal_fixture="RC idle, ARVALID=1, rst_n=1; next RS decision"
        else:
            for signal,value in [("aw_held",True),("w_held",True),("w_bad",False),("w_last",True),("ctrl_aw_pending",False)]:
                constraints.append(circuit.bit(prefix+"/"+signal)==value)
            constraints.append(circuit.vector(prefix,"w_remaining",9)==1)
            addr=circuit.vector(prefix,"aw_addr",32)
            length=circuit.vector(prefix,"aw_len",8)
            size=circuit.vector(prefix,"aw_size",3)
            burst=circuit.vector(prefix,"aw_burst",2)
            actual=circuit.next_q(prefix+"/ctrl_aw_pending")
            terminal_fixture="WC idle, AW and W held, final promised W, WLAST=1, w_bad=0, rst_n=1; next local AW pending"
        expected=z3.And(length==0,size==4,z3.ULE(burst,1),(addr&15)==0,
            z3.UGE(addr,0x40010000),z3.ULE(addr,0x40010ff0))
        solver=z3.Solver();solver.set(timeout=60000)
        solver.add(*constraints,actual!=expected)
        smt=WORK / f"cone_{label}_{channel}.smt2";smt.write_text(solver.to_smt2(),encoding="ascii")
        answer=solver.check()
        result={"channel":channel,"fixture":terminal_fixture,"result":str(answer),
            "inputs": "all 32-bit address, 8-bit LEN, 3-bit SIZE, 2-bit BURST values; unmentioned state/input signals unconstrained",
            "independent_expected": "LEN=0, SIZE=4, BURST in {0,1}, aligned16, BASE <= address <= BASE+0xff0",
            "z3_version":z3.get_version_string(),"solver_statistics":str(solver.statistics()),
            "netlist_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"parsed_primitive_cells":len(circuit.raw),
            "smt2":smt.name}
        if answer==z3.sat:
            model=solver.model();result["counterexample"]={"addr":hex(model.eval(addr,model_completion=True).as_long()),
                "len":model.eval(length,model_completion=True).as_long(),"size":model.eval(size,model_completion=True).as_long(),
                "burst":model.eval(burst,model_completion=True).as_long(),"actual":str(model.eval(actual,model_completion=True))}
        answers.append(result)
        print(label,channel,result["result"],result.get("counterexample",""),flush=True)
    return answers


if __name__=="__main__":
    prior=WORK / "cone_proof_results.json"
    if prior.exists() and not (WORK / "cone_proof_initial_parser.json").exists():
        (WORK / "cone_proof_initial_parser.json").write_bytes(prior.read_bytes())
    result={}
    result["standalone"]=prove(WORK / "synthesize/fpga_v8_coop_axi128_endpoint_syn.vm",
        "fpga_v8_coop_axi128_endpoint","dut","leaf")
    result["existing_connected"]=prove(WORK.parent / "endpoint_ctrl_01/synthesize/fpga_v8_endpoint_ctrl_synth_syn.vm",
        "fpga_v8_endpoint_ctrl_synth","dut/endpoint","connected")
    result["all_decisions_equivalent"]=all(r["result"]=="unsat" for checks in result.values() if isinstance(checks,list) for r in checks)
    (WORK / "cone_proof_results.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    if not result["all_decisions_equivalent"]:raise RuntimeError("Counterexample or unknown; inspect saved evidence")
