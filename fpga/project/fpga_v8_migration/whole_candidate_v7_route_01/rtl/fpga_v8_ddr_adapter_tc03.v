`timescale 1ns/1ps
// Isolated tc03 candidate; no additional state or handshake latency.
// Common reset of adapter, upstream fabric and vendor controller is required.
module fpga_v8_ddr_adapter_tc03 #(
    parameter [31:0] DDR_ADDRESS_LIMIT = 32'h10000000
) (
    input wire clk, input wire rst_n,
    input wire [3:0] s_awid,
    input wire [31:0] s_awaddr,
    input wire [7:0] s_awlen,
    input wire [2:0] s_awsize,
    input wire [1:0] s_awburst,
    input wire s_awvalid, output wire s_awready,
    input wire [127:0] s_wdata, input wire [15:0] s_wstrb,
    input wire s_wlast, input wire s_wvalid, output wire s_wready,
    output reg [3:0] s_bid, output reg [1:0] s_bresp,
    output reg s_bvalid, input wire s_bready,
    input wire [6:0] s_arid,
    input wire [31:0] s_araddr,
    input wire [7:0] s_arlen,
    input wire [2:0] s_arsize,
    input wire [1:0] s_arburst,
    input wire s_arvalid, output wire s_arready,
    output wire [6:0] s_rid, output wire [127:0] s_rdata,
    output wire [1:0] s_rresp, output wire s_rlast,
    output wire s_rvalid, input wire s_rready,
    output wire [3:0] v_awid, output wire [27:0] v_awaddr,
    output wire [3:0] v_awlen, output reg v_awvalid, input wire v_awready,
    output wire [127:0] v_wdata, output wire [15:0] v_wstrb,
    input wire v_wready, input wire v_wlast, input wire [3:0] v_wid,
    output wire [3:0] v_arid, output wire [27:0] v_araddr,
    output wire [3:0] v_arlen, output reg v_arvalid, input wire v_arready,
    input wire [3:0] v_rid, input wire [127:0] v_rdata,
    input wire v_rlast, input wire v_rvalid,
    output reg [7:0] error_flags,
    output wire [4:0] write_water_level,
    output wire write_fifo_full, output wire write_fifo_empty,
    output wire read_fifo_full, output wire read_fifo_empty,
    output wire write_busy, output wire read_busy
);
    wire fifo_rst = !rst_n;
    reg write_active, write_hold, vendor_write_active;
    reg [3:0] aw_id, aw_len;
    reg [27:0] aw_addr;
    reg [8:0] accepted_w, consumed_w;
    reg write_failed;
    reg read_active, vendor_read_active;
    reg [6:0] ar_id;
    reg [3:0] ar_len;
    reg [27:0] ar_addr;
    reg [8:0] received_r, retired_r;
    wire [3:0] fifo_rid;
    // For a 16-byte aligned start, last beat index <= 255 is exactly
    // offset + (LEN+1)*16 <= 4096. Extend BOTH operands: max sum is 510.
    wire [8:0] aw_last_page_beat = {1'b0,s_awaddr[11:4]} + {1'b0,s_awlen};
    wire [8:0] ar_last_page_beat = {1'b0,s_araddr[11:4]} + {1'b0,s_arlen};
    wire aw_limit_ok, ar_limit_ok;
    wire limit_ok = DDR_ADDRESS_LIMIT!=0 && DDR_ADDRESS_LIMIT<=32'h10000000 && DDR_ADDRESS_LIMIT[3:0]==0;
    generate
        if (DDR_ADDRESS_LIMIT[11:0]==0) begin : page_aligned_limit
            // Together with the page check and alignment, a burst cannot
            // pass a page-aligned limit when its start is strictly below it.
            // Keep the original 32-bit parameter and full 32-bit addresses;
            // no truncating address arithmetic is used on this branch.
            assign aw_limit_ok = s_awaddr < DDR_ADDRESS_LIMIT;
            assign ar_limit_ok = s_araddr < DDR_ADDRESS_LIMIT;
        end else begin : general_limit
            // Preserve the original overflow-safe expression for other limits.
            wire [63:0] aw_end = {32'd0,s_awaddr} + ({56'd0,s_awlen}+64'd1)*64'd16;
            wire [63:0] ar_end = {32'd0,s_araddr} + ({56'd0,s_arlen}+64'd1)*64'd16;
            assign aw_limit_ok = aw_end <= {32'd0,DDR_ADDRESS_LIMIT};
            assign ar_limit_ok = ar_end <= {32'd0,DDR_ADDRESS_LIMIT};
        end
    endgenerate
    wire aw_ok = limit_ok && s_awlen<=15 && s_awaddr[3:0]==0 && s_awsize==4 && s_awburst==1 &&
                 aw_last_page_beat<=9'd255 && aw_limit_ok;
    wire ar_ok = limit_ok && s_arlen<=15 && s_araddr[3:0]==0 && s_arsize==4 && s_arburst==1 &&
                 ar_last_page_beat<=9'd255 && ar_limit_ok;
    assign s_awready = rst_n && !write_active && !write_hold && !v_awvalid && !s_bvalid && write_fifo_empty && aw_ok;
    assign s_wready = rst_n && write_active && !write_fifo_full && accepted_w<({5'd0,aw_len}+9'd1);
    wire push_w = s_wvalid && s_wready;
    wire pop_w = rst_n && v_wready && vendor_write_active && !write_fifo_empty;
    assign write_busy = write_active;
    assign v_awid=aw_id;
    assign v_awaddr=aw_addr;
    assign v_awlen=aw_len;
    ddr_fifo16_w write_fifo (
        .clk(clk), .rst(fifo_rst), .wr_data({s_wstrb,s_wdata}), .wr_en(push_w),
        .wr_water_level(write_water_level), .full(write_fifo_full), .almost_full(),
        .rd_data({v_wstrb,v_wdata}), .rd_en(pop_w), .empty(write_fifo_empty), .almost_empty()
    );
    // Retain the full route ID until the downstream last R is consumed.
    assign s_arready = rst_n && !read_active && !v_arvalid && read_fifo_empty && ar_ok;
    assign v_arid=ar_id[3:0];
    assign v_araddr=ar_addr;
    assign v_arlen=ar_len;
    assign read_busy=read_active;
    assign s_rid={ar_id[6:4],fifo_rid};
    // The vendor interface has no RRESP. Protocol diagnostics remain sticky;
    // do not change a queued/stalled response based on a later vendor beat.
    assign s_rresp=2'b00;
    assign s_rvalid=rst_n && !read_fifo_empty;
    wire push_r=rst_n && v_rvalid && vendor_read_active && !read_fifo_full;
    ddr_fifo16_r read_fifo (
        .clk(clk), .rst(fifo_rst), .wr_data({v_rid,v_rlast,v_rdata}), .wr_en(push_r),
        .full(read_fifo_full), .almost_full(), .rd_data({fifo_rid,s_rlast,s_rdata}),
        .rd_en(s_rvalid && s_rready), .empty(read_fifo_empty), .almost_empty()
    );
    always @(posedge clk) begin
        if(!rst_n) begin
            write_active<=0; write_hold<=0; vendor_write_active<=0;
            aw_id<=0; aw_len<=0; aw_addr<=0; accepted_w<=0; consumed_w<=0;
            write_failed<=0; s_bvalid<=0; s_bresp<=0; s_bid<=0; v_awvalid<=0;
            read_active<=0; vendor_read_active<=0; ar_id<=0; ar_len<=0; ar_addr<=0;
            received_r<=0; retired_r<=0; v_arvalid<=0; error_flags<=0;
        end else begin
            // Unsupported requests are flagged and remain unaccepted; no LEN/address truncation.
            if(s_awvalid && !aw_ok) error_flags[0]<=1;
            if(s_arvalid && !ar_ok) error_flags[1]<=1;
            if(s_awvalid && s_awready) begin
                write_active<=1; write_hold<=1; aw_id<=s_awid;
                aw_len<=s_awlen[3:0]; aw_addr<=s_awaddr[27:0];
                accepted_w<=0; consumed_w<=0; write_failed<=0;
            end
            if(push_w) begin
                accepted_w<=accepted_w+1;
                if(s_wlast != (accepted_w=={5'd0,aw_len})) begin
                    error_flags[2]<=1; write_failed<=1;
                end
            end
            if(write_hold && !v_awvalid && !write_fifo_empty &&
                write_water_level>=({1'b0,aw_len}+5'd1)) begin
                v_awvalid<=1; write_hold<=0;
            end
            if(v_awvalid && v_awready) begin v_awvalid<=0; vendor_write_active<=1; end
            if(v_wready && (!vendor_write_active || write_fifo_empty)) error_flags[3]<=1;
            if(pop_w) begin
                consumed_w<=consumed_w+1;
                if(v_wlast != (consumed_w=={5'd0,aw_len}) || v_wid!=aw_id) begin
                    error_flags[4]<=1; write_failed<=1;
                end
                // The vendor's last-consumed indication, not upstream WLAST, mints B.
                if(v_wlast) begin
                    vendor_write_active<=0; s_bvalid<=1; s_bid<=aw_id;
                    s_bresp<=(write_failed || consumed_w!={5'd0,aw_len} || v_wid!=aw_id)?2'b10:2'b00;
                end
            end
            if(s_bvalid && s_bready) begin s_bvalid<=0; write_active<=0; end
            if(s_arvalid && s_arready) begin
                read_active<=1; v_arvalid<=1; ar_id<=s_arid;
                ar_addr<=s_araddr[27:0]; ar_len<=s_arlen[3:0];
                received_r<=0; retired_r<=0;
            end
            if(v_arvalid && v_arready) begin v_arvalid<=0; vendor_read_active<=1; end
            if(v_rvalid && (!vendor_read_active || read_fifo_full)) error_flags[5]<=1;
            if(push_r) begin
                received_r<=received_r+1;
                if(v_rid!=ar_id[3:0] || v_rlast!=(received_r=={5'd0,ar_len})) begin
                    error_flags[6]<=1;
                end
                if(v_rlast) vendor_read_active<=0;
            end
            if(s_rvalid && s_rready) begin
                retired_r<=retired_r+1;
                if(s_rlast) begin
                    read_active<=0;
                    if(retired_r!={5'd0,ar_len}) error_flags[7]<=1;
                end
            end
        end
    end
endmodule
