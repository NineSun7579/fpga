"""Isolated byte-preserving decode candidate and real RTL cycle miter."""
from pathlib import Path
import re, json, hashlib, difflib, subprocess, importlib.util

HERE = Path(__file__).resolve().parent
MIG = HERE.parent.parent
SOURCE = HERE.parent / 'source_diagnostics_route_02/rtl'
EXACT = HERE.parent / 'physical_subagent_evidence_01/fixed_06/physical_exact_09/input_hashes.json'
NAME = 'fpga_v8_capture_control_axil_arm_v2'
SIM = Path(r'C:\modeltech64_10.6e\win64')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p, text): p.write_text(text, encoding='utf-8')

def prepare():
    for d in ('original','candidate','sim','artifacts','integration_inputs'): (HERE/d).mkdir(exist_ok=True)
    inputs=[SOURCE/(NAME+'.v'),EXACT]
    inputs.extend(SOURCE/n for n in ('fpga_v8_coop_axi128_endpoint.v','fpga_v8_coop_control_axil_rfg01.v','fpga_v8_capture_lease_tc04.v','fpga_v8_coop_axil_router.v'))
    inputs.extend(MIG/'capture_arm_contract/endpoint'/n for n in ('run_tests.py','tb_fpga_v8_capture_endpoint.sv'))
    before={str(p):sha(p) for p in inputs}
    save(HERE/'input_hashes.json',json.dumps(before,indent=2)+'\n')
    for p in inputs[2:]: (HERE/'integration_inputs'/p.name).write_bytes(p.read_bytes())
    original = (SOURCE/(NAME+'.v')).read_bytes()
    expected = json.loads(EXACT.read_text())['rtl\\'+NAME+'.v']
    assert hashlib.sha256(original).hexdigest() == expected
    (HERE/'original'/(NAME+'.v')).write_bytes(original)
    candidate = original.replace(b'    wire [31:0] wr_offset=aw_addr-LOCAL_BASE;\n', b'')
    candidate = re.sub(rb'wr_offset==32\'h([0-9a-f]+)', rb"aw_addr==(LOCAL_BASE+32'h\1)", candidate)
    candidate = candidate.replace(b'case(addr-LOCAL_BASE)', b'case(addr)').replace(b'case(wr_offset)', b'case(aw_addr)')
    candidate = re.sub(rb"32'h([0-9a-f]+)(?=[:,])", rb"(LOCAL_BASE+32'h\1)", candidate)
    assert b'wr_offset' not in candidate and b'addr-LOCAL_BASE' not in candidate
    (HERE/'candidate'/(NAME+'.v')).write_bytes(candidate)
    (HERE/'sim/golden.v').write_bytes(original.replace(('module '+NAME).encode(), ('module '+NAME+'_golden').encode(),1))
    save(HERE/'decode.diff', ''.join(difflib.unified_diff(original.decode('gbk').splitlines(True),candidate.decode('gbk').splitlines(True),fromfile='original/'+NAME+'.v',tofile='candidate/'+NAME+'.v')))
    ports=[]
    for m in re.finditer(rb'\b(input|output)\s+(?:wire|reg)\s*(\[[^\]]+\])?\s*(\w+)',original.split(b');',1)[0]):
        ports.append((m[1].decode(),(m[2] or b'').decode(),m[3].decode()))
    regs=[]
    for m in re.finditer(rb'\breg\s*(?:\[[^\]]+\])?\s*([^;]+);', original[original.index(b'localparam'):original.index(b'    function')]):
        regs.extend(x.strip().decode() for x in m[1].split(b','))
    checks=list(dict.fromkeys([n for d,w,n in ports if d=='output']+regs+['commit','wr_in_range','doorbell','key_match']))
    save(HERE/'sim/compared_signals.json',json.dumps(checks,indent=2))
    return ports,checks

def monitor(checks,a,b):
    return '\n'.join(f'if({a}.{n} !== {b}.{n}) $fatal(1,"mismatch {n} t=%0t",$time);' for n in checks)

def make_miter(ports,checks):
    decl='\n'.join(f'reg {w} {n}=0;' for d,w,n in ports if d=='input' and n!='clk')
    conn=','.join(f'.{n}({n})' for d,w,n in ports if d=='input')
    text='''`timescale 1ns/1ps
module tb_decode;
parameter [31:0] BASE=32'h100;
reg clk=0; always #5 clk=~clk;
DECL
fpga_v8_capture_control_axil_arm_v2_golden #(.LOCAL_BASE(BASE)) gold(CONN);
fpga_v8_capture_control_axil_arm_v2 #(.LOCAL_BASE(BASE)) cand(CONN);
integer cycles=0,arms=0,rels=0,claims=0,armwait=0,relwait=0,bothcfg=0,bothrel=0;
integer seed=1,i,j,order,strb,offset;
reg [31:0] value, address;
task check; begin CHECK end endtask
always @(posedge clk) begin
 check(); cycles=cycles+1;
 if(gold.config_valid) arms=arms+1;
 if(gold.host_ready) claims=claims+1;
 if(gold.host_release_valid) rels=rels+1;
 if(gold.pending==1) armwait=armwait+1;
 if(gold.pending==2) relwait=relwait+1;
 if(gold.pending==1 && config_accept && config_reject) bothcfg=bothcfg+1;
 if(gold.pending==2 && host_release_accept && host_release_reject) bothrel=bothrel+1;
 #1;check();
end
always @(negedge clk) begin #1;check(); end
task tick; input integer n; integer t; begin for(t=0;t<n;t=t+1) @(negedge clk); end endtask
task reset; begin rst_n=0; tick(2);rst_n=1;tick(2); end endtask
task write; input [31:0] addr,data; input [3:0] mask; input integer ord; begin
 s_axil_awaddr=addr;s_axil_wdata=data;s_axil_wstrb=mask;
 if(ord==0) begin s_axil_awvalid=1;s_axil_wvalid=1;tick(1);s_axil_awvalid=0;s_axil_wvalid=0;end
 if(ord==1) begin s_axil_awvalid=1;tick(1);s_axil_awvalid=0;tick(3);s_axil_wvalid=1;tick(1);s_axil_wvalid=0;end
 if(ord==2) begin s_axil_wvalid=1;tick(1);s_axil_wvalid=0;tick(3);s_axil_awvalid=1;tick(1);s_axil_awvalid=0;end
 tick(2);
end endtask
task drain; begin
 if(gold.pending==1) begin tick(4);config_accept=1;tick(1);config_accept=0;end
 if(gold.pending==2) begin tick(4);host_release_accept=1;tick(1);host_release_accept=0;end
 tick(2);
end endtask
task bind_ack; begin
 write(BASE+32'h14,{31'd0,host_bank},15,1);
 write(BASE+32'h38,{31'd0,host_bank},15,2);
 write(BASE+32'h3c,host_seq,15,0);
 write(BASE+32'h40,host_generation,15,1);
 write(BASE+32'h44,host_token[31:0],15,2);
 write(BASE+32'h48,host_token[63:32],15,0);
 write(BASE+32'h4c,{29'd0,host_camera},15,1);
end endtask
initial begin
 if(!$value$plusargs("SEED=%d",seed)) seed=1;
 tick(1);reset();s_axil_bready=1;s_axil_rready=1;
 config_ready=1;host_valid=1;host_release_ready=1;host_bank=1;host_seq=32'h87654321;
 host_generation=32'hffffffff;host_camera=7;host_token=64'hfedcba9876543210;
 host_length=32'hfffffff0;host_src_addr=32'hfffffff0;
 // All 16 byte masks, both AW/W orderings, every aligned register and illegal boundary byte.
 for(i=0;i<16;i=i+1) begin
  for(j=-4;j<132;j=j+1) begin
   s_axil_araddr=BASE+j;s_axil_arvalid=1;
   write(BASE+j,32'h12345679,i,i%3);drain();
  end
 end
 s_axil_arvalid=0;reset();
 // ARM dispatch with SOF/status and response on the same edge, then delayed contradictory ack.
 config_accept=1;config_reject=1;epoch_start=1;
 write(BASE+32'h10,1,1,0);
 config_accept=0;config_reject=0;tick(5);
 config_accept=1;config_reject=1;tick(1);config_accept=0;config_reject=0;tick(3);
 bind_ack();
 // Release dispatch concurrent with SOF/config response; registered reject wins over accept.
 host_release_accept=1;host_release_reject=1;config_accept=1;epoch_start=1;
 write(BASE+32'h50,1,1,2);
 host_release_accept=0;host_release_reject=0;config_accept=0;tick(5);
 host_release_accept=1;host_release_reject=1;tick(1);host_release_accept=0;host_release_reject=0;tick(3);
 write(BASE+32'h50,1,1,1);drain();
 // Reset aborts ARM_WAIT, RELEASE_WAIT and independently held AW/W and blocked B/R.
 write(BASE+32'h10,1,1,0);reset();
 bind_ack();write(BASE+32'h50,1,1,0);reset();
 s_axil_awvalid=1;tick(1);s_axil_awvalid=0;reset();
 s_axil_wvalid=1;tick(1);s_axil_wvalid=0;reset();
 s_axil_bready=0;s_axil_rready=0;s_axil_arvalid=1;s_axil_araddr=BASE;
 write(BASE+32'h0c,32'hdeadbeef,15,0);reset();
 s_axil_bready=1;s_axil_rready=1;s_axil_arvalid=0;
 // Reproducible directed random traffic: full-address aliases, backpressure and asynchronous reset.
 for(i=0;i<4000;i=i+1) begin
  value=$random(seed);offset=($random(seed)&255)-64;
  case(i%7)
   0: address=BASE+offset;
   1: address=$random(seed);
   2: address=32'hffffffff;
   3: address=0;
   default: address=BASE+((value&31)*4);
  endcase
  config_ready=value[0];host_release_ready=value[1];host_valid=value[2];
  epoch_start=value[3];armed=value[4];config_ok=value[5];protocol_fault=value[6];
  bank0_state=value[8:7];bank1_state=value[10:9];published_count=value;failed_count=~value;
  rejected_release_count=$random(seed);s_axil_awprot=value[13:11];s_axil_arprot=value[16:14];
  s_axil_araddr=address;s_axil_arvalid=1;s_axil_rready=value[17];
  write(address,value,value[21:18],i%3);s_axil_rready=1;drain();
  if(i%17==0) begin #2;rst_n=0;#1;check();tick(1);rst_n=1;tick(2);end
 end
 if(BASE[1:0]==0 && BASE<=32'hffffff80 && (!arms || !rels || !claims || !armwait || !relwait || !bothcfg || !bothrel))
  $fatal(1,"missing directed coverage arms=%d rels=%d claims=%d both=%d/%d",arms,rels,claims,bothcfg,bothrel);
 $display("DECODE_MITER_PASS base=%h cycles=%0d arms=%0d releases=%0d claims=%0d ARM_WAIT=%0d RELEASE_WAIT=%0d bothcfg=%0d bothrel=%0d",BASE,cycles,arms,rels,claims,armwait,relwait,bothcfg,bothrel);$finish;
end
initial begin #20000000;$fatal(1,"watchdog");end
endmodule
'''
    text=text.replace('DECL',decl).replace('CONN',conn).replace('CHECK',monitor(checks,'gold','cand'))
    save(HERE/'sim/tb_decode.sv',text)

def tool(args,log,cwd):
    command=[str(SIM/args[0])]+([] if args[0]=='vlib.exe' else ['-modelsimini',(HERE/'artifacts/modelsim.ini').as_posix()])+[x.replace('\\','/') for x in args[1:]]
    p=subprocess.run(command,cwd=cwd,capture_output=True,text=True,timeout=120)
    out=p.stdout+p.stderr;save(log,out)
    if p.returncode or '** Error' in out or '** Fatal' in out: raise RuntimeError(out[-6000:])
    return out

def integration(ports,checks):
    endpoint=HERE/'integration_inputs'
    spec=importlib.util.spec_from_file_location('existing_suite',endpoint/'run_tests.py')
    module=importlib.util.module_from_spec(spec)
    import sys
    sys.dont_write_bytecode=True
    sys.modules[spec.name]=module;spec.loader.exec_module(module)
    suite=module.Suite().build()
    art=HERE/'artifacts/integration';art.mkdir(exist_ok=True)
    save(art/'stimulus.txt',''.join(str(code)+' '+' '.join(f'{v:x}' for v in args)+'\n' for code,args in suite.ops))
    tb=(endpoint/'tb_fpga_v8_capture_endpoint.sv').read_text()
    match=re.search(r'    '+NAME+r' capture_control \((.*?)\n    \);',tb,re.S)
    body=match[1]
    outputs={n for d,w,n in ports if d=='output'}
    # Leave golden outputs unconnected; real original sequential RTL consumes identical inputs.
    pairs=re.findall(r'\.(\w+)\(([^\n]*?)\)(?=,|\s*$)',body,re.M)
    assert len(pairs)==len(ports),(len(pairs),len(ports))
    shadow=NAME+'_golden capture_golden (\n'+',\n'.join('.'+n+'('+('' if n in outputs else expr)+')' for n,expr in pairs)+'\n);\n'
    tb=tb.replace('endmodule',shadow+'\ntask miter_check; begin\n'+monitor(checks,'capture_control','capture_golden')+'\nend endtask\nalways @(posedge clk) begin miter_check();#1;miter_check();end\nalways @(negedge clk) begin #1;miter_check();end\nendmodule')
    tb=tb.replace('fpga_v8_capture_lease manager', 'fpga_v8_capture_lease_tc04 manager')
    tb=tb.replace('fpga_v8_coop_control_axil cooperative_control (', "fpga_v8_coop_control_axil_rfg01 cooperative_control ( .session_fault(1'b0),")
    save(HERE/'sim/tb_integration.sv',tb)
    deps=[endpoint/n for n in ('fpga_v8_coop_axi128_endpoint.v','fpga_v8_coop_control_axil_rfg01.v','fpga_v8_capture_lease_tc04.v','fpga_v8_coop_axil_router.v')]
    for p in deps: assert p.exists(),p
    tool(['vlog.exe','-work','work',*map(str,deps),str(HERE/'sim/tb_integration.sv')],art/'compile.log',HERE/'artifacts')
    out=tool(['vsim.exe','-c','-onfinish','stop','-lib',str(HERE/'artifacts/work'),'tb_fpga_v8_capture_endpoint','-do','onerror {quit -code 1}; run -all; quit -f'],art/'modelsim.log',art)
    assert 'CAPTURE_ENDPOINT_PASS' in out
    # Existing oracle is supplementary; equivalence gold is solely original RTL.
    from collections import defaultdict
    actual=defaultdict(list)
    for line in (art/'actual.trace').read_text().splitlines():
        f=line.split();actual[(int(f[0]),f[1])].append(tuple(int(v,16) for v in f[2:]))
    failures=[str(k) for k in set(actual)|set(suite.expected) if actual[k]!=suite.expected[k]]
    save(art/'comparison.txt','PASS: existing integration planned transactions and state matched.\n' if not failures else '\n'.join(failures))
    assert not failures,failures[:20]
    return {'operations':len(suite.ops),'events':sum(map(len,actual.values())),'pass_line':[s for s in out.splitlines() if 'CAPTURE_ENDPOINT_PASS' in s]}

def main():
    import sys
    integration_only='--integration-only' in sys.argv
    ports,checks=prepare();make_miter(ports,checks)
    art=HERE/'artifacts'
    save(art/'modelsim.ini', '[Library]\nwork = '+str(art/'work').replace('\\','/')+'\nothers = C:/modeltech64_10.6e/modelsim.ini\n')
    tool(['vlib.exe','work'],art/'vlib.log',art)
    tool(['vlog.exe','-sv','-work','work',str(HERE/'sim/golden.v'),str(HERE/'candidate'/(NAME+'.v')),str(HERE/'sim/tb_decode.sv')],art/'compile.log',art)
    runs=[]
    for base in (0x100,0,4,0x7fffffc0,0xffffff7c,0xffffff80,0xffffff84,0xfffffffc,0x101):
        for seed in (1,202603):
            label=f'{base:08x}_{seed}'
            out=(art/(label+'.log')).read_text() if integration_only else tool(['vsim.exe','-c','-onfinish','stop','work.tb_decode',f'-gBASE=32\'h{base:08x}',f'+SEED={seed}','-do','onerror {quit -code 1}; run -all; quit -f'],art/(label+'.log'),art)
            assert 'DECODE_MITER_PASS' in out
            runs.append({'base':f'{base:08x}','seed':seed,'pass_line':[s for s in out.splitlines() if 'DECODE_MITER_PASS' in s]})
            print(runs[-1]['pass_line'][0],flush=True)
    result={'status':'PASS','golden':'original actual route02 RTL; no behavioral mirror','signals_compared':checks,'runs':runs,'integration':integration(ports,checks)}
    assert sha(SOURCE/(NAME+'.v'))==sha(HERE/'original'/(NAME+'.v'))
    before=json.loads((HERE/'input_hashes.json').read_text())
    after={p:sha(Path(p)) for p in before}
    assert before==after
    save(HERE/'input_hashes_after.json',json.dumps(after,indent=2)+'\n')
    result['input_hashes_unchanged']=True
    result['hashes']={str(p.relative_to(HERE)):sha(p) for p in HERE.rglob('*') if p.is_file() and not any(x.startswith('work') or x=='__pycache__' for x in p.relative_to(HERE).parts) and p.name!='results.json'}
    result['source_sha256']=sha(SOURCE/(NAME+'.v'))
    save(art/'results.json',json.dumps(result,indent=2)+'\n')
    print('ALL_REGRESSIONS_PASS',flush=True)

if __name__=='__main__': main()
