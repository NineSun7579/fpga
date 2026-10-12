"""Offline host-alignment + production bridge/decoder/register regression."""
from pathlib import Path
import ast
import subprocess
import hashlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXE = Path('C:/modeltech64_10.6e/win64')
offsets = [0x190, 0x1a0, 0x1b0, 0x1c0]

# Guard the modeled ingress against the actual DMA expression and top width.
assert b"r_cur_addr <= {(fpga_ddr3_addr >> AXI_DATA_SIZE), {AXI_DATA_SIZE{1'b0}}};" in (ROOT/'source/pcie_dma/pcie_fifo.v').read_bytes()
assert b'AXI_DATA_LEN    = 128' in (ROOT/'source/top.v').read_bytes()

# Extract only the helper AST: importing the verifier would access the board.
class Reader:
    def __init__(self, unstable=False):
        self.unstable = unstable
        self.calls = []
        self.seq = 1
    def read32(self, addr):
        self.calls.append(addr)
        off = addr-0x20000200
        assert off in offsets
        if off == 0x1c0:
            self.seq += int(self.unstable)
            return self.seq if self.unstable else 123
        return {0x190:307200, 0x1a0:1290240, 0x1b0:7}[off]

data = (ROOT/'tools/verify_cdc_stage_board.py').read_bytes()
tree = ast.parse(data)
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'stage_snapshot')
for unstable in [False, True]:
    reader = Reader(unstable)
    ns = {'d':reader}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), '<snapshot-only>', 'exec'), ns)
    result = ns['stage_snapshot'](0x20000200)
    assert [result[k] for k in ['input','output','drop']] == [307200,1290240,7]
    assert result.get('unstable',False) == unstable
    assert len(reader.calls) == (150 if unstable else 5)
    if unstable:
        assert result['seq_before'] == 60 and result['seq'] == 61

# Check generator output in memory, stopping before its filesystem write.
prep = ast.parse((ROOT/'tools/prepare_cdc_stage_verify.py').read_bytes())
stop = next(i for i,n in enumerate(prep.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='target' for t in n.targets))
ns = {'__file__':str(ROOT/'tools/prepare_cdc_stage_verify.py')}
exec(compile(ast.Module(body=prep.body[:stop], type_ignores=[]), '<prepare-in-memory>', 'exec'), ns)
assert ns['data'] == data, 'generator and verifier differ'
print('PASS verifier stable/unstable raw values and generator parity; no board import')

tb = '''`timescale 1ns/1ps
module tb_cdc_host_map;
reg clk=0; always #5 clk=~clk;
reg rst=1, valid=0, ready=1;
reg [31:0] host_addr=0;
localparam AXI_DATA_SIZE=4;
// Exact pcie_fifo ingress expression, including assignment truncation.
wire [31:0] aligned_addr = {(host_addr >> AXI_DATA_SIZE), {AXI_DATA_SIZE{1'b0}}};
wire arready, rvalid, rlast; wire [127:0] rdata;
wire [31:0] la, ld; wire lv, lr, lrv, lrr;
axi_to_axi_lite bridge(.axi_clk(clk),.axi_rst(rst),
 .s_axi_awvalid(1'b0),.s_axi_wvalid(1'b0),.s_axi_bready(1'b1),
 .s_axi_arid(4'd0),.s_axi_araddr(aligned_addr),.s_axi_arlen(8'd0),
 .s_axi_arsize(3'd4),.s_axi_arburst(2'b01),.s_axi_arvalid(valid),.s_axi_arready(arready),
 .s_axi_rvalid(rvalid),.s_axi_rready(ready),.s_axi_rdata(rdata),.s_axi_rlast(rlast),
 .m_axil_araddr(la),.m_axil_arvalid(lv),.m_axil_arready(lr),
 .m_axil_rvalid(lrv),.m_axil_rready(lrr),.m_axil_rdata(ld),.m_axil_rresp(2'b00));
wire [31:0] ca[0:3], cd[0:3];
wire [3:0] cv, cr, crv, crr;
ovreg_axil_decode decode(.clk(clk),.rst(rst),
 .s_awvalid(1'b0),.s_wvalid(1'b0),.s_bready(1'b1),
 .s_araddr(la),.s_arvalid(lv),.s_arready(lr),
 .s_rdata(ld),.s_rvalid(lrv),.s_rready(lrr),
'''
tb += ',\n'.join(f' .m{i}_araddr(ca[{i}]),.m{i}_arvalid(cv[{i}]),.m{i}_arready(cr[{i}]),.m{i}_rdata(cd[{i}]),.m{i}_rvalid(crv[{i}]),.m{i}_rready(crr[{i}]),.m{i}_rresp(2\'b00)' for i in range(4)) + ');\n'
for cam, port in enumerate([0,2,3]):
    tb += f'''ov5640_reg #(.BASE_ADDR(32'h{0x20000000+cam*0x200:08x})) cam{cam}(
 .clk(clk),.rst(rst),.s_axi_awvalid(1'b0),.s_axi_wvalid(1'b0),.s_axi_bready(1'b1),
 .s_axi_araddr(ca[{port}]),.s_axi_arvalid(cv[{port}]),.s_axi_arready(cr[{port}]),
 .s_axi_rdata(cd[{port}]),.s_axi_rvalid(crv[{port}]),.s_axi_rready(crr[{port}]),
 .dbg_cdc_input(32'd{307200+cam}),.dbg_cdc_output(32'd{1290240+cam}),
 .dbg_cdc_drop(32'd{7+cam}),.dbg_cdc_seq(32'd{123+cam}),
 .dbg_fault_snapshot(32'h80006123),.dbg_pclk_cnt(32'h12345678));
'''
tb += '''// PREP sentinel confirms all its implemented offsets retain routing.
assign cr[1]=cv[1];
reg prep_valid=0;
always @(posedge clk) begin
 if(rst) prep_valid<=0;
 else if(cv[1] && cr[1]) prep_valid<=1;
 else if(crr[1]) prep_valid<=0;
end
assign crv[1]=prep_valid;
assign cd[1]=32'hfacefeed;
task check(input [31:0] addr, input [31:0] expected);
begin
 @(negedge clk);host_addr=addr;valid=1;ready=0;
 do @(posedge clk); while(!arready);
 @(negedge clk);valid=0;host_addr=32'h20000100;
 wait(rvalid); #1;
 repeat(3) begin
  if(rdata !== {96'd0,expected} || !rlast || !rvalid)
   $fatal(1,"host address %h returned %h expected %h",addr,rdata,expected);
  @(negedge clk);
 end
 ready=1;repeat(3)@(negedge clk);
end endtask
integer cam;
initial begin
 repeat(4)@(negedge clk);rst=0;
 for(cam=0;cam<3;cam=cam+1) begin
  check(32'h20000190+cam*'h200,307200+cam);
  check(32'h200001a0+cam*'h200,1290240+cam);
  check(32'h200001b0+cam*'h200,7+cam);
  check(32'h200001c0+cam*'h200,123+cam);
  // Reproduce the old broken accesses: 04/08/0c alias ACK, 14 aliases PCLK.
  check(32'h20000004+cam*'h200,32'h80006123);
  check(32'h20000008+cam*'h200,32'h80006123);
  check(32'h2000000c+cam*'h200,32'h80006123);
  check(32'h20000014+cam*'h200,32'h12345678);
 end
'''
for page in [0x20000100,0x20000300]:
    for off in range(0,0x90,0x10):
        tb += f" check(32'h{page+off:08x},32'hfacefeed);\n"
tb += '''// Existing CAM3 SCCB reads remain accessible and reset to zero.
 check(32'h20000510,0);check(32'h20000520,0);
 $display("PASS HOST MAP three cameras, old alignment aliases, PREP/SCCB routing, R backpressure and zero extension");
 $finish;
end
initial begin #100000;$fatal(1,"timeout");end
endmodule
'''
(HERE/'tb_cdc_host_map.sv').write_bytes(tb.encode('ascii'))
for args, log, marker in [
    (['vlog.exe','-work','work_cdc','-sv',str(ROOT/'source/ov5640/axi_to_axi_lite.v'),str(ROOT/'source/ov5640/ovreg_axil_decode.v'),str(ROOT/'source/ov5640/ov5640_reg.v'),'tb_cdc_host_map.sv'],'compile_host_map.log',b'Errors: 0'),
    (['vsim.exe','-c','work_cdc.tb_cdc_host_map','-do','run -all; quit -force'],'host_map.log',b'PASS HOST MAP')]:
    p = subprocess.run([str(EXE/args[0]),*args[1:]], cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (HERE/log).write_bytes(p.stdout)
    assert p.returncode==0 and marker in p.stdout and b'** Fatal:' not in p.stdout and b'** Error:' not in p.stdout, p.stdout.decode(errors='replace')
    print('PASS',log)
