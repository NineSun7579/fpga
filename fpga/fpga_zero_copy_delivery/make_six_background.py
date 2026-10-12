"""Source-only isolated clone; byte substitutions retain all original GBK bytes."""
from pathlib import Path
import hashlib
import json
import os
import re
import sys
from make_six_batch import ROOT, replace

BASE = ROOT / 'integrated_six_batch'
OUT = ROOT / 'integrated_six_background'
NEW = ('background_producer.v', 'background_six.v', 'background_write_arbiter.v')

PORTS = '''    output wire bg_sof, bg_valid, bg_bad, bg_raw_publish,
    output wire [15:0] bg_pixel,
'''
CONNECT = '''        .bg_sof(bg_sof),.bg_valid(bg_valid),.bg_bad(bg_bad),
        .bg_raw_publish(bg_raw_publish),.bg_pixel(bg_pixel),
'''
ADAPTER_PORTS = '''input wire [5:0] bg_sof, bg_valid, bg_bad, bg_raw_publish,
input wire [95:0] bg_pixels,
'''

def adapter(raw):
    for declaration in ('wire [31:0] l_araddr;','wire l_arvalid;','wire l_arready;'):
        raw=replace(raw,declaration+'\n','')
    raw = replace(raw, 'output wire [5:0] capture_hold,', ADAPTER_PORTS+'output wire [5:0] capture_hold,')
    raw = replace(raw, '.s_axi_rdata(s_axi_rdata),', '.s_axi_rdata(bridge_rdata),')
    raw = replace(raw, 'wire [31:0] l_awaddr;', '''wire [31:0] l_araddr;
wire l_arvalid, l_arready;
wire [127:0] bridge_rdata;
reg record_read;
reg [127:0] record_data;
wire [3071:0] bg_records;
wire bg_enable, bg_quiescent, bg_quarantine;
assign s_axi_rdata=record_read ? record_data : bridge_rdata;
always @(posedge clk) begin
    if(rst) begin record_read<=0; record_data<=0; end
    else if(l_arvalid && l_arready) begin
        record_read<=l_araddr>=32'h40020200 && l_araddr<=32'h40020370 && l_araddr[3:0]==0;
        if(l_araddr>=32'h40020200 && l_araddr<=32'h40020370 && l_araddr[3:0]==0)
            record_data<=bg_records[((l_araddr-32'h40020200)>>4)*128 +:128];
    end
end
wire [31:0] l_awaddr;''')
    raw = replace(raw, '.capture_hold(capture_hold),', '''.capture_hold(capture_hold),
.background_enable(bg_enable),.background_quiescent(bg_quiescent),
.background_quarantine(bg_quarantine),''')
    pos=raw.index(b');')+2
    header, body=raw[:pos], raw[pos:]
    names=('awaddr','awlen','awsize','awburst','awvalid','awready','wdata','wstrb','wlast','wvalid','wready','bresp','bvalid','bready')
    for name in names:
        body=re.sub(rb'(?<!\.)\bm_axi_'+name.encode()+rb'\b', ('ep_'+name).encode(), body)
    declarations=''
    for name, width in [('awaddr',32),('awlen',8),('awsize',3),('awburst',2),('awvalid',1),('awready',1),('wdata',128),('wstrb',16),('wlast',1),('wvalid',1),('wready',1),('bresp',2),('bvalid',1),('bready',1)]:
        declarations+=f'wire [{width-1}:0] ep_{name};\n'
    extra='''
wire [31:0] bg_awaddr;
wire [7:0] bg_awlen;
wire bg_awvalid, bg_awready, bg_wvalid, bg_wlast, bg_wready, bg_bvalid, bg_bready;
wire [127:0] bg_wdata;
wire [15:0] bg_wstrb;
wire [1:0] bg_bresp, arb_awready, arb_wready, arb_bvalid;
wire [3:0] arb_bresp;
wire [11:0] legacy_invalidate;
genvar legacy_camera, legacy_bank;
generate for(legacy_camera=0;legacy_camera<6;legacy_camera=legacy_camera+1) begin: invalidate_camera
    for(legacy_bank=0;legacy_bank<2;legacy_bank=legacy_bank+1) begin: invalidate_bank
        localparam SLOT=legacy_camera==4 ? 0 : (legacy_camera<4 ? legacy_camera+1 : 5);
        assign legacy_invalidate[legacy_camera*2+legacy_bank]=cmd_valid && cmd_ready && selected_mode &&
            dst==32'h0a200000+SLOT*32'h80000+legacy_bank*32'h40000;
    end
end endgenerate
assign ep_awready=arb_awready[0]; assign bg_awready=arb_awready[1];
assign ep_wready=arb_wready[0]; assign bg_wready=arb_wready[1];
assign ep_bvalid=arb_bvalid[0]; assign bg_bvalid=arb_bvalid[1];
assign ep_bresp=arb_bresp[1:0]; assign bg_bresp=arb_bresp[3:2];
assign m_axi_awsize=3'd4; assign m_axi_awburst=2'd1;
background_six #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) background (
.clk(clk),.rst(rst),.enable(bg_enable),.invalidate(legacy_invalidate),.sof(bg_sof),.pixel_valid(bg_valid),
.source_bad(bg_bad),.raw_publish(bg_raw_publish),.pixels(bg_pixels),
.source_sequence(camera_sequence),.quiescent(bg_quiescent),.quarantine(bg_quarantine),
.records(bg_records),.awaddr(bg_awaddr),.awlen(bg_awlen),.awvalid(bg_awvalid),.awready(bg_awready),
.wdata(bg_wdata),.wstrb(bg_wstrb),.wvalid(bg_wvalid),.wlast(bg_wlast),.wready(bg_wready),
.bresp(bg_bresp),.bvalid(bg_bvalid),.bready(bg_bready));
background_write_arbiter arbiter (
.clk(clk),.rst(rst),.in_awaddr({bg_awaddr,ep_awaddr}),.in_awlen({bg_awlen,ep_awlen}),
.in_awvalid({bg_awvalid,ep_awvalid}),.in_awready(arb_awready),
.in_wdata({bg_wdata,ep_wdata}),.in_wstrb({bg_wstrb,ep_wstrb}),
.in_wvalid({bg_wvalid,ep_wvalid}),.in_wlast({bg_wlast,ep_wlast}),.in_wready(arb_wready),
.in_bresp(arb_bresp),.in_bvalid(arb_bvalid),.in_bready({bg_bready,ep_bready}),
.awaddr(m_axi_awaddr),.awlen(m_axi_awlen),.awvalid(m_axi_awvalid),.awready(m_axi_awready),
.wdata(m_axi_wdata),.wstrb(m_axi_wstrb),.wvalid(m_axi_wvalid),.wlast(m_axi_wlast),
.wready(m_axi_wready),.bresp(m_axi_bresp),.bvalid(m_axi_bvalid),.bready(m_axi_bready));
'''
    return header+b'\n'+declarations.encode('ascii')+body.replace(b'endmodule',extra.encode('ascii')+b'endmodule')

def regs(raw):
    raw=replace(raw,'    output reg selected_mode','''    output reg background_enable,
    input wire background_quiescent, background_quarantine,
    output reg selected_mode''')
    raw=replace(raw,'            cmd_valid<=0; cmd_dst<=DEST; selected_mode<=0;',
                '            background_enable<=0;\n            cmd_valid<=0; cmd_dst<=DEST; selected_mode<=0;')
    raw=replace(raw,'                        if(!w_data[0] && (busy || quarantined)) s_bresp<=2;',
                '''                        if(selected_mode && (background_enable || !background_quiescent) && w_data[0]) s_bresp<=2;
                        else if(!w_data[0] && (busy || quarantined)) s_bresp<=2;''')
    raw=replace(raw,'                    default: s_bresp<=2;', '''                    BASE+32'h180: begin
                        if(w_strb!=4'hf || w_data>1 ||
                           (w_data[0] && (background_quarantine ||
                            (selected_mode && selector_locked)))) s_bresp<=2;
                        else background_enable<=w_data[0];
                    end
                    default: s_bresp<=2;''')
    raw=replace(raw,"s_rdata<=32'hf; // RGB, thumbnail, six-camera ownership, register snapshot",
                "s_rdata<=32'h1f; // RGB, thumbnail, six-camera ownership, snapshot, background")
    raw=replace(raw,'                    default: begin s_rdata<=0; s_rresp<=2; end', '''                    BASE+32'h180: s_rdata<={29'd0,background_quarantine,background_quiescent,background_enable};
                    default: begin
                        s_rdata<=0;
                        if(!(s_araddr>=BASE+32'h200 && s_araddr<=BASE+32'h370 && s_araddr[3:0]==0)) s_rresp<=2;
                    end''')
    return raw

def project(raw):
    def rebase(m):
        path=(BASE/'project'/m[2].decode('ascii')).resolve()
        ref=('../source/'+path.relative_to(BASE/'source').as_posix() if path.is_relative_to(BASE/'source') else os.path.relpath(path,OUT/'project').replace('\\','/'))
        return m[1]+ref.encode('ascii')+m[3]
    new=re.sub(rb'(\((?:_file|_ip|_ip_source_item) ")([^"]+)(")',rebase,raw)
    anchor=b'                (_file "../source/delivery/delivery_raw_letterbox.v"'
    insertion=b''.join(('                (_file "../source/delivery/'+n+'"\n                    (_format verilog)\n                    (_timespec "2026-10-09T14:44:37")\n                )\n').encode('ascii') for n in NEW)
    assert new.count(anchor)==1
    return new.replace(anchor,insertion+anchor)

def main():
    if OUT.exists():
        assert '--refresh' in sys.argv, 'Refuse to overwrite existing clone'
        for record in json.loads((ROOT/'six_background_source_manifest.json').read_text()):
            assert hashlib.sha256((BASE/record['path']).read_bytes()).hexdigest()==record['baseline_sha256']
    records=[]
    inputs=list((BASE/'source').rglob('*'))+[BASE/'project/project.pds']
    for p in inputs:
        if not p.is_file(): continue
        raw=p.read_bytes(); new=raw; rel=p.relative_to(BASE).as_posix()
        if rel=='source/ov5640/ov5640_ddr/ov5640_ddr.v':
            new=replace(raw,'    output wire [1:0] lease_published,',PORTS+'    output wire [1:0] lease_published,')
            new=replace(new,'assign lease_prev_base=prev_frame_base;', '''// Passive export only; existing RAW controls are byte-identical.
reg [31:0] bg_sequence_q;
always @(posedge axi_clk) begin
    if(axi_rst) bg_sequence_q<=0; else bg_sequence_q<=dbg_last_cnt;
end
assign bg_sof=m_vsync;
assign bg_valid=m_data_valid;
assign bg_pixel=m_data;
// Successful RAW tag retirement also requests local capture flush. Flush is
// not a source fault; missing RAW publication is handled by branch deadline.
assign bg_bad=capture_bad || capture_overflow || dma_abort;
assign bg_raw_publish=dbg_last_cnt!=bg_sequence_q;
assign lease_prev_base=prev_frame_base;''')
        elif rel=='source/ov5640/ov5640_top.v':
            new=replace(raw,'    output wire [1:0] lease_published,',PORTS+'    output wire [1:0] lease_published,')
            new=replace(new,'        .lease_prev_base(lease_prev_base),',CONNECT+'        .lease_prev_base(lease_prev_base),')
        elif rel=='source/top.v':
            new=replace(raw,'wire delivery_hold;', '''wire [5:0] bg_sof, bg_valid, bg_bad, bg_raw_publish;
wire [95:0] bg_pixels;
wire delivery_hold;''')
            for c in range(6):
                key=f'    .lease_prev_base(six_prev[{c*32} +: 32]),'
                conn=f'    .bg_sof(bg_sof[{c}]),.bg_valid(bg_valid[{c}]),.bg_bad(bg_bad[{c}]),\n    .bg_raw_publish(bg_raw_publish[{c}]),.bg_pixel(bg_pixels[{c*16} +:16]),\n'
                new=replace(new,key,conn+key)
            new=replace(new,'delivery_top_adapter delivery_u (','''delivery_top_adapter delivery_u (
.bg_sof(bg_sof),.bg_valid(bg_valid),.bg_bad(bg_bad),.bg_raw_publish(bg_raw_publish),.bg_pixels(bg_pixels),''')
        elif rel=='source/delivery/delivery_top_adapter.v': new=adapter(raw)
        elif rel=='source/delivery/delivery_regs.v': new=regs(raw)
        elif rel=='source/pcie_dma/pcie_fifo.v':
            new=replace(raw,"                              r_cur_addr <= 32'h40020120;", """                              r_cur_addr <= 32'h40020120 ||
                              r_cur_addr == 32'h40020180 ||
                              (r_cur_addr >= 32'h40020200 && r_cur_addr <= 32'h40020370 && r_cur_addr[3:0]==0);""")
        elif rel=='project/project.pds': new=project(raw)
        q=OUT/rel; q.parent.mkdir(parents=True,exist_ok=True); q.write_bytes(new)
        assert p.read_bytes()==raw
        records.append(dict(path=rel,baseline_sha256=hashlib.sha256(raw).hexdigest(),candidate_sha256=hashlib.sha256(new).hexdigest()))
    for n in NEW:
        raw=(ROOT/n).read_bytes(); assert raw.isascii(); (OUT/'source/delivery'/n).write_bytes(raw)
    for ref in re.findall(rb'\((?:_file|_ip|_ip_source_item) "([^"]+)"',(OUT/'project/project.pds').read_bytes()):
        assert (OUT/'project'/ref.decode('ascii')).resolve().exists(),ref
    (ROOT/'six_background_source_manifest.json').write_text(json.dumps(records,indent=2))
    print('Source-only clone generated; IPs reused;',len(records),'baseline hashes recorded')

if __name__=='__main__': main()
