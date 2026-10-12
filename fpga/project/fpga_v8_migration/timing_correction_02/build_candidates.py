"""Byte-preserving copies from routed v3. Writes only timing_correction_02."""
from pathlib import Path
import hashlib,json,difflib,re
HERE=Path(__file__).resolve().parent
SOURCE=HERE.parent/'whole_candidate_v3_timing_route_01'
RTL=HERE/'rtl'
E=HERE/'evidence'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def replace_once(b,a,c):
    assert b.count(a)==1,(a[:100],b.count(a))
    return b.replace(a,c,1)
def emit(name,b):
    src=SOURCE/'rtl'/name
    new=name.replace('.v','_tc02.v')
    b=replace_once(b,b'module '+name[:-2].encode(),b'module '+new[:-2].encode())
    (RTL/new).write_bytes(b)
    (E/(new+'.diff')).write_text(''.join(difflib.unified_diff(
        src.read_bytes().decode('ascii',errors='replace').splitlines(True),
        b.decode('ascii',errors='replace').splitlines(True),fromfile=str(src),tofile=str(RTL/new))),encoding='utf-8')
    return {'source':str(src),'source_sha256':sha(src),'candidate':str(RTL/new),'candidate_sha256':sha(RTL/new),
            'old_module':name[:-2],'new_module':new[:-2]}
def build():
    RTL.mkdir(exist_ok=True); E.mkdir(exist_ok=True)
    names=['fpga_v8_ddr_adapter.v','fpga_v8_pcie_fifo_h2f_rfg01.v']
    before={str(SOURCE/'rtl'/n):sha(SOURCE/'rtl'/n) for n in names}
    a=(SOURCE/'rtl'/names[0]).read_bytes()
    start=a.index(b'    wire [63:0] aw_end')
    end=a.index(b'    assign s_awready',start)
    a=a[:start]+b'''    // TC02: requests are aligned and contain at most 16 beats. Checking
    // their last beat needs only a 9-bit page-local sum. With no page
    // crossing, compare page number and last offset against a constant.
    // Invalid limits/unaligned requests remain unaccepted, exactly as before.
    localparam [27:0] LIMIT_LAST_BEAT = (DDR_ADDRESS_LIMIT >> 4) - 1;
    wire limit_ok = DDR_ADDRESS_LIMIT!=0 && DDR_ADDRESS_LIMIT<=32'h10000000 && DDR_ADDRESS_LIMIT[3:0]==0;
    wire [8:0] aw_last_in_page = {1'b0,s_awaddr[11:4]} + {5'd0,s_awlen[3:0]};
    wire [8:0] ar_last_in_page = {1'b0,s_araddr[11:4]} + {5'd0,s_arlen[3:0]};
    wire aw_range_ok = (s_awaddr[31:12] < LIMIT_LAST_BEAT[27:8]) ||
        ((s_awaddr[31:12] == LIMIT_LAST_BEAT[27:8]) &&
         (aw_last_in_page <= {1'b0,LIMIT_LAST_BEAT[7:0]}));
    wire ar_range_ok = (s_araddr[31:12] < LIMIT_LAST_BEAT[27:8]) ||
        ((s_araddr[31:12] == LIMIT_LAST_BEAT[27:8]) &&
         (ar_last_in_page <= {1'b0,LIMIT_LAST_BEAT[7:0]}));
    wire aw_ok = limit_ok && s_awlen<=15 && s_awaddr[3:0]==0 && s_awsize==4 && s_awburst==1 &&
                 !aw_last_in_page[8] && aw_range_ok;
    wire ar_ok = limit_ok && s_arlen<=15 && s_araddr[3:0]==0 && s_arsize==4 && s_arburst==1 &&
                 !ar_last_in_page[8] && ar_range_ok;
''' + a[end:]
    first=emit(names[0],a)
    b=(SOURCE/'rtl'/names[1]).read_bytes()
    b=replace_once(b,b'''wire [31:0] rx_input_bytes = ((fpga_ddr3_length - rx_chunk_bytes) >= 16) ?
                            32'd16 : fpga_ddr3_length - rx_chunk_bytes;
wire [127:0] rx_input_mask = {128{1'b1}} >> ((32'd16-rx_input_bytes)*8);''',b'''// TC02: capture chunk metadata at the existing RAM-copy start edge.
// Chunk length is fixed throughout this copy. The last beat's byte count and
// mask are local registered metadata; no 32-bit subtract/subtract/barrel-mask
// chain connects the controller length to RX packed data on each copy edge.
reg [28:0] rx_beats_remaining;
reg [4:0] rx_tail_bytes;
reg [127:0] rx_tail_mask;
wire rx_last_input = (rx_beats_remaining == 1);
wire [31:0] rx_input_bytes = rx_last_input ? {27'd0,rx_tail_bytes} : 32'd16;
wire [127:0] rx_input_mask = rx_last_input ? rx_tail_mask : {128{1'b1}};
wire [4:0] chunk_tail_bytes = (fpga_ddr3_length[3:0] == 0) ?
                             5'd16 : {1'b0,fpga_ddr3_length[3:0]};
wire [127:0] chunk_tail_mask;
genvar tail_lane;
generate for (tail_lane=0;tail_lane<16;tail_lane=tail_lane+1) begin : tc02_tail_mask
    assign chunk_tail_mask[tail_lane*8 +: 8] =
        (chunk_tail_bytes > tail_lane) ? 8'hff : 8'h00;
end endgenerate''')
    b=replace_once(b,b'        rx_bytes_total <= 0; rx_chunk_bytes <= 0;',b'''        rx_bytes_total <= 0; rx_chunk_bytes <= 0;
        rx_beats_remaining <= 0; rx_tail_bytes <= 0; rx_tail_mask <= 0;''')
    b=replace_once(b,b'            rx_chunk_bytes <= 0;',b'''            rx_chunk_bytes <= 0;
            rx_beats_remaining <= total_beats[28:0];
            rx_tail_bytes <= chunk_tail_bytes;
            rx_tail_mask <= chunk_tail_mask;''')
    b=replace_once(b,b'            if (fpga_rx_clk_en_d) begin',b'''            if (fpga_rx_clk_en_d) begin
                rx_beats_remaining <= rx_beats_remaining - 1'b1;''')
    second=emit(names[1],b)
    assert before=={p:sha(Path(p)) for p in before}
    manifest={'source_root':str(SOURCE),'changes':[first,second],'protected_unchanged':before,
              'no_pds':True,'guard_rtl_changed':False}
    (HERE/'candidate_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))
    return manifest
if __name__=='__main__':build()
