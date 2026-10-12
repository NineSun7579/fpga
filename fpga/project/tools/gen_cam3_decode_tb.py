from pathlib import Path

out = Path('sim/preprocess/tb_cam3_decode.sv')
signals = {'awvalid':1,'awready':1,'awaddr':32,'wvalid':1,'wready':1,'wdata':32,'wstrb':4,
           'bvalid':1,'bready':1,'bresp':2,'arvalid':1,'arready':1,'araddr':32,
           'rvalid':1,'rready':1,'rdata':32,'rresp':2}
text = '''`timescale 1ns/1ps
module tb_cam3_decode;
reg clk=0, rst=1;
always #5 clk=~clk;
reg awvalid=0,wvalid=0,bready=0,arvalid=0,rready=0;
reg [31:0] awaddr=0,wdata=0,araddr=0;
reg [3:0] wstrb=15;
wire awready,wready,bvalid,arready,rvalid;
wire [1:0] bresp,rresp;
wire [31:0] rdata;
'''
for name,width in signals.items():
    text += 'wire '+(f'[{width-1}:0] ' if width>1 else '')+f'm_{name} [0:3];\n'
ports = ['.clk(clk)', '.rst(rst)'] + [f'.s_{n}({n})' for n in signals]
ports += [f'.m{i}_{n}(m_{n}[{i}])' for i in range(4) for n in signals]
text += 'ovreg_axil_decode dut('+',\n'.join(ports)+');\n'
for i,base in enumerate([0x20000000,0x20000100,0x20000200,0x20000400]):
    ports=['.clk(clk)','.rst(rst)']+[f'.s_axi_{n}(m_{n}[{i}])' for n in signals]
    text += f"ov5640_reg #(.BASE_ADDR(32'h{base:08x})) slave{i}("+',\n'.join(ports)+');\n'
text += '''
task wr(input [31:0] a, input [31:0] v);
begin
 @(negedge clk); awaddr=a; wdata=v; awvalid=1; wvalid=1;
 @(posedge clk); while (!(awready && wready)) @(posedge clk);
 @(negedge clk); awvalid=0; wvalid=0;
 wait(bvalid===1); repeat(3) @(negedge clk);
 if (!bvalid || bresp!==0) $fatal(1,"write response lost");
 bready=1; @(negedge clk); bready=0;
end endtask
task rd(input [31:0] a, input [31:0] expected);
begin
 @(negedge clk); araddr=a; arvalid=1;
 @(posedge clk); while(!arready) @(posedge clk);
 @(negedge clk); arvalid=0;
 wait(rvalid===1); repeat(3) @(negedge clk);
 if (!rvalid || rresp!==0 || rdata!==expected)
   $fatal(1,"READ addr=%h got=%h expected=%h",a,rdata,expected);
 rready=1; @(negedge clk); rready=0;
end endtask
initial begin
 repeat(5) @(negedge clk); rst=0;
 rd(32'h20000040,1); rd(32'h20000240,1); rd(32'h20000440,1);
 wr(32'h20000080,32'h00800000);
 wr(32'h20000280,32'h00c00000);
 wr(32'h20000480,32'h01000000);
 wr(32'h20000180,32'h00f00000);
 rd(32'h20000480,32'h01000000);
 rd(32'h20000280,32'h00c00000);
 rd(32'h20000080,32'h00800000);
 rd(32'h20000180,32'h00f00000);
 wr(32'h20000440,0); rd(32'h20000440,0);
 rd(32'h20000040,1); rd(32'h20000240,1);
 wr(32'h20000440,1); rd(32'h20000440,1);
 $display("CAM3_DECODE_PASS: four windows, isolated registers, stalled B/R");
 $finish;
end
initial begin #20000; $fatal(1,"TIMEOUT"); end
endmodule
'''
out.write_bytes(text.encode('ascii'))
print(out)
