`timescale 1ns/1ps
// Logical extraction of top.v:256-268,540-548,601-607,640-655.
// Retains the original vendor-last retirement gate and 133-bit generated FIFO.
module fpga_v8_top_read_route_snapshot (
    input wire clk, input wire rst_n,
    input wire [6:0] arid, input wire [31:0] araddr, input wire [7:0] arlen,
    input wire arvalid, output wire arready,
    output reg [3:0] vendor_arid, output reg [27:0] vendor_araddr,
    output reg [3:0] vendor_arlen, output reg vendor_arvalid, input wire vendor_arready,
    input wire [3:0] vendor_rid, input wire [127:0] vendor_rdata,
    input wire vendor_rlast, input wire vendor_rvalid,
    output wire [6:0] rid, output wire [127:0] rdata,
    output wire rlast, output wire rvalid, input wire rready,
    output wire full, output wire empty, output reg rd_inflight
);
    reg [2:0] ar_sid;
    wire latch_now=arvalid && !vendor_arvalid && empty && !rd_inflight;
    assign arready=latch_now;
    assign rvalid=!empty;
    assign rid[6:4]=ar_sid;
    ddr_fifo16_r fifo (
        .clk(clk), .rst(!rst_n), .wr_data({vendor_rid,vendor_rlast,vendor_rdata}),
        .wr_en(vendor_rvalid), .full(full), .almost_full(),
        .rd_data({rid[3:0],rlast,rdata}), .rd_en(rready), .empty(empty), .almost_empty()
    );
    always @(posedge clk) begin
        if(!rst_n) begin ar_sid<=0; rd_inflight<=0; vendor_arvalid<=0; end
        else begin
            if(latch_now) begin
                ar_sid<=arid[6:4]; rd_inflight<=1; vendor_arvalid<=1;
                vendor_arid<=arid[3:0]; vendor_araddr<=araddr[27:0]; vendor_arlen<=arlen[3:0];
            end else if(vendor_rvalid && vendor_rlast) rd_inflight<=0;
            if(!latch_now && vendor_arvalid && vendor_arready) vendor_arvalid<=0;
        end
    end
endmodule
