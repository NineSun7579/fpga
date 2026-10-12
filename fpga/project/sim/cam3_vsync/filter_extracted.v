module filter_under_test #(parameter VSYNC_STABLE_CYCLES=64)(
input cam_pclk, ov_rst_n, cam_vsync, output filtered);

// 0: combinational bypass. N>0: accept only N consecutive opposite samples.
// Both edges are delayed by N PCLK samples (64/84 MHz = 0.762 us).
// Raw diagnostics above intentionally remain upstream. HREF/data are untouched.
// Requires real VSYNC pulses and edge-to-active-video blanking to exceed N
// samples plus the existing capture latency. No timeout or synthetic frames.
wire capture_vsync;
generate
    if (VSYNC_STABLE_CYCLES == 0) begin : g_vsync_bypass
        assign capture_vsync = cam_vsync;
    end else begin : g_vsync_filter
        localparam COUNT_W = (VSYNC_STABLE_CYCLES <= 1) ? 1 :
                             $clog2(VSYNC_STABLE_CYCLES);
        reg [COUNT_W-1:0] stable_count;
        reg stable_vsync;
        assign capture_vsync = stable_vsync;
        always @(posedge cam_pclk or negedge ov_rst_n) begin
            if (!ov_rst_n) begin
                stable_count <= {COUNT_W{1'b0}};
                stable_vsync <= 1'b0;
            end else if (cam_vsync == stable_vsync) begin
                stable_count <= {COUNT_W{1'b0}};
            end else if (stable_count == VSYNC_STABLE_CYCLES - 1) begin
                stable_count <= {COUNT_W{1'b0}};
                stable_vsync <= cam_vsync;
            end else begin
                stable_count <= stable_count + 1'b1;
            end
        end
    end
endgenerate
assign filtered=capture_vsync;
endmodule
