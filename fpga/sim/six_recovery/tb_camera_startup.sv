`timescale 1ns/1ps
module tb_camera_startup;
  // The included declarations/always block are extracted byte-for-byte from top.v.
  reg clk_50m = 0;
  always #20 clk_50m = ~clk_50m;
  `include "top_startup_block.vh"
  integer edges = 0;
  wire [3:0] finished;
  always @(posedge clk_50m) begin
    edges = edges + 1;
    #1;
    if (edges < 65536 && camera_ctrl_rst_n !== 1'b0)
      $fatal(1, "startup reset released early at edge %0d", edges);
    if (edges >= 65536 && camera_ctrl_rst_n !== 1'b1)
      $fatal(1, "startup reset failed to release at edge %0d", edges);
    if (edges >= 65536 && camera_startup_count !== 16'hffff)
      $fatal(1, "startup counter did not saturate");
  end
  genvar c;
  generate for (c=0; c<4; c=c+1) begin: cameras
    six_camera_init_check #(.CAMERA(c+1)) check_camera(
      .clk(clk_50m), .rst_n(camera_ctrl_rst_n), .finished(finished[c]));
  end endgenerate
  initial begin
    #1;
    if (camera_ctrl_rst_n !== 0 || camera_startup_count !== 0)
      $fatal(1, "missing FPGA power-up initialization");
    wait (&finished);
    repeat (1000) @(posedge clk_50m);
    $display("PASS CAMERA STARTUP external_resets=0 release_edge=65536 cameras=4 commands_each=264");
    $finish;
  end
  initial begin #100000000; $fatal(1, "real camera initialization timeout"); end
endmodule

module six_camera_init_check #(parameter CAMERA=1)(
  input clk, input rst_n, output reg finished=0);
  wire scl, ov_rst_n, cam_rst_n;
  tri1 sda;
  wire [31:0] status;
  // Keep the production clock frequency, delays, sequencer and master intact.
  ov5640 #(.H_CMOS_DISP(640), .V_CMOS_DISP(480),
    .TOTAL_H_PIXEL(1896), .TOTAL_V_PIXEL(984)) dut(
    .clk_50m(clk), .rst_n(rst_n), .ov_rst_n(ov_rst_n),
    .cam_pclk(clk), .cam_vsync(1'b0), .cam_href(1'b0), .cam_data(8'd0),
    .cam_rst_n(cam_rst_n), .cam_pwdn(), .cam_scl(scl), .cam_sda(sda),
    .video_clk(clk), .video_rst(1'b0), .video_vsync(), .video_hsync(),
    .video_valid(), .video_data(), .dbg_i2c_status(status),
    .pt_req_toggle(1'b0), .pt_rw(1'b0), .pt_addr(16'd0), .pt_wdata(8'd0),
    .pt_rdata(), .pt_ack(), .pt_done_toggle());
  // SCCB slave: ACK released cycles and provide the two sensor ID reads.
  // Only the slave pins are driven; no internal register is forced or deposited.
  wire [7:0] read_byte = dut.i2c_dri.addr_t == 16'h300a ? 8'h56 : 8'h40;
  wire slave_bit = dut.i2c_dri.cur_state == 8'h40 && dut.i2c_dri.cnt < 32
    ? read_byte[7-(dut.i2c_dri.cnt >> 2)] : 1'b0;
  assign sda = !dut.i2c_dri.sda_dir ? slave_bit : 1'bz;
  integer started=0, completed=0, read_ops=0, scl_edges=0;
  reg done_prev=0;
  reg [23:0] tail [0:7];
  initial begin
    tail[0]=24'h3b070a; tail[1]=24'h503d00; tail[2]=24'h301602;
    tail[3]=24'h301c02; tail[4]=24'h301902; tail[5]=24'h300802;
    tail[6]=24'h300802; tail[7]=24'h301900;
  end
  always @(posedge scl) if (rst_n) scl_edges=scl_edges+1;
  always @(posedge dut.dri_clk) begin
    if (rst_n) begin
      if (dut.i2c_exec) begin
        if (finished || started >= 264) $fatal(1, "extra initialization command");
        if (dut.i2c_dri.cur_state !== 8'h01) $fatal(1, "command while master busy");
        if (!cam_rst_n) $fatal(1, "SCCB command before sensor reset release");
        if (started < 2) begin
          if (!dut.i2c_rh_wl || dut.i2c_data[23:8] !== (started==0 ? 16'h300a : 16'h300b))
            $fatal(1, "sensor ID read sequence mismatch");
          read_ops=read_ops+1;
        end else if (dut.i2c_rh_wl) $fatal(1, "unexpected register read");
        if (started >= 256 && dut.i2c_data !== tail[started-256])
          $fatal(1, "9-bit table tail mismatch command=%0d data=%h", started, dut.i2c_data);
        started=started+1;
      end
      if (dut.i2c_done && !done_prev) begin
        if (dut.i2c_ack !== 0) $fatal(1, "slave ACK failed");
        completed=completed+1;
        if (completed > started) $fatal(1, "completion without command");
      end
      done_prev=dut.i2c_done;
    end
  end
  initial begin
    wait (ov_rst_n === 1'b1);
    repeat (4) @(negedge dut.dri_clk);
    if (started != 264 || completed != 264 || read_ops != 2 ||
        dut.ov5640_i2c_rgb565_cfg.init_reg_cnt !== 264 || status !== 32'h00005640 || scl_edges < 9000)
      $fatal(1, "camera %0d incomplete started=%0d completed=%0d status=%h scl_edges=%0d",
        CAMERA, started, completed, status, scl_edges);
    $display("PASS real camera %0d started=%0d completed=%0d ID=%h SCL_edges=%0d",
      CAMERA, started, completed, status[15:0], scl_edges);
    finished=1;
  end
endmodule
