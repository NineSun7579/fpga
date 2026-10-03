"""Generate byte-preserving isolated production integration and byte backups."""
from pathlib import Path
import hashlib,json,difflib
R=Path(__file__).resolve().parent; P=R.parents[1];S=P/'source'
OUT=R/'candidate';BACK=R/'original';OUT.mkdir(exist_ok=True);BACK.mkdir(exist_ok=True)
manifest={}
def load(rel):
 p=S/rel;b=p.read_bytes();q=BACK/rel;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(b)
 manifest[rel]=dict(source=str(p),sha256=hashlib.sha256(b).hexdigest());return b
def replace(b,old,new):
 old=old.encode('ascii');new=new.encode('ascii');assert b.count(old)==1,old;return b.replace(old,new)
def save(rel,b):
 p=OUT/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
link=load('sfp/sfp_rx_link.v')
link=replace(link,'output wire        o_rx_sigdet','output wire [31:0] o_raw_d,\n    output wire [3:0] o_raw_k, o_disp_err, o_decode_err,\n    output wire [2:0] o_rxstatus,\n    output wire [1:0] o_phase,\n    output wire o_raw_en,\n    output wire        o_rx_sigdet')
link=replace(link,'    assign o_rxd    = rxd_al;','    assign o_raw_d=rxd_raw; assign o_raw_k=rxk_raw;\n    assign o_disp_err=rdisper_2; assign o_decode_err=rdecer_2;\n    assign o_rxstatus=rxstatus_2; assign o_phase=rot;\n    assign o_raw_en=rx_en_sync[1];\n    assign o_rxd    = rxd_al;')
save('sfp/sfp_rx_link.v',link)
top=load('top.v')
top=replace(top,'parameter   MSI_NUM = 5,','parameter   MSI_NUM = 5,\n    parameter SFP_NEW_PARSER = 0,')
top=replace(top,'sfp_rx_link u_sfp_rx_link (','wire [31:0] sfp_raw_d; wire [3:0] sfp_raw_k,sfp_disp_err,sfp_decode_err;\nwire [2:0] sfp_raw_status; wire [1:0] sfp_phase;\nwire sfp_raw_en,sfp_malformed,sfp_parser_overflow;\nsfp_rx_link u_sfp_rx_link (\n    .o_raw_d(sfp_raw_d),.o_raw_k(sfp_raw_k),.o_disp_err(sfp_disp_err),\n    .o_decode_err(sfp_decode_err),.o_rxstatus(sfp_raw_status),\n    .o_phase(sfp_phase),.o_raw_en(sfp_raw_en),')
start=top.index(b'sfp_video_rx u_sfp_video_rx (');end=top.index(b'\n);',start)+3
old=top[start:end]
old=old.replace(b'.o_overflow ()',b'.o_overflow (sfp_parser_overflow)')
new=b'''generate if (SFP_NEW_PARSER) begin : sfp_new_rx
rx_symbol_candidate u_parser(.i_clk(sfp_rx_clk),.i_rst_n(sfp_rx_rst_n),
 .i_en(sfp_raw_en),.i_rxd(sfp_raw_d),.i_rxk(sfp_raw_k),
 .o_vs(sfp_vs),.o_hs(sfp_hs),.o_de(sfp_de),.o_pix(sfp_pix),
 .o_overflow(sfp_parser_overflow),.o_malformed(sfp_malformed));
end else begin : sfp_old_rx
assign sfp_malformed=1'b0;
'''+old+b'''\nend endgenerate
sfp_rx_diagnostics #(.NEW_PARSER(SFP_NEW_PARSER)) u_sfp_diag(
 .rx_clk(sfp_rx_clk),.rx_rst_n(sfp_rx_rst_n),.host_clk(axi_clk),.host_rst_n(~axi_rst),
 .link_en(sfp_raw_en),.raw_d(sfp_raw_d),.raw_k(sfp_raw_k),
 .disp_err(sfp_disp_err),.decode_err(sfp_decode_err),.status(sfp_raw_status),
 .phase(sfp_phase),.vs(sfp_vs),.de(sfp_de),.malformed(sfp_malformed),
 .overflow(sfp_parser_overflow),.host_snapshot(sfp_rx_diag_bank));'''
top=top[:start]+new+top[end:]
top=replace(top,'.sfp_diag_status(sfp_diag_status),','.sfp_diag_status(sfp_diag_status),\n    .sfp_rx_diag_bank(sfp_rx_diag_bank),')
top=replace(top,'prep_regs #(.TICK_DIV(50), .SFP_DIAG_EN(1)) prep_regs_u (','wire [511:0] sfp_rx_diag_bank;\nprep_regs #(.TICK_DIV(50), .SFP_DIAG_EN(1)) prep_regs_u (')
save('top.v',top)
reg=load('preprocess/prep_regs.v')
reg=replace(reg,'input  wire [31:0]                   sfp_diag_rejects','input wire [511:0] sfp_rx_diag_bank,\n    input  wire [31:0]                   sfp_diag_rejects')
reg=replace(reg,'    reg        r_bypass;','    reg [3:0] rx_diag_index;\n    reg [511:0] rx_diag_frozen;\n    reg [31:0] rx_diag_capture_seq;\n    reg        r_bypass;')
# Independent write-only capture/index register; existing write/read cases unchanged.
anchor='    reg [3:0] rx_diag_index;'
insert='''    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin rx_diag_index<=0;rx_diag_frozen<=0;rx_diag_capture_seq<=0;end
        else if(SFP_DIAG_EN && wr_fire && woff==8'hD0 && s_axi_wstrb[0]) begin
            rx_diag_index<=s_axi_wdata[3:0];
            if(s_axi_wstrb[1] && s_axi_wdata[8]) begin
                rx_diag_frozen<=sfp_rx_diag_bank;rx_diag_capture_seq<=rx_diag_capture_seq+1;
            end
        end
    end
'''
reg=replace(reg,'    wire [7:0] woff = aw_addr[7:0];','    wire [7:0] woff = aw_addr[7:0];\n'+insert)
reg=replace(reg,'        case (ar_addr[7:0])',"        case (ar_addr[7:0])\n            8'hD0: rdata_mux = SFP_DIAG_EN ? {28'd0,rx_diag_index} : 0;\n            8'hE0: rdata_mux = SFP_DIAG_EN ? rx_diag_frozen[rx_diag_index*32 +:32] : 0;\n            8'hF0: rdata_mux = SFP_DIAG_EN ? rx_diag_capture_seq : 0;")
save('preprocess/prep_regs.v',reg)
for rel in ['sfp/sfp_video_rx.v','sfp/sfp_rx_cam_if.v','sfp/video_async_fifo.v']:save(rel,load(rel))
save('sfp/rx_symbol_candidate.sv',(R.parent/'sfp_payload_probe/rx_symbol_candidate.sv').read_bytes())
save('sfp/sfp_rx_diagnostics.sv',(R/'sfp_rx_diagnostics.sv').read_bytes())
ip=P/'ipcore/hsst_sfp/hsst_sfp.v';manifest['vendor_ip']=dict(source=str(ip),sha256=hashlib.sha256(ip.read_bytes()).hexdigest())
(R/'manifest.json').write_text(json.dumps(manifest,indent=2))
parts=[]
for path in sorted(OUT.rglob('*')):
 if not path.is_file():continue
 rel=path.relative_to(OUT).as_posix();before=BACK/rel
 old=before.read_bytes().splitlines(keepends=True) if before.exists() else []
 new=path.read_bytes().splitlines(keepends=True)
 parts.extend(difflib.diff_bytes(difflib.unified_diff,old,new,
     fromfile=('a/source/'+rel).encode(),tofile=('b/source/'+rel).encode()))
(R/'integration.patch').write_bytes(b''.join(parts))
for row in manifest.values():assert hashlib.sha256(Path(row['source']).read_bytes()).hexdigest()==row['sha256']
print('Generated isolated candidate and byte-exact backups; production/IP unchanged')
