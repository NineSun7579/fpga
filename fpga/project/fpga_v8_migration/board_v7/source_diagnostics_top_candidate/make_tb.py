from generate import P,F,B,replace
import re
bus=(B/'tb.sv').read_bytes()
tasks=bus[bus.index(b'integer checks='):bus.index(b'task marker;')]
tasks=replace(tasks,b'begin ar(a);take_r(v,expected);end',b'begin $display("READ addr=%h expected=%h",a,expected); ar(a);take_r(v,expected);end')
# Real crossbar legally withholds WREADY until it has an AW route. Offer W
# first, but do not wait for its handshake before offering AW.
tasks=replace(tasks,b'else if(order==1) begin w(v,strb);repeat(3) @(negedge clk);aw(a);end',b'else if(order==1) fork w(v,strb);begin repeat(3) @(negedge clk);aw(a);end join')
monitor=bus[bus.index(b'reg stalled_r='):bus.rindex(b'endmodule')]
decl=bus[bus.index(b'reg u_awvalid'):bus.index(b'`include')]
lines=['`timescale 1ns/1ps','module tb_sdt;', 'reg clk=0,camclk=0,rst=1,ctrlclk=0; always #5 clk=~clk; always #7 camclk=~camclk; always #20 ctrlclk=~ctrlclk;', 'reg [3:0] rawvs=0,href=0,camrun=0;',decl.decode()]
con=[".free_clk(1'b0)",".button_rst_n(1'b1)",".perst_n(1'b0)",".ref_clk_p(1'b0)",".ref_clk_n(1'b1)",".rxn(2'b0)",".rxp(2'b0)",".sfp_l2rxn(1'b0)",".sfp_l2rxp(1'b0)"]
for i in range(4): con += [f'.cmos{i+1}_pclk(camclk)',f'.cmos{i+1}_vsync(rawvs[{i}])',f'.cmos{i+1}_href(href[{i}])',f".cmos{i+1}_data(8'h55)"]
lines += ["GTP_GRS GRS_INST (.GRS_N(1'b1));",'v7_sdt_top dut('+','.join(con)+');','initial begin force dut.axi_clk=clk; force dut.ddr_init_done=!rst; force dut.clk_50m=ctrlclk;']
for n in ['awvalid','awaddr','wvalid','bready','arvalid','araddr','rready']:
    lines += ['force dut.pcie_axi_'+n+'=u_'+n+';']
for n,v in [('wdata','dma_wdata'),('wstrb','dma_wstrb'),('wlast',"1'b1")]: lines += ['force dut.pcie_axi_'+n+'='+v+';']
for ch in ['aw','ar']:
    for n in ['id','len','size','burst','lock','cache','prot','qos']:
        lines += [f'force dut.pcie_axi_{ch}{n}={4 if n=="size" else 1 if n=="burst" else 0};']
for i,inst in enumerate(['ov5640_top','cam2_ov5640_top','cam3_ov5640_top','cam4_ov5640_top']):
    lines += [f'force dut.{inst}.ov5640.cam_init_done=camrun[{i}];',f'force dut.{inst}.ov5640.i2c_start_en=camrun[{i}];']
lines += ['end']
for n in ['awready','wready','bvalid','bresp','arready','rvalid','rresp']: lines += ['assign u_'+n+'=dut.pcie_axi_'+n+';']
lines += ['assign dma_rdata=dut.pcie_axi_rdata;',tasks.decode(),monitor.decode(),'`include "scenario.vh"','endmodule']
(P/'tb_sdt.sv').write_text('\n'.join(lines))
print('TB uses actual top, bus injected at PCIe DMA AXI output; I2C completion only is modeled')
