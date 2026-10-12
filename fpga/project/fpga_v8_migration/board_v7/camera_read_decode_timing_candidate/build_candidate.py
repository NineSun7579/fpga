"""隔离候选生成：原始 RTL 按 bytes 保留，不触碰 route02。"""
from pathlib import Path
import re, hashlib, json, difflib, base64

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / 'source_diagnostics_route_02/inputs/source/ov5640/ov5640_reg.v'
sha = lambda b: hashlib.sha256(b).hexdigest()
raw = SOURCE.read_bytes()
for d in ['original', 'rtl', 'sim', 'evidence']:
    (ROOT/d).mkdir(exist_ok=True)
(ROOT/'original/ov5640_reg.v').write_bytes(raw)
(ROOT/'sim/ov5640_reg_reference.v').write_bytes(raw.replace(b'module ov5640_reg #(', b'module ov5640_reg_reference #(', 1))
case = re.search(rb'case\(raddr_reg\)(.*?)endcase', raw, re.S)
items = re.findall(rb'^\s*([^\r\n]+?):\s*rdata <= (.*?);', case[1], re.M)
assert len(items) == 23 and items[-1][0].strip() == b'default', items
N = len(items)
decode = ['    // P1: register priority one-hot at the original AR capture edge.',
          f'    reg [{N-1}:0] read_select;',
          '    always @(posedge clk) begin',
          '        if (s_axi_arvalid & s_axi_arready) begin',
          '            case (s_axi_araddr)']
for i, (addr, _) in enumerate(items):
    decode.append(f'                {addr.decode().strip()}: read_select <= {N}\'h{1<<i:06x};')
decode += ['            endcase', '        end', '    end', '',
           '    // Sized wires retain original assignment extension/truncation.',
           '    // Values remain live until the original data_out_valid edge.']
for i, (_, value) in enumerate(items):
    decode.append(f'    wire [AXI_ADDR_WIDTH-1:0] read_value_{i} = {value.decode()};')
decode.append('    wire [AXI_ADDR_WIDTH-1:0] read_mux =')
for i in range(N):
    decode.append(f'        ({{AXI_ADDR_WIDTH{{read_select[{i}]}}}} & read_value_{i})' + (';' if i == N-1 else ' |'))
decode = ('\r\n'.join(decode)+'\r\n').encode('ascii')
capture = re.search(rb'    reg \[AXI_ADDR_WIDTH-1:0\] raddr_reg;.*?\r?\n    end', raw, re.S)
assert capture
candidate = raw[:case.start()] + b'rdata <= read_mux;' + raw[case.end():]
candidate = candidate[:capture.start()] + decode + candidate[capture.end():]
edits = [{'offset': m.start(), 'delete_b64': base64.b64encode(m[0]).decode(), 'insert_b64': base64.b64encode(new).decode()} for m,new in [(capture, decode), (case, b'rdata <= read_mux;')]]
(ROOT/'evidence/byte_patch.json').write_text(json.dumps({'source_sha256': sha(raw), 'candidate_sha256': sha(candidate), 'edits': edits}, indent=2), encoding='ascii')
rebuilt = raw
for edit in reversed(edits):
    offset = edit['offset']
    old = base64.b64decode(edit['delete_b64'])
    assert rebuilt[offset:offset+len(old)] == old
    rebuilt = rebuilt[:offset] + base64.b64decode(edit['insert_b64']) + rebuilt[offset+len(old):]
assert rebuilt == candidate
(ROOT/'rtl/ov5640_reg.v').write_bytes(candidate)
(ROOT/'sim/ov5640_reg_candidate.v').write_bytes(candidate.replace(b'module ov5640_reg #(', b'module ov5640_reg_candidate #(', 1))
diff = ''.join(difflib.unified_diff(raw.decode('gbk', errors='replace').splitlines(True), candidate.decode('gbk', errors='replace').splitlines(True), fromfile='route02/inputs/source/ov5640/ov5640_reg.v', tofile='candidate/rtl/ov5640_reg.v'))
(ROOT/'evidence/candidate.patch').write_text(diff, encoding='utf-8')
manifest = {'source': str(SOURCE), 'source_sha256': sha(raw), 'candidate_sha256': sha(candidate), 'source_bytes': len(raw), 'candidate_bytes': len(candidate), 'encoding': 'raw bytes; legacy GBK/mixed comments preserved', 'read_entries': N-1}
exact = ROOT.parent/'physical_subagent_evidence_01/fixed_06/physical_exact_09/input_hashes.json'
exact_data = json.loads(exact.read_text())
assert exact_data['inputs\\source\\ov5640\\ov5640_reg.v'] == sha(raw)
manifest['exact09_input_manifest'] = {'path': str(exact), 'sha256': sha(exact.read_bytes()), 'camera_matches': True}
for p in (SOURCE.parents[3]).rglob('input_hashes.json'):
    if 'failed_' not in str(p):
        manifest.setdefault('input_hash_manifests', []).append({'path': str(p), 'sha256': sha(p.read_bytes())})
(ROOT/'evidence/input_hashes.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

# Generate shared port wiring only. No behavioral reference model is generated.
header = raw.split(b');', 1)[0]
ports = []
for line in header.splitlines():
    m = re.match(rb'\s*(input|output)\s+(?:reg\s+)?(\[[^\]]+\])?\s*(\w+)\s*[,)]?\s*$', line)
    if m:
        ports.append(tuple(x.decode() if x else '' for x in m.groups()))
assert len(ports) > 60
tb = '''`timescale 1ns/1ps
module camera_pair #(parameter AXI_ADDR_WIDTH=32, parameter BASE_ADDR=32'h20000000, parameter ID=0)(output reg done=0);
reg clk=0; always #5 clk=~clk;
'''
for direction, width, name in ports:
    if name == 'clk': continue
    if direction == 'input': tb += f'reg {width} {name} = 0;\n'
    else:
        tb += f'wire {width} ref_{name}, dut_{name};\n'
for module, prefix in [('ov5640_reg_reference', 'ref'), ('ov5640_reg_candidate', 'dut')]:
    tb += f'{module} #(.AXI_ADDR_WIDTH(AXI_ADDR_WIDTH), .BASE_ADDR(BASE_ADDR), .CAM_ADDR_1_DEF(32\'h12345678), .CAM_ADDR_2_DEF(32\'h87654321), .CAM_EN_DEF(0), .DLY_STEP_DEF(73)) {prefix}_inst (\n'
    tb += ',\n'.join(f'    .{n}({n if d == "input" else prefix+"_"+n})' for d,w,n in ports) + '\n);\n'
outputs = [n for d,w,n in ports if d == 'output']
tb += 'wire mismatch =\n    ' + ' ||\n    '.join(f'(ref_{n} !== dut_{n})' for n in outputs) + ';\n'
tb += 'wire [' + str(sum(1 if not w else (0 if 'AXI_ADDR_WIDTH' in w else int(re.findall(r'\d+', w)[0])+1) for d,w,n in ports if d=='output')) + '+3*AXI_ADDR_WIDTH-1:0] ref_outputs = {' + ','.join('ref_'+n for n in outputs) + '};\n'
tb += 'wire [$bits(ref_outputs)-1:0] dut_outputs = {' + ','.join('dut_'+n for n in outputs) + '};\n'
debug = [n for d,w,n in ports if d=='input' and n.startswith('dbg_')]
tb += '''integer cycles=0, reads=0, writes=0, stalls=0, resets=0, simult=0;
integer i,j,k, seed;
reg [31:0] rnd;
reg [31:0] offsets[0:21];
reg [AXI_ADDR_WIDTH-1:0] hold_data;
reg holding=0;
reg expect_default=0;
reg [31:0] edge_fault;
reg [AXI_ADDR_WIDTH-1:0] before_write;
integer trace;
task tick;
begin
    @(posedge clk); #1;
    cycles=cycles+1;
    if (mismatch) begin
        $display("FAIL id=%0d cycle=%0d ar=%h ref=%h dut=%h",ID,cycles,s_axi_araddr,ref_s_axi_rdata,dut_s_axi_rdata);
        $fatal(1,"cycle comparison");
    end
    $fdisplay(trace,"%0d,%0d,%h,%h,%h,%h,%h,%h,%h,%h,%h", ID,cycles,s_axi_araddr,
        {ref_s_axi_arready,ref_s_axi_rvalid,ref_s_axi_awready,ref_s_axi_wready,ref_s_axi_bvalid},
        {dut_s_axi_arready,dut_s_axi_rvalid,dut_s_axi_awready,dut_s_axi_wready,dut_s_axi_bvalid},
        ref_s_axi_rdata,dut_s_axi_rdata,ref_cam_addr_1,dut_cam_addr_1,ref_outputs,dut_outputs);
    if (holding && !rst && ref_s_axi_rdata !== hold_data) $fatal(1,"R backpressure changed data");
    holding=ref_s_axi_rvalid && !s_axi_rready && !rst;
    hold_data=ref_s_axi_rdata;
    @(negedge clk);
end
endtask
task scramble;
begin
'''
for n in debug: tb += f'    {n}=$random(seed);\n'
tb += '''    pt_rdata=$random(seed); pt_ack=$random(seed);
end
endtask
task read_at(input [AXI_ADDR_WIDTH-1:0] address, input integer stall_n, input integer do_write);
begin
    s_axi_araddr=address; s_axi_arvalid=1; s_axi_rready=0;
    s_axi_awaddr=address; s_axi_awvalid=do_write; s_axi_wvalid=do_write;
    s_axi_wdata=$random(seed); s_axi_wstrb=$random(seed);
    scramble;
    reads=reads+1;
    if(do_write) begin writes=writes+1; simult=simult+1; end
    tick; // AR edge
    s_axi_arvalid=0; s_axi_awvalid=0; s_axi_wvalid=0;
    scramble; // must use this edge's values, not values at AR
    edge_fault=dbg_fault_snapshot;
    pt_done_toggle=~pt_done_toggle;
    tick; // data edge
    if(!ref_s_axi_rvalid) $fatal(1,"missing response on fixed edge");
    if(expect_default && ID!=5 && ref_s_axi_rdata !== {AXI_ADDR_WIDTH{1'b1}}) $fatal(1,"illegal/alias default");
    if((address === BASE_ADDR) && ref_s_axi_rdata !== AXI_ADDR_WIDTH'(edge_fault)) $fatal(1,"data edge or first-case priority");
    for(k=0;k<stall_n;k=k+1) begin
        s_axi_arvalid=1; s_axi_araddr=$random(seed); scramble; stalls=stalls+1; tick;
    end
    s_axi_arvalid=0; s_axi_rready=1; tick;
    s_axi_rready=0; tick;
end
endtask
initial begin
    seed=32'h453123+ID*237;
    trace=$fopen($sformatf("trace_%0d.csv",ID),"w");
    if(!trace) $fatal(1,"trace open");
    $fdisplay(trace,"pair,cycle,araddr,ref_axi,dut_axi,ref_rdata,dut_rdata,ref_cam1,dut_cam1,ref_all_outputs,dut_all_outputs");
    offsets[0]='h00; offsets[1]='h40; offsets[2]='h80; offsets[3]='hc0;
    offsets[4]='h190; offsets[5]='h1a0; offsets[6]='h1b0; offsets[7]='h1c0;
    offsets[8]='h30; offsets[9]='h20; offsets[10]='h50; offsets[11]='h90;
    offsets[12]='ha0; offsets[13]='hf0; offsets[14]='hb0; offsets[15]='he0;
    offsets[16]='h60; offsets[17]='h10; offsets[18]='h70; offsets[19]='hd0;
    offsets[20]='h110; offsets[21]='h120;
    rst=1; resets=resets+1; tick; tick; rst=0;
    // All implemented addresses, simultaneous writes and every low-bit alias.
    for(i=0;i<22;i=i+1) begin
        read_at(BASE_ADDR+offsets[i], 5, 1);
        expect_default=1;
        for(j=1;j<16;j=j+1) read_at(BASE_ADDR+offsets[i]+j, 0, 0);
        read_at((BASE_ADDR+offsets[i]) ^ (64'h1 << (AXI_ADDR_WIDTH-1)), 2, 0);
        expect_default=0;
    end
    expect_default=1;
    read_at(BASE_ADDR+'h100,8,1); // write-only command, invalid read
    read_at(BASE_ADDR+'h180,1,0);
    expect_default=0;
    // Collision parameter: all constant expressions evaluate X. First case wins.
    if(ID==5) begin
        read_at({AXI_ADDR_WIDTH{1'bx}},4,0);
    end
    if(ID!=5) begin
        reads=reads+2; writes=writes+2; simult=simult+1;
        // Write on AR edge: read sees the newly stored value on next edge.
        s_axi_arvalid=1; s_axi_araddr=BASE_ADDR+'h80; s_axi_rready=0;
        s_axi_awvalid=1; s_axi_wvalid=1; s_axi_awaddr=BASE_ADDR+'h80; s_axi_wdata='h13579bdf;
        tick; s_axi_arvalid=0; s_axi_awvalid=0; s_axi_wvalid=0;
        tick;
        if(ref_s_axi_rdata !== AXI_ADDR_WIDTH'('h13579bdf)) $fatal(1,"AR edge write/read");
        s_axi_rready=1; tick; s_axi_rready=0; tick;
        // Write on data edge: read sees pre-NBA register, write commits separately.
        before_write=ref_cam_addr_1;
        s_axi_arvalid=1; s_axi_araddr=BASE_ADDR+'h80; tick; s_axi_arvalid=0;
        s_axi_awvalid=1; s_axi_wvalid=1; s_axi_awaddr=BASE_ADDR+'h80; s_axi_wdata='h2468ace0;
        tick;
        if(ref_s_axi_rdata !== before_write || ref_cam_addr_1 !== AXI_ADDR_WIDTH'('h2468ace0)) $fatal(1,"data edge read/write priority");
        s_axi_awvalid=0; s_axi_wvalid=0; s_axi_rready=1; tick; s_axi_rready=0; tick;
    end
    // Reset on AR edge, data edge and held R response, with writes asserted.
    for(i=0;i<3;i=i+1) begin
        s_axi_arvalid=1; s_axi_araddr=BASE_ADDR+'h80;
        s_axi_awvalid=1; s_axi_wvalid=1; s_axi_awaddr=BASE_ADDR+'h80;
        s_axi_wdata='hdeadbeef; s_axi_rready=0;
        if(i==0) rst=1;
        tick;
        s_axi_arvalid=0;
        if(i==1) rst=1;
        tick;
        rst=1; resets=resets+1; tick;
        if(ref_cam_addr_1 !== AXI_ADDR_WIDTH'(32'h12345678) || ref_s_axi_rvalid || ref_s_axi_bvalid || ref_s_axi_rdata !== 0) $fatal(1,"reset beats read/write");
        s_axi_awvalid=0; s_axi_wvalid=0; rst=0; tick;
    end
    // Independent random streams, including protocol-unfriendly mixed VALID.
    for(i=0;i<20000;i=i+1) begin
        rnd=$random(seed);
        rst=(rnd[9:0]==0); if(rst) resets=resets+1;
        s_axi_arvalid=rnd[0]; s_axi_rready=rnd[1];
        s_axi_awvalid=rnd[2]; s_axi_wvalid=rnd[3]; s_axi_bready=rnd[4];
        s_axi_araddr=BASE_ADDR+offsets[(rnd>>16)%22]+(rnd[5] ? 0 : rnd[15:12]);
        if(rnd[6]) s_axi_araddr=s_axi_araddr ^ (64'h1 << (AXI_ADDR_WIDTH-1));
        s_axi_awaddr=BASE_ADDR+offsets[(rnd>>8)%22];
        s_axi_wdata=$random(seed); s_axi_wstrb=$random(seed);
        scramble;
        if(rnd[7]) pt_done_toggle=~pt_done_toggle;
        if(s_axi_arvalid && ref_s_axi_arready) reads=reads+1;
        if(s_axi_awvalid && s_axi_wvalid) writes=writes+1;
        if(s_axi_arvalid && ref_s_axi_arready && s_axi_awvalid && s_axi_wvalid) simult=simult+1;
        if(ref_s_axi_rvalid && !s_axi_rready) stalls=stalls+1;
        tick;
    end
    rst=1; tick; $fclose(trace);
    $display("PASS pair=%0d width=%0d cycles=%0d reads=%0d writes=%0d stalls=%0d resets=%0d simultaneous=%0d",ID,AXI_ADDR_WIDTH,cycles,reads,writes,stalls,resets,simult);
    done=1;
end
endmodule
module tb_camera_read_decode;
wire [5:0] done;
camera_pair #(.ID(0)) p0(done[0]);
camera_pair #(.ID(1),.BASE_ADDR(32'h20000100)) p1(done[1]);
camera_pair #(.ID(2),.BASE_ADDR(32'hffffff80)) p2(done[2]);
camera_pair #(.ID(3),.AXI_ADDR_WIDTH(64),.BASE_ADDR(64'h120000000)) p3(done[3]);
camera_pair #(.ID(4),.AXI_ADDR_WIDTH(16),.BASE_ADDR(32'h00000000)) p4(done[4]);
camera_pair #(.ID(5),.BASE_ADDR(32'hxxxxxxxx)) p5(done[5]);
initial begin wait(&done); $display("PASS ALL 6 actual-module cycle miters"); $finish; end
initial begin #2000000; $fatal(1,"timeout"); end
endmodule
'''
(ROOT/'sim/tb_camera_read_decode.sv').write_text(tb,encoding='ascii')
print(json.dumps(manifest,ensure_ascii=False,indent=2))
