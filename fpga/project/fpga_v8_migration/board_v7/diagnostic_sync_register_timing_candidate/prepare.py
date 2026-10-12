"""Byte-preserving isolated preparation. Does not invoke PDS or alter inputs."""
from pathlib import Path
import hashlib, json, re, difflib
import pymupdf

P = Path(__file__).resolve().parent
B = P.parent / 'source_diagnostics_timing_build_01'
F = P.parents[1] / 'whole_candidate_v7_route_01'
S = P.parent / 'source_frame_diagnostics_candidate'
T = P.parent / 'source_diagnostics_bus_candidate'
V = Path('C:/pango/PDS_2022.2-SP6.4')
for d in ['baseline', 'rtl', 'sim', 'evidence', 'docs']:
    (P/d).mkdir(exist_ok=True)
protected = [B/'rtl/v7_sfd_candidate.v', B/'rtl/v7_sdt_bus.v', B/'project.pds',
             S/'tb_v7_sfd_candidate.sv', T/'tb.sv', T/'fixture.vh',
             F/'inputs/source/ov5640/ov5640/cmos_capture.v',
             F/'inputs/source/ov5640/axi_to_axi_lite.v', F/'rtl/ovreg_axil_decode_tc01.v']
docs = {'doc/ADS_Synthesis_User_Guide.pdf':[53,54,84,85,92,93,94,104,105],
        'syn/doc/fpga_attribute_reference.pdf':[90,91,92,127,130,161,162,163]}
for name,pages in docs.items():
    path=V/name
    protected.append(path)
    doc=pymupdf.open(path)
    (P/'docs'/ (path.stem+'.txt')).write_text('\n'.join(
        f'FILE: {path}\nPDF PAGE: {n}\n'+doc[n-1].get_text() for n in pages),encoding='utf8')
for name in ['GTP_DFF_CE.v','GTP_DFF_PE.v','GTP_GRS.v']:
    path=V/'arch/vendor/pango/verilog/simulation'/name
    if path.exists(): protected.append(path)
help_root=P.parent/'physical_subagent_evidence_01'
helps=[help_root/'verified_command_manual.txt',help_root/'fixed_06/mapped_help16/shell.txt',
       help_root/'fixed_06/stage_help11/shell.log']
for h in helps:
    if h.exists():
        protected.append(h)
        (P/'docs'/('stored_'+h.parent.name+'_'+h.name)).write_bytes(h.read_bytes())
manifest={str(x.resolve()):hashlib.sha256(x.read_bytes()).hexdigest() for x in protected}
(P/'evidence/frozen_inputs.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')

attr=b'(* syn_preserve=1, syn_allow_retiming=0, syn_srlstyle="registers" *)'
def kept_inputs(name, width, rhs):
    # Each stage gets a separate kept D net, including the constant first reset D.
    decl=b''
    for i in range(width):
        decl+=f'    (* syn_keep=1 *) wire {name}_d{i} = '.encode()+rhs[i]+b';\n'
    vector=b'{'+b','.join(f'{name}_d{i}'.encode() for i in reversed(range(width)))+b'}'
    return decl,vector

original=(B/'rtl/v7_sfd_candidate.v').read_bytes()
data=original.replace(b'(* syn_preserve=1, syn_allow_retiming=0 *)',attr)
data=data.replace(b'reg [1:0] cr, hr;',b'reg [1:0] cr;\n    '+attr+b' reg [1:0] hr;')
for name,clk in [('cr','cam_clk'),('hr','host_clk')]:
    decl,vec=kept_inputs(name,2,[b"1'b0",name.encode()+b'[0]'])
    needle=f'    always @(posedge {clk} or posedge reset_any)'.encode()
    data=data.replace(needle,decl+needle)
    data=data.replace((name+'<={'+name+"[0],1'b0}").encode(),name.encode()+b'<='+vec)
for name,width,rhs in [('ack_sync',2,[b'ack',b'ack_sync[0]']),
                       ('req_sync',3,[b'request',b'req_sync[0]',b'req_sync[1]']),
                       ('overrun_sync',2,[b'sticky_overrun',b'overrun_sync[0]'])]:
    decl,vec=kept_inputs(name,width,rhs)
    needle=re.search(rb'    '+re.escape(attr)+rb' reg \['+str(width-1).encode()+rb':0\] '+name.encode()+rb';',data).group()
    data=data.replace(needle,needle+b'\n'+decl.rstrip())
    expr={'ack_sync':b'{ack_sync[0],ack}','req_sync':b'{req_sync[1:0],request}',
          'overrun_sync':b'{overrun_sync[0],sticky_overrun}'}[name]
    data=data.replace(name.encode()+b'<='+expr,name.encode()+b'<='+vec)
header=b'// ADS guide printed pp52,83-84,91-93,103-104; Pango attribute reference p88.\n// Isolated mapping candidate: stage count, reset polarity and all enables unchanged.\n'
candidate=header+data

bus_original=(B/'rtl/v7_sdt_bus.v').read_bytes()
bus=bus_original.replace(b'(* syn_preserve=1, syn_allow_retiming=0 *)',attr)
decl,vec=kept_inputs('reset_pipe',4,[b"1'b0",b'reset_pipe[0]',b'reset_pipe[1]',b'reset_pipe[2]'])
bus=bus.replace(b'  always @(posedge clk or posedge cam_reset[g] or posedge rst)',decl+b'  always @(posedge clk or posedge cam_reset[g] or posedge rst)')
bus=bus.replace(b"reset_pipe<={reset_pipe[2:0],1'b0}",b'reset_pipe<='+vec)
bus=header+bus
for name,old,new in [('v7_sfd_candidate.v',original,candidate),('v7_sdt_bus.v',bus_original,bus)]:
    (P/'baseline'/name).write_bytes(old)
    (P/'rtl'/name).write_bytes(new)
    (P/'evidence'/(name+'.diff')).write_text(''.join(difflib.unified_diff(
        old.decode('ascii').splitlines(True),new.decode('ascii').splitlines(True),
        fromfile='frozen/'+name,tofile='candidate/'+name)),encoding='ascii')

# Simulation-only baseline names keep original body byte-for-byte otherwise.
ref=original.replace(b'v7_sfd_candidate',b'dsr_baseline_source').replace(b'v7_sfd_counter',b'dsr_baseline_counter')
refbus=bus_original.replace(b'v7_sdt_bus',b'dsr_baseline_bus').replace(b'v7_sfd_candidate',b'dsr_baseline_source')
(P/'sim/baseline_source.v').write_bytes(ref)
(P/'sim/baseline_bus.v').write_bytes(refbus)

tb=(S/'tb_v7_sfd_candidate.sv').read_bytes()
extra=b'''
    wire [31:0] ref_data;
    wire ref_rv,ref_re,ref_sv,ref_av,ref_ov;
    dsr_baseline_source ref_dut(cam_clk,cam_reset,host_clk,host_reset,
        v,h,h,cs_r,observed_valid,rd,acq,rel,addr,ref_data,ref_rv,ref_re,ref_sv,ref_av,ref_ov);
    integer compare_cam=0,compare_host=0,compare_async=0;
    task compare_all;
      begin
        if({rdata,rv,re,sv,av,ov} !== {ref_data,ref_rv,ref_re,ref_sv,ref_av,ref_ov})
          $fatal(1,"FAIL source complete outputs t=%0t",$time);
        if({dut.cr,dut.hr,dut.ack_sync,dut.req_sync,dut.overrun_sync,
            dut.request,dut.ack,dut.mailbox,dut.host_bank,dut.seq_q,
            dut.bytes_q,dut.aligned_q,dut.native_q,dut.overlap_q,dut.raw_overlap_q,
            dut.segments_q,dut.odd_q,dut.gap_q} !==
           {ref_dut.cr,ref_dut.hr,ref_dut.ack_sync,ref_dut.req_sync,ref_dut.overrun_sync,
            ref_dut.request,ref_dut.ack,ref_dut.mailbox,ref_dut.host_bank,ref_dut.seq_q,
            ref_dut.bytes_q,ref_dut.aligned_q,ref_dut.native_q,ref_dut.overlap_q,ref_dut.raw_overlap_q,
            ref_dut.segments_q,ref_dut.odd_q,ref_dut.gap_q})
          $fatal(1,"FAIL source stages mailbox handshake counters t=%0t",$time);
      end
    endtask
    always @(posedge cam_clk) begin #0.002; compare_all(); compare_cam++; end
    always @(posedge host_clk) begin #0.002; compare_all(); compare_host++; end
    always @(posedge cam_reset or posedge host_reset) begin #0.002; compare_all(); compare_async++; end
'''
tb=tb.replace(b'    integer errors=0,checks=0;',extra+b'    integer errors=0,checks=0;')
tb=tb.replace(b'        $finish;',b'        $display("DSR_SOURCE_COMPARE_PASS cam=%0d host=%0d async=%0d",compare_cam,compare_host,compare_async);\n        $finish;')
(P/'sim/tb_source.sv').write_bytes(tb)

fixture=(T/'fixture.vh').read_bytes().replace(b'v7_sdb dut',b'v7_sdt_bus dut')
ports={'awvalid':1,'awready':1,'awaddr':32,'wvalid':1,'wready':1,'wdata':32,'wstrb':4,
       'bvalid':1,'bready':1,'bresp':2,'arvalid':1,'arready':1,'araddr':32,'rvalid':1,'rready':1,'rdata':32,'rresp':2}
outs=['s_awready','s_wready','s_bvalid','s_bresp','s_arready','s_rvalid','s_rdata','s_rresp',
      'm_awvalid','m_awaddr','m_wvalid','m_wdata','m_wstrb','m_bready','m_arvalid','m_araddr','m_rready']
extra='\n'+''.join(f'wire {"" if ports[n[2:]]==1 else "["+str(ports[n[2:]]-1)+":0] "}ref_{n};\n' for n in outs)
extra+='dsr_baseline_bus ref_bus (.clk(clk),.rst(rst),.cam_clk({4{camclk}}),.cam_reset(cr),.raw_vsync(rawvs),.raw_href(href),.raw_byte_accept(href),.capture_vsync(capvs),.capture_valid(capvalid),'
extra+=','.join(f'.{p}_{n}({"ref_" if p+"_"+n in outs else ""}{p}_{n})' for p in ['s','m'] for n in ports)+');\n'
extra+='integer bus_cycles=0;\nalways @(posedge clk or posedge camclk) begin #0.002;\n'
extra+='if({'+','.join(outs)+'} !== {'+','.join('ref_'+n for n in outs)+'}) $fatal(1,"FAIL all bus outputs t=%0t",$time); bus_cycles++; end\n'
extra+='genvar cmp; generate for(cmp=0;cmp<4;cmp=cmp+1) begin: stage_compare\n'
internal=['reset_pipe','source.cr','source.hr','source.ack_sync','source.req_sync','source.overrun_sync',
          'source.mailbox','source.host_bank','source.request','source.ack','source.seq_q','source.bytes_q',
          'source.aligned_q','source.native_q','source.segments_q','source.odd_q']
extra+='always @(posedge clk or posedge camclk or posedge cr[cmp] or posedge rst) begin #0.002;\n'
extra+='if({'+','.join('dut.cameras[cmp].'+n for n in internal)+'} !== {'+','.join('ref_bus.cameras[cmp].'+n for n in internal)+'}) $fatal(1,"FAIL 28sync 32reset mailbox counts camera=%0d",cmp); end\nend endgenerate\n'
(P/'sim/fixture.vh').write_bytes(fixture+extra.encode())
bustb=(T/'tb.sv').read_bytes().replace(b'$display("SDB_ALL_PASS checks=%0d",checks);',b'$display("DSR_BUS_COMPARE_PASS cycles=%0d",bus_cycles);$display("SDB_ALL_PASS checks=%0d",checks);')
(P/'sim/tb_bus.sv').write_bytes(bustb)
topology=[]
for c in range(4):
    prefix=f'source_diagnostics/cameras[{c}]'
    for n,w in [('ack_sync',2),('req_sync',3),('overrun_sync',2)]:
        for i in range(w): topology.append({'kind':'sync','logical':f'{prefix}/source/{n}[{i}]','kept_d':f'{prefix}/source/{n}_d{i}'})
    for n,w in [('source/cr',2),('source/hr',2),('reset_pipe',4)]:
        for i in range(w): topology.append({'kind':'reset','logical':f'{prefix}/{n}[{i}]','kept_d':f'{prefix}/{n}_d{i}'})
assert sum(x['kind']=='sync' for x in topology)==28
assert sum(x['kind']=='reset' for x in topology)==32
(P/'evidence/topology_contract.json').write_text(json.dumps(topology,indent=2),encoding='utf8')
print('Prepared isolated documented attribute candidate: 28 sync + 32 reset; no PDS invoked.')
