module tb_boundary;
wire [11:0] done;
boundary_pair #(.ID(0),.BURST(8),.EXHAUST(1)) p0(done[0]);
boundary_pair #(.ID(1),.BURST(0)) p1(done[1]);
boundary_pair #(.ID(2),.BURST(1)) p2(done[2]);
boundary_pair #(.ID(3),.BURST(255)) p3(done[3]);
boundary_pair #(.ID(4),.BURST(-1),.EXPECT(0)) p4(done[4]);
boundary_pair #(.ID(5),.BURST(256),.EXPECT(0)) p5(done[5]);
boundary_pair #(.ID(6),.BURST(32'd8),.EXPECT(0)) p6(done[6]);
boundary_pair #(.ID(7),.BURST(8'd8),.EXPECT(0)) p7(done[7]);
boundary_pair #(.ID(8),.BURST(64'd8),.EXPECT(0)) p8(done[8]);
boundary_pair #(.ID(9),.WIDTH(64),.EXPECT(0)) p9(done[9]);
boundary_pair #(.ID(10),.WIDTH(256),.EXPECT(0)) p10(done[10]);
boundary_pair #(.ID(11),.WIDTH(128),.KEEP(8),.EXPECT(0)) p11(done[11]);
initial begin wait(&done);$display("BOUNDARY_ALL_PASS pairs=12");$finish;end
initial begin #2000000;$fatal(1,"boundary timeout");end
endmodule
