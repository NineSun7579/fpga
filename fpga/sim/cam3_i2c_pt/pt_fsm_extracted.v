module pt_fsm_under_test(
    input          dri_clk,
    input          rst_n,
    input          cam_init_done,
    input          cfg_exec,
    input  [23:0]  cfg_data,
    input          cfg_rh_wl,
    input          i2c_done,
    input          i2c_ack,
    input  [7:0]   i2c_data_r,
    input          pt_req_toggle,
    input          pt_rw,
    input  [15:0]  pt_addr,
    input  [7:0]   pt_wdata,
    output [7:0]   pt_rdata,
    output         pt_ack,
    output         pt_done_toggle,
    output         i2c_exec,
    output [23:0]  i2c_data,
    output         i2c_rh_wl
);

// [PT 2026-09-26] host SCCB passthrough FSM (dri_clk domain). After sensor
// init completes, a host command issues exactly one transaction on the shared
// master; cfg_* is the autonomous init table. Results are handed back with a
// done-toggle (data held stable; CDC to video_clk lives in ov5640_top).
reg         pt_req_s1, pt_req_s2, pt_req_s3;
always @(posedge dri_clk or negedge rst_n) begin
    if(!rst_n) {pt_req_s1, pt_req_s2, pt_req_s3} <= 3'b0;
    else       {pt_req_s1, pt_req_s2, pt_req_s3} <= {pt_req_toggle, pt_req_s1, pt_req_s2};
end
wire pt_req_pulse = pt_req_s2 ^ pt_req_s3;

reg  pt_pending;
reg  pt_busy;
wire pt_take = pt_pending & cam_init_done & ~pt_busy;
always @(posedge dri_clk or negedge rst_n) begin
    if(!rst_n)          pt_pending <= 1'b0;
    else if(pt_req_pulse) pt_pending <= 1'b1;
    else if(pt_take)      pt_pending <= 1'b0;
end
always @(posedge dri_clk or negedge rst_n) begin
    if(!rst_n)        pt_busy <= 1'b0;
    else if(pt_take)  pt_busy <= 1'b1;
    else if(i2c_done) pt_busy <= 1'b0;
end

assign i2c_exec  = cfg_exec | pt_take;
assign i2c_data  = pt_take ? {pt_addr, pt_wdata} : cfg_data;
assign i2c_rh_wl = pt_take ? pt_rw : cfg_rh_wl;

reg [7:0] pt_rdata_r;
reg       pt_ack_r;
reg       pt_done_toggle_r;
always @(posedge dri_clk or negedge rst_n) begin
    if(!rst_n) begin
        pt_rdata_r       <= 8'd0;
        pt_ack_r         <= 1'b0;
        pt_done_toggle_r <= 1'b0;
    end
    else if(i2c_done && pt_busy) begin
        pt_rdata_r       <= i2c_data_r;
        pt_ack_r         <= i2c_ack;
        pt_done_toggle_r <= ~pt_done_toggle_r;
    end
end
assign pt_rdata       = pt_rdata_r;
assign pt_ack         = pt_ack_r;
assign pt_done_toggle = pt_done_toggle_r;
endmodule
