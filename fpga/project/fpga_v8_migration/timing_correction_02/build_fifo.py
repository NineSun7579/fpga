"""Byte-level candidate generation; never edits frozen RTL or route evidence."""
from pathlib import Path
import hashlib,json,difflib
HERE=Path(__file__).resolve().parent
M=HERE.parent
def sha(data): return hashlib.sha256(data).hexdigest()
def transform(raw):
    old=b'''wire [31:0] rx_input_bytes = ((fpga_ddr3_length - rx_chunk_bytes) >= 16) ?
                            32'd16 : fpga_ddr3_length - rx_chunk_bytes;'''
    # The registered byte count follows the synchronous RAM read request.
    new=b'''reg [4:0] rx_input_bytes;
always @(posedge fifo_pcie_clk or posedge fifo_pcie_rst) begin
    if (fifo_pcie_rst) rx_input_bytes <= 0;
    else if (fpga_rx_clk_en_r)
        rx_input_bytes <= (fpga_rx_addr_r == total_beats-1 &&
                           fpga_ddr3_length[3:0] != 0) ?
                           {1'b0,fpga_ddr3_length[3:0]} : 5'd16;
end'''
    # Normalize only the search view, retaining all other source bytes.
    crlf=b'\r\n' in raw
    needle=old.replace(b'\n',b'\r\n') if old not in raw and crlf else old
    replacement=new.replace(b'\n',b'\r\n') if b'\r\n' in needle else new
    if raw.count(needle)==0 and b'wire [31:0] rx_input_bytes;' in raw:
        # ModelSim compatibility copy moves declarations above instance use.
        raw=raw.replace(b'wire [31:0] rx_input_bytes;',b'reg [4:0] rx_input_bytes;')
        needle=old.replace(b'wire [31:0] rx_input_bytes =',b'assign rx_input_bytes =')
        replacement=new.replace(b'reg [4:0] rx_input_bytes;\n',b'')
    assert raw.count(needle)==1,'Expected exact original metadata expression'
    raw=raw.replace(needle,replacement)
    # The old expression was 32 bits; preserve downstream explicit zero extension.
    raw=raw.replace(b'rx_input_bytes[5:0]',b'{1\'b0,rx_input_bytes}')
    return raw
def main():
    out=HERE/'rtl';out.mkdir(exist_ok=True)
    source=M/'whole_candidate_v3_timing_route_01/rtl/fpga_v8_pcie_fifo_h2f_rfg01.v'
    before=source.read_bytes()
    candidate=transform(before).replace(b'module fpga_v8_pcie_fifo_h2f_rfg01',b'module fpga_v8_pcie_fifo_h2f_tc02')
    target=out/'fpga_v8_pcie_fifo_h2f_tc02.v';target.write_bytes(candidate)
    (HERE/'binding.json').write_text(json.dumps({'source':str(source),'original_sha256':sha(before),'candidate':str(target),'candidate_sha256':sha(candidate),'instance_type_from':'fpga_v8_pcie_fifo_h2f_rfg01','instance_type_to':'fpga_v8_pcie_fifo_h2f_tc02','routed_timing_verified':False},indent=2))
    text=lambda b:b.decode('ascii','backslashreplace').splitlines(True)
    (HERE/'fifo.diff').write_text(''.join(difflib.unified_diff(text(before),text(candidate))),encoding='ascii')
    assert source.read_bytes()==before
if __name__=='__main__':main()
