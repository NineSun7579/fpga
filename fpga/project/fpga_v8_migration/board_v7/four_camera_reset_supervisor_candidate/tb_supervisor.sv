`timescale 1ns/1ps
module tb_supervisor;
 reg clk=0,epoch=1,request=0,vr=1;
 always #5 clk=~clk;
 reg [3:0] cams=0,clock_enable=15,i2c=0,init=0,ov=0,sv=0,valid=0,cap=0,wa=0;
 always #3 if(clock_enable[0]) cams[0]=~cams[0];
 always #4 if(clock_enable[1]) cams[1]=~cams[1];
 always #6 if(clock_enable[2]) cams[2]=~cams[2];
 always #7 if(clock_enable[3]) cams[3]=~cams[3];
 wire fault,admit,cold;wire [3:0] bf,abort_all,started,outvalid;
 GTP_GRS GRS_INST(.GRS_N(1'b1));
 four_camera_supervised_boundary #(.STARTUP_LIMIT(400),.CLOCK_LIMIT(64)) dut(
  .video_clk(clk),.config_epoch_reset(epoch),.config_cold_request(request),.cam_clk(cams),
  .i2c_start_en(i2c),.cam_init_done(init),.ov_rst_n(ov),.video_reset(vr),
  .source_data(64'h123456789abcdef0),.source_valid(valid),.source_hsync(valid),.source_vsync(sv),
  .capture_abort_req(cap),.writer_abort(wa),.video_valid(outvalid),
  .boundary_fault(bf),.transport_abort(abort_all),.camera_session_fault(fault),
  .admission_enable(admit),.cold_system_reset(cold),.source_started(started));
 integer errors=0,which;
 task tick; @(negedge clk);endtask
 task check(input bit ok,input string msg);
  if(!ok) begin errors++;$display("FAIL supervisor case=%0d %s",which,msg);end
 endtask
 task fresh;
  epoch=1;request=0;vr=1;i2c=0;init=0;ov=0;valid=0;sv=0;cap=0;wa=0;clock_enable=((which==0 || which==2)?7:15);
  repeat(12)tick();epoch=0;request=1;repeat(12)tick();request=0;vr=0;
 endtask
 task ready_all;
  i2c=15;init=15;ov=15;repeat(45)tick();
  check(admit && !cold && !fault && started==15,"normal source init must admit without fault");
 endtask
 task locked;
  repeat(8)tick();check(fault && !admit && abort_all==15,"session must lock and broadcast");
  i2c=15;init=15;ov=15;vr=0;cap=0;wa=0;valid=0;sv=0;clock_enable=15;
  repeat(90)tick();check(fault && !admit && outvalid==0,"local recovery cannot unlock session");
 endtask
 initial begin
  for(which=0;which<19;which++) begin
   fresh();
   case(which)
    0: begin // normal staggered init plus late camera clock
     clock_enable[3]=0;i2c=15;init=7;ov=7;repeat(110)tick();
     check(!fault && cold && !admit && started==7,"late clock/init waits without false fault");
     init=15;ov=15;repeat(20)tick();check(!admit,"no source clock cannot start");
     clock_enable=15;repeat(50)tick();check(admit&&!fault&&bf==0,"late source clock completes startup");
    end
    1: begin i2c=15;init=7;ov=7;repeat(420)tick();locked();check(cold,"failed init must never release cold boundary");end
    2: begin clock_enable[3]=0;i2c=15;init=15;ov=15;repeat(420)tick();locked();end
    3: begin i2c=15;init=7;ov=7;repeat(50)tick();ov[0]=0;#0.2;ov[0]=1;locked();check(cold,"one started camera reset while another init pending");end
    4: begin ready_all();ov[2]=0;#0.2;ov[2]=1;locked();check(!cold,"fault must not regenerate cold authorization");end
    5: begin ready_all();i2c[1]=0;#0.2;i2c[1]=1;locked();end
    6: begin ready_all();vr=1;#0.2;vr=0;locked();check(!cold,"warm video/AXI reset is not cold reset");end
    7: begin ready_all();clock_enable[3]=0;repeat(85)tick();locked();end
    8: begin ready_all();request=1;#0.2;request=0;locked();check(!cold,"repeat auth must not clear CDC");end
    9: begin // short initial request: separate configuration epoch
     epoch=1;request=0;repeat(5)tick();epoch=0;#1;request=1;#0.2;request=0;
     repeat(10)tick();check(!dut.supervisor.authorization_used,"glitch cannot authorize");locked();
    end
    10: begin ready_all();ov=0;i2c=0;#0.2;ov=15;i2c=15;locked();check(bf==15,"four CDC faults remain sticky");end
    11: begin ready_all();cap=4;tick();cap=0;locked();end
    12: begin ready_all();wa=8;tick();wa=0;locked();end
    13: begin ready_all(); // real sustained producer overrun, no forced FIFO flags
     repeat(20)tick();sv[0]=1;repeat(15)tick();sv=0;repeat(15)tick();valid[0]=1;
     repeat(6500)tick();valid=0;check(bf[0],"natural CDC FIFO overrun must fault");locked();
    end
    14: begin // repeated authorization even before all sources initialize
     tick();request=1;#0.2;request=0;locked();check(cold,"repeat during startup cannot authorize");
    end
    15: begin // two edges before qualification finishes, including subcycle gap
     epoch=1;request=0;repeat(5)tick();epoch=0;#1;request=1;#1;request=0;#0.2;request=1;
     repeat(12)tick();check(!dut.supervisor.authorization_used,"unqualified repeat cannot authorize");locked();
    end
    16: begin // epoch cannot bless an already-high untrusted request
     epoch=1;request=1;repeat(5)tick();epoch=0;repeat(420)tick();
     check(!dut.supervisor.authorization_used,"must see post-epoch request edge");locked();
    end
    17: begin ready_all();init[0]=0;#0.2;init[0]=1;locked();end
    18: begin // normal opposite release order: video initializes last
     vr=1;i2c=15;init=15;ov=15;repeat(120)tick();
     check(cold && !admit && !fault && started==15,"video late must wait without startup fault");
     vr=0;repeat(40)tick();check(admit && !cold && !fault && bf==0,"video late clean startup");
    end
   endcase
   $display("SUPERVISOR case=%0d fault=%b boundary=%b started=%b cold=%b errors=%0d",which,fault,bf,started,cold,errors);
  end
  $display("SUPERVISOR_DONE errors=%0d",errors);$finish;
 end
 initial begin #300000;$display("FAIL supervisor timeout");$finish;end
endmodule
