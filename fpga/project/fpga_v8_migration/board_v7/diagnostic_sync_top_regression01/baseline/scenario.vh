task tick(input [3:0] hh,input [3:0] vv,input integer n);
 repeat(n) begin @(negedge camclk);#1;href=hh;rawvs=vv;end
endtask
task marker;
 begin tick(0,15,80);tick(0,0,80);end
endtask
task reset_cam(input [3:0] mask);
 begin #2;camrun=15^mask;#2;camrun=15;repeat(12) @(negedge clk);end
endtask
integer c,j,row,deficit; reg [31:0] base,expected,words[0:3][0:15];
reg [3:0] split;
integer m01_reads=0,m01_writes=0,legacy_reads=0;
integer r_age=0,w_age=0;reg r_pending=0,w_pending=0;
always @(posedge clk) begin
 if(rst) begin r_pending<=0;w_pending<=0;r_age<=0;w_age<=0;end
 else begin
  if(u_arvalid) r_pending<=1;
  if(u_rvalid && u_rready) r_pending<=0;
  if(u_awvalid || u_wvalid) w_pending<=1;
  if(u_bvalid && u_bready) w_pending<=0;
   r_age<=r_pending?r_age+1:0;w_age<=w_pending?w_age+1:0;
   if(w_age==999) $display("B_DEBUG adapter=%b/%b bridge=%b/%b id=%h coop=%b/%b id=%h",dut.source_diagnostics.s_bvalid,dut.source_diagnostics.s_bready,dut.ovreg_axi_bvalid,dut.ovreg_axi_bready,dut.ovreg_axi_bid,dut.npu_reg_axi_bvalid,dut.npu_reg_axi_bready,dut.npu_reg_axi_bid);
  if(r_age>1000 || w_age>1000) $fatal(1,"FAIL timeout r/w=%d/%d ar=%h aw=%h M01=%b%b bus ah/wh=%b%b sent=%b%b wa=%h legacy AW=%b%b W=%b%b B=%b%b upstreamB=%b%b",r_age,w_age,dut.pcie_axi_araddr,dut.pcie_axi_awaddr,dut.ovreg_axi_arvalid,dut.ovreg_axi_arready,dut.source_diagnostics.ah,dut.source_diagnostics.wh,dut.source_diagnostics.wasent,dut.source_diagnostics.wdsent,dut.source_diagnostics.wa,dut.diag_legacy_awvalid,dut.diag_legacy_awready,dut.diag_legacy_wvalid,dut.diag_legacy_wready,dut.diag_legacy_bvalid,dut.diag_legacy_bready,u_bvalid,u_bready);
 end
end
always @(posedge clk) if(!rst) begin
  if(dut.npu_reg_axi_arvalid && dut.npu_reg_axi_arready) $display("M02_AR addr=%h len=%h size=%h burst=%h",dut.npu_reg_axi_araddr,dut.npu_reg_axi_arlen,dut.npu_reg_axi_arsize,dut.npu_reg_axi_arburst);
 if(dut.ovreg_axi_arvalid && dut.ovreg_axi_arready) m01_reads++;
 if(dut.ovreg_axi_awvalid && dut.ovreg_axi_awready) m01_writes++;
 if(dut.diag_legacy_arvalid && dut.diag_legacy_arready) begin
  legacy_reads++;
  check(dut.diag_legacy_araddr[31:10]!=22'h080004,"new aperture never reaches legacy decoder");
 end
end
initial begin
 #100; @(negedge clk);rst=0;
 // Run the REAL startup counter, with no force of camera_ctrl reset.
 wait(dut.camera_ctrl_rst_n);camrun=15;repeat(20) @(negedge clk);
 $display("STARTUP_DONE t=%0t",$time);
 check(dut.camera_startup_count==65535,"real camera_ctrl startup contract");
 read_reg('h20001030,d,2);
 for(c=0;c<4;c++) begin
  read_reg('h20000040+c*512,d);check(d==1,"legacy CAM enable default");
  write_reg('h20000040+c*512,0);read_reg('h20000040+c*512,d);check(d==0,"legacy CAM write/read disable");
  write_reg('h20000040+c*512,1);read_reg('h20000040+c*512,d);check(d==1,"legacy CAM restore");
 end
 read_reg('h20000830,d);check(d=='h4d4f5431,"motion magic actual endpoint");
 read_reg('h20000100,d);
 read_reg('h40010000,d);check(d=='h434f4f50,"COOP magic actual endpoint M02");
  read_reg('h40010400,d);check(d=='h4341504c,"CAPL magic actual endpoint M02");
 $display("PASS actual top legacy CAM PREP motion COOP CAPL routing");
 repeat(11) marker();
 // Four concurrent complete 640x480 frames: 0/1/2/7 odd splits.
 for(row=0;row<480;row++) begin
  split={row<7,row<2,row<1,1'b0};
  tick(15,0,639);tick(15^split,0,1);tick(15,0,640);tick(split,0,1);
  if(row<479) tick(0,0,16);
 end
 tick(0,0,20);marker();repeat(20) @(negedge clk);
 for(c=0;c<4;c++) begin
  base='h20001000+c*256; deficit=c==3?7:c;
  read_reg(base,d);check(d[2],"four real bindings snapshot available");
  write_reg(base+'h10,1,c%3);
  for(j=0;j<16;j++) begin
   write_reg(base+'h20,j,j%3);read_reg(base+'h30,d);words[c][j]=d;
   case(j)
    0:expected=1; 1:expected=614400; 2:expected=480+deficit;
    3:expected=2*deficit; 4,5:expected=307200-deficit;
     7:expected='h00050000+21+(c>=2?64:0);
    15:expected='h53464401;
    default:expected=0;
   endcase
   check(d===expected,$sformatf("cam%0d field%0d actual=%h expected=%h",c+1,j,d,expected));
  end
  $display("PASS CAM%0d FULL640x480 bytes=%0d segments=%0d odd=%0d aligned=%0d native=%0d flags=%h",c+1,words[c][1],words[c][2],words[c][3],words[c][4],words[c][5],words[c][7]);
 end
 // More source frames while leases are held must not alter any of 64 words.
 tick(15,0,16);tick(0,0,8);marker();repeat(20) @(negedge clk);
 for(c=0;c<4;c++) begin
  base='h20001000+c*256;
  read_reg(base,d);check(d[1],"overrun visible all cameras");
  for(j=0;j<16;j++) begin
   write_reg(base+'h20,j);read_reg(base+'h30,d);check(d===words[c][j],"all64 lease words immutable");
  end
 end
 for(c=0;c<4;c++) write_reg('h20001010+c*256,2);
 repeat(20) @(negedge camclk);
 tick(15,0,20);tick(0,0,6);marker();repeat(20) @(negedge clk);
 for(c=0;c<4;c++) begin
  base='h20001000+c*256;write_reg(base+'h10,1);
  for(j=0;j<16;j++) begin
   write_reg(base+'h20,j);read_reg(base+'h30,d);
   case(j)
    0:expected=3;1:expected=20;2,13:expected=1;4,5:expected=10;
     7:expected='h00070006+(c>=2?64:0);8:expected=16;9,10:expected=8;15:expected='h53464401;
    default:expected=0;
   endcase
   check(d===expected,$sformatf("new lease cam%0d field%0d actual=%h expected=%h",c+1,j,d,expected));
  end
 end
 $display("PASS all64 new lease fields include immediately previous dropped frame");
 read_reg('h20001040,e0);write_reg('h20001020,15);
 ar('h20001030);wait(u_rvalid);#1;held=dma_rdata[31:0];reset_cam(1);
 check(u_rvalid && dma_rdata[31:0]==held && u_rresp==0,"camera reset keeps stalled AXI R");take_r(d);
 read_reg('h20001040,e1);check(e1==e0+1,"resetepoch increments once");read_reg('h20001030,d,2);
 check(dut.camera_ctrl_rst_n && !dut.axi_rst,"camera reset cannot clear camera_ctrl or AXI interface");
 read_reg('h20001130,d);check(d==words[1][15],"other camera lease intact");
 fork aw('h20001320);w(15);join
 wait(u_bvalid);reset_cam(8);check(u_bvalid,"camera reset keeps stalled B");b(0);
 // Reset after source adapter AR acceptance, before read result commitment.
 fork
  ar('h20001230);
  begin wait(dut.source_diagnostics.s_arvalid && dut.source_diagnostics.s_arready);@(posedge clk);#1;camrun=11;#2;camrun=15;end
 join
 take_r(d,2);
 for(c=0;c<4;c++) for(j=0;j<256;j++)
  if(j!=0 && j!='h20 && j!='h30 && j!='h40) read_reg('h20001000+c*256+j,d,2);
 read_reg('h20001400,d);read_reg('h20000ff0,d);read_reg('h30001030,d);
 check(m01_reads>1000 && m01_writes>100,"actual crossbar M01 traversed");
 ar('h20001040);wait(u_rvalid);@(negedge clk);rst=1;repeat(5) @(negedge clk);
 check(!u_rvalid && !u_bvalid,"whole AXI reset clears handshakes");
 check(dut.camera_ctrl_rst_n,"AXI reset does not restart camera_ctrl");rst=0;
 repeat(20) @(negedge clk);read_reg('h20001030,d,2);
 $display("SDT_ALL_PASS checks=%0d M01_reads=%0d M01_writes=%0d legacy_reads=%0d",checks,m01_reads,m01_writes,legacy_reads);
// Appended AFTER the unchanged original SDT_ALL_PASS 14540-check marker.
for(c=0;c<4;c++) begin
 base='h20001000+c*256;
 read_reg(base+'h40,e0);
 reset_cam(1<<c);
 read_reg(base+'h40,e1);check(e1==e0+1,"supplement four-camera epoch exactly once");
 read_reg(base+'h30,d,2);
 check(dut.camera_ctrl_rst_n && !dut.axi_rst,"supplement camera reset isolates startup and AXI");
 $display("TOP_RESET_CAM_PASS camera=%0d epoch_before=%h epoch_after=%h",c+1,e0,e1);
end
$display("TOP_FOUR_RESET_PASS checks=%0d",checks);

$finish;
end
initial begin #30000000;$fatal(1,"FAIL full top watchdog");end
