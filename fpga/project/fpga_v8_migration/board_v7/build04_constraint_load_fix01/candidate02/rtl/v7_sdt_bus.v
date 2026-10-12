// ADS guide printed pp52,83-84,91-93,103-104; Pango attribute reference p88.
// Isolated mapping candidate: stage count, reset polarity and all enables unchanged.
// Isolated AXI-Lite interceptor, inserted AFTER axi_to_axi_lite and BEFORE
// ovreg_axil_decode_tc01. One outstanding read and one write, independently.
module v7_sdt_bus (
 input clk, rst,
 input [3:0] cam_clk, cam_reset, raw_vsync, raw_href, raw_byte_accept,
 input [3:0] capture_vsync, capture_valid,
 input s_awvalid, output s_awready, input [31:0] s_awaddr,
 input s_wvalid, output s_wready, input [31:0] s_wdata, input [3:0] s_wstrb,
 output reg s_bvalid, input s_bready, output reg [1:0] s_bresp,
 input s_arvalid, output s_arready, input [31:0] s_araddr,
 output reg s_rvalid, input s_rready, output reg [31:0] s_rdata, output reg [1:0] s_rresp,
 output m_awvalid, input m_awready, output [31:0] m_awaddr,
 output m_wvalid, input m_wready, output [31:0] m_wdata, output [3:0] m_wstrb,
 input m_bvalid, output m_bready, input [1:0] m_bresp,
 output m_arvalid, input m_arready, output [31:0] m_araddr,
 input m_rvalid, output m_rready, input [31:0] m_rdata, input [1:0] m_rresp
);
 function hit(input [31:0] a);
  hit=(a[31:10]==22'h080004);
 endfunction
 reg ah, wh, wasent, wdsent;
 reg [31:0] wa, wd, ra;
 reg [3:0] ws;
 reg [2:0] rs;
 reg [1:0] wc, rc;
 reg [31:0] read_epoch;
 reg [3:0] acq, rel, rd;
 reg [4:0] word_sel;
 reg [3:0] index [0:3];
 wire [3:0] valid, available, overrun, rv, re;
 wire [31:0] data [0:3];
 wire [3:0] invalid;
 reg [31:0] epoch [0:3];
 reg [3:0] was_invalid;
 genvar g;
 generate for(g=0;g<4;g=g+1) begin: cameras
  // Async assertion captures even camera reset pulses shorter than clk.
  // Keep invalid high beyond the source's two-cycle host reset release.
  (* syn_keep=1 *) wire [3:0] reset_pipe;
    (* syn_keep=1 *) wire reset_pipe_d0 = 1'b0;
    (* syn_keep=1 *) wire reset_pipe_d1 = reset_pipe[0];
    (* syn_keep=1 *) wire reset_pipe_d2 = reset_pipe[1];
    (* syn_keep=1 *) wire reset_pipe_d3 = reset_pipe[2];
  (* syn_keep=1 *) wire reset_pipe_assert = rst | cam_reset[g];
    (* syn_noprune=1 *) GTP_DFF_PE #(.GRS_EN("TRUE"),.INIT(1'b1)) reset_pipe_ff0 (.Q(reset_pipe[0]),.D(reset_pipe_d0),.CLK(clk),.P(reset_pipe_assert),.CE(1'b1));
    (* syn_noprune=1 *) GTP_DFF_PE #(.GRS_EN("TRUE"),.INIT(1'b1)) reset_pipe_ff1 (.Q(reset_pipe[1]),.D(reset_pipe_d1),.CLK(clk),.P(reset_pipe_assert),.CE(1'b1));
    (* syn_noprune=1 *) GTP_DFF_PE #(.GRS_EN("TRUE"),.INIT(1'b1)) reset_pipe_ff2 (.Q(reset_pipe[2]),.D(reset_pipe_d2),.CLK(clk),.P(reset_pipe_assert),.CE(1'b1));
    (* syn_noprune=1 *) GTP_DFF_PE #(.GRS_EN("TRUE"),.INIT(1'b1)) reset_pipe_ff3 (.Q(reset_pipe[3]),.D(reset_pipe_d3),.CLK(clk),.P(reset_pipe_assert),.CE(1'b1));
  assign invalid[g]=reset_pipe[3] || (&epoch[g]);
  v7_sfd_candidate source (
   .cam_clk(cam_clk[g]),.cam_reset(cam_reset[g]),.host_clk(clk),.host_reset(rst),
   .raw_vsync(raw_vsync[g]),.raw_href(raw_href[g]),.raw_byte_accept(raw_byte_accept[g]),
   .capture_vsync(capture_vsync[g]),.capture_valid(capture_valid[g]),
   .read_strobe(rd[g]),.acquire_strobe(acq[g]),.release_strobe(rel[g]),
   .read_word(word_sel),.read_data(data[g]),.read_valid(rv[g]),.read_error(re[g]),
   .snapshot_valid(valid[g]),.snapshot_available(available[g]),.overrun(overrun[g]));
 end endgenerate
 assign s_awready=!rst && !ah && !s_bvalid;
 assign s_wready=!rst && !wh && !s_bvalid;
 assign s_arready=!rst && rs==0 && !s_rvalid;
 assign m_awaddr=wa;
 assign m_wdata=wd;
 assign m_wstrb=ws;
 // Offer AW and W together: frozen CAM requires simultaneous valid.
 // Decoder uses live AW route while AWVALID, saved route after AW handshake.
 assign m_awvalid=ah && wh && !hit(wa) && !wasent && !s_bvalid;
 assign m_wvalid=ah && wh && !hit(wa) && !wdsent && !s_bvalid;
 assign m_bready=ah && wh && !hit(wa) && wasent && wdsent && !s_bvalid;
 assign m_araddr=ra;
 assign m_arvalid=rs==1;
 assign m_rready=rs==2 && !s_rvalid;
 integer i;
 always @(posedge clk) begin
  if(rst) begin
   ah<=0; wh<=0; wasent<=0; wdsent<=0; s_bvalid<=0; s_bresp<=0;
   rs<=0; s_rvalid<=0; s_rdata<=0; s_rresp<=0;
   wa<=0; wd<=0; ws<=0; ra<=0; wc<=0; rc<=0; read_epoch<=0;
   acq<=0; rel<=0; rd<=0; word_sel<=0; was_invalid<=0;
   for(i=0;i<4;i=i+1) begin epoch[i]<=0; index[i]<=0; end
  end else begin
   acq<=0; rel<=0; rd<=0;
   for(i=0;i<4;i=i+1) begin
    was_invalid[i]<=invalid[i];
    if(invalid[i] && !was_invalid[i] && !(&epoch[i])) epoch[i]<=epoch[i]+1'b1;
   end
   if(s_bvalid && s_bready) begin s_bvalid<=0; ah<=0; wh<=0; wasent<=0; wdsent<=0; end
   if(s_rvalid && s_rready) s_rvalid<=0;
   if(s_awvalid && s_awready) begin ah<=1; wa<=s_awaddr; wc<=s_awaddr[9:8]; end
   if(s_wvalid && s_wready) begin wh<=1; wd<=s_wdata; ws<=s_wstrb; end
   if(m_awvalid && m_awready) wasent<=1;
   if(m_wvalid && m_wready) wdsent<=1;
   if(m_bvalid && m_bready) begin s_bvalid<=1; s_bresp<=m_bresp; end
   if(ah && wh && hit(wa) && !s_bvalid) begin
    s_bvalid<=1; s_bresp<=2'b10;
    if(ws==4'hf && !invalid[wc]) begin
     if(wa[7:0]==8'h20 && wd<16) begin index[wc]<=wd[3:0]; s_bresp<=0; end
     if(wa[7:0]==8'h10 && (wd==1 || wd==2)) begin
      if(wd==2) begin rel[wc]<=1; s_bresp<=0; end
      else if(valid[wc] || available[wc]) begin acq[wc]<=1; s_bresp<=0; end
     end
    end
   end
   if(s_arvalid && s_arready) begin
    ra<=s_araddr; rc<=s_araddr[9:8]; read_epoch<=epoch[s_araddr[9:8]];
    if(!hit(s_araddr)) rs<=1;
    else begin
     rs<=3; word_sel<={1'b0,index[s_araddr[9:8]]};
     if(s_araddr[7:0]==8'h30) rd[s_araddr[9:8]]<=1;
    end
   end
   if(m_arvalid && m_arready) rs<=2;
   if(m_rvalid && m_rready) begin rs<=0; s_rvalid<=1; s_rdata<=m_rdata; s_rresp<=m_rresp; end
   // Source strobe executes in state 3; its registered response is sampled
   // in state 4. Reset can erase it: always complete with SLVERR in that case.
   if(rs==3) rs<=4;
   if(rs==4) begin
    rs<=0; s_rvalid<=1; s_rdata<=0; s_rresp<=2'b10;
    case(ra[7:0])
     8'h00: begin s_rdata<={28'b0,invalid[rc],available[rc],overrun[rc],valid[rc] && !invalid[rc]}; s_rresp<=0; end
     8'h20: begin s_rdata<={28'b0,index[rc]}; s_rresp<=0; end
     8'h40: begin s_rdata<=epoch[rc]; s_rresp<=0; end
     8'h30: if(rv[rc] && !re[rc] && !invalid[rc] && epoch[rc]==read_epoch) begin s_rdata<=data[rc]; s_rresp<=0; end
     default: begin end
    endcase
   end
  end
 end
endmodule
