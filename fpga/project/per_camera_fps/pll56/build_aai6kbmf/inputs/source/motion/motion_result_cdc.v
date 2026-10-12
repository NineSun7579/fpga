`timescale 1ns/1ps
// One-entry bundled-data mailbox. src_valid is a one-src-clock pulse.
// A request is accepted only when src_busy is low BEFORE the rising edge.
// Busy requests are discarded; src_dropped_count wraps modulo 2^32.
// Both resets must be asserted together (including when aborting a transfer).
// Reset assertion is asynchronous; deassert each reset synchronously to its
// local clock in the integrating design. Independent domain reset is unsupported.
//
// PHYSICAL CDC CONTRACT (integration must supply constraints):
// - Preserve/place the two-flop req_sync and ack_sync chains as synchronizers.
//   ASYNC_REG uses standard Verilog attributes; verify PDS honors them.
// - Only req_toggle -> req_sync[0] and ack_toggle -> ack_sync[0] are
//   asynchronous control paths; keep each synchronizer's internal path timed.
// - held_data -> dst_data is intentionally an unsynchronized bundled bus.
//   Apply an explicit datapath-only max delay to EVERY bit, conservatively
//   <= one minimum dst_clk period minus setup/uncertainty margin. Do not let
//   blanket asynchronous-clock false paths override that max-delay constraint.
//   held_data stays immutable until the captured acknowledgement returns.
//   The extra settle edge gives timing margin; simulation cannot prove physical
//   metastability resolution or bus routing/setup compliance.
//
// No-metastability latency: capture/valid occurs on the fourth dst rising edge
// after acceptance (2 sync edges, detection edge, settle/capture edge), i.e.
// approximately 3..4 dst periods depending on phase. Metastability may add time.
// Busy clears after two src edges following capture/ack; acceptance is possible
// on the next src edge. dst_data holds its last value between dst_valid pulses.
module motion_result_cdc #(
    parameter WIDTH = 320
) (
    input  wire                 src_clk,
    input  wire                 src_rst,
    input  wire                 src_valid,
    input  wire [WIDTH-1:0]     src_data,
    output wire                 src_busy,
    output reg  [31:0]          src_dropped_count,
    input  wire                 dst_clk,
    input  wire                 dst_rst,
    output reg                  dst_valid,
    output reg  [WIDTH-1:0]     dst_data
);
    reg [WIDTH-1:0] held_data;
    reg req_toggle;
    reg ack_toggle;
    (* ASYNC_REG = "TRUE" *) reg [1:0] ack_sync;
    (* ASYNC_REG = "TRUE" *) reg [1:0] req_sync;
    reg capture_pending;
    reg pending_toggle;

    assign src_busy = req_toggle ^ ack_sync[1];

    always @(posedge src_clk or posedge src_rst) begin
        if (src_rst) begin
            ack_sync <= 2'b00;
            held_data <= {WIDTH{1'b0}};
            req_toggle <= 1'b0;
            src_dropped_count <= 32'b0;
        end else begin
            ack_sync <= {ack_sync[0], ack_toggle};
            if (src_valid) begin
                if (src_busy)
                    src_dropped_count <= src_dropped_count + 32'd1;
                else begin
                    held_data <= src_data;
                    req_toggle <= ~req_toggle;
                end
            end
        end
    end

    always @(posedge dst_clk or posedge dst_rst) begin
        if (dst_rst) begin
            req_sync <= 2'b00;
            ack_toggle <= 1'b0;
            capture_pending <= 1'b0;
            pending_toggle <= 1'b0;
            dst_valid <= 1'b0;
            dst_data <= {WIDTH{1'b0}};
        end else begin
            req_sync <= {req_sync[0], req_toggle};
            dst_valid <= 1'b0;
            if (capture_pending) begin
                dst_data <= held_data;
                dst_valid <= 1'b1;
                ack_toggle <= pending_toggle;
                capture_pending <= 1'b0;
            end else if (req_sync[1] != ack_toggle) begin
                pending_toggle <= req_sync[1];
                capture_pending <= 1'b1;
            end
        end
    end
endmodule
