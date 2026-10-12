"""Byte-only, backed-up changes. Never touch vendor IP or camera clocks."""
from pathlib import Path
root=Path(__file__).resolve().parents[2]
def edit(name, changes):
    p=root/name
    b=p.read_bytes()
    for old,new in changes:
        old=old.encode('ascii');new=new.encode('ascii')
        assert b.count(old)==1,(name,old,b.count(old))
        b=b.replace(old,new)
    backup=p.with_name(p.name+'.burst_credit.bak')
    assert not backup.exists(),backup
    backup.write_bytes(p.read_bytes())
    p.write_bytes(b)
edit('source/axi_dma/axi_dma_write.v',[
 ('parameter WD_LIMIT', 'parameter WAIT_FOR_DATA = 0, // camera source supplies stored beat credits\n\t\tparameter WD_LIMIT'),
 ('input abort_req,','input [15:0] data_in_available, // complete beats already stored upstream\n\tinput abort_req,'),
 ('assign max_burst_len =', '''// Do not reserve the shared DDR owner while waiting for future pixels.
// Once advertised, AW remains irrevocable even if an abort arrives.
wire source_burst_ready = !WAIT_FOR_DATA ||
                         (data_in_valid && data_in_available >= max_burst_len);
wire waiting_source = WAIT_FOR_DATA && trans && !burst_trans &&
                      !m_axi_awvalid && (len != 0) && !source_burst_ready;
reg [15:0] available_q;
always @(posedge clk) begin
    if(rst) available_q <= 0;
    else available_q <= data_in_available;
end
assign max_burst_len ='''),
 ('&& !abort_req)begin','&& !abort_req && source_burst_ready)begin'),
 ('''\tif((rst == 1'b1) || (burst_trans == 1'b0)''','''    if(rst || abort_r) wd_cnt <= 0;
    else if(waiting_source) begin
        if(data_in_available != available_q) wd_cnt <= 0;
        else if(wd_cnt != 24'hFFFFFF) wd_cnt <= wd_cnt + 1'b1;
    end
    else if((rst == 1'b1) || (burst_trans == 1'b0)'''),
 ('''    else if(!abort_r && burst_trans && (act_burst_len != 0)''','''    else if(waiting_source && (wd_cnt == WD_LIMIT))
        abort_r <= 1'b1; // no AW exists: retire locally without owning DDR
    else if(!abort_r && burst_trans && (act_burst_len != 0)''')])
edit('source/ov5640/ov5640_ddr/ov5640_ddr_w.v',[
 ('    output         capture_overflow,','    output         capture_overflow,\n    output [15:0] axi_data_available,'),
 ('    assign capture_overflow =', '''    // Stored credits span BOTH existing FIFOs and the DRM read pipeline.
    // Count accepted 32-bit writes minus consumed AXI words; no new storage.
    // Counting only the 16-deep output FIFO would deadlock at almost_full=15
    // when the input is sparse and no DRM read is pending to fill slot 16.
    localparam CREDIT_WORDS_PER_BEAT = AXI_DATA_WIDTH / 32;
    reg [12:0] stored_words;
    always @(posedge axi_clk) begin
        if(local_rst) stored_words <= 0;
        else case ({(wr_en && !full), rd_en})
            2'b10: stored_words <= stored_words + 1'b1;
            2'b01: stored_words <= stored_words - CREDIT_WORDS_PER_BEAT;
            2'b11: stored_words <= stored_words - (CREDIT_WORDS_PER_BEAT-1);
            default: stored_words <= stored_words;
        endcase
    end
    assign axi_data_available = local_rst ? 16'd0 :
                                stored_words / CREDIT_WORDS_PER_BEAT;
    assign capture_overflow =''')])
edit('source/ov5640/ov5640_ddr/ov5640_ddr.v',[
 ('    output         dma_abort_req,','    output         dma_abort_req,\n    output [15:0] axi_data_available,'),
 ('    wire                        w_valid ;','    wire [15:0] w_available;\n    wire                        w_valid ;'),
 ('    .capture_overflow(capture_overflow),','    .capture_overflow(capture_overflow),\n    .axi_data_available(w_available),'),
 ('    assign axi_data       =','    assign axi_data_available = tag_active ? 16\'d1 : (frame_active ? w_available : 16\'d0);\n    assign axi_data       =')])
edit('source/ov5640/ov5640_top.v',[
 ('    output                        cam_dma_abort_req,','    output                        cam_dma_abort_req,\n    output [15:0]                 cam_s_data_available,'),
 ('        .dma_abort_req  (cam_dma_abort_req),','        .dma_abort_req  (cam_dma_abort_req),\n        .axi_data_available(cam_s_data_available),')])
# Top has three distinct cameras. Enable credit gating only on those engines.
p=root/'source/top.v';b=p.read_bytes();changes=[]
for cam in ['cam','cam2','cam3']:
    changes.append((f'    .dma_abort_req_unused_{cam}', '')) if False else None
    # Locate actual port spelling without transcoding the source.
    import re
    matches=list(re.finditer(rb'\.cam_dma_abort_req\s*\('+cam.encode()+rb'_dma_abort_req\)',b))
    assert len(matches)==1,(cam,matches)
    token=matches[0].group().decode()
    changes.append((token, f'.cam_s_data_available({cam}_s_data_available),\n    '+token))
    matches=list(re.finditer(rb'\.abort_req\('+cam.encode()+rb'_dma_abort_req\)',b))
    assert len(matches)==1
    token=matches[0].group().decode()
    changes.append((token, f'.data_in_available({cam}_s_data_available),\n    '+token))
    instance='ov5640_axi_dma_write' if cam=='cam' else cam+'_axi_dma_write'
    start=b.rfind(b'axi_dma_write #(',0,b.index(instance.encode()+b'('))
    end=b.index(instance.encode()+b'(',start)
    token=b[start:end].decode()
    changes.append((token,token.replace('axi_dma_write #(','axi_dma_write #(\n    .WAIT_FOR_DATA(1),')))
changes.append(('wire [AXI_DATA_LEN-1:0]     ddr_axi_wdata ', 'wire [15:0] cam_s_data_available, cam2_s_data_available, cam3_s_data_available;\nwire [AXI_DATA_LEN-1:0]     ddr_axi_wdata '))
changes.append(("    .abort_req(1'b0),", "    .data_in_available(16'd0),\n    .abort_req(1'b0),"))
# Parameter blocks are identical: replace with full block including instance.
changes=[c for c in changes if not c[0].startswith('axi_dma_write #(')]
for instance in ['ov5640_axi_dma_write','cam2_axi_dma_write','cam3_axi_dma_write']:
    end=b.index(instance.encode()+b'(')+len(instance)+1
    start=b.rfind(b'axi_dma_write #(',0,end-len(instance)-1)
    token=b[start:end].decode()
    changes.append((token,token.replace('axi_dma_write #(','axi_dma_write #(\n    .WAIT_FOR_DATA(1),')))
edit('source/top.v',changes)
p=root/'source/axi_dma/axi_dma.v';b=p.read_bytes()
import re
m=list(re.finditer(rb'\.abort_req\s*\(1\'b0\)',b));assert len(m)==1
token=m[0].group().decode()
edit('source/axi_dma/axi_dma.v',[(token,".data_in_available(16'd0),\n    "+token)])
print('Applied burst credits to 6 production files; all pre-edit bytes backed up.')
