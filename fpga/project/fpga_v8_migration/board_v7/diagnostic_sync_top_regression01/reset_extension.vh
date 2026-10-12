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
