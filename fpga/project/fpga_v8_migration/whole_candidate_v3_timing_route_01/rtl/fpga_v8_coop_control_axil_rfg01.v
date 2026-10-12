`timescale 1ns/1ps
// Isolated candidate, Verilog-2001. All ports use core_clk.
// A certified descriptor handshake transfers an EXISTING input lease.
// Common reset with the bridge/interconnect is mandatory. See README.md.
module fpga_v8_coop_control_axil_rfg01 #(
    parameter [31:0] OUTPUT_BANK0_ADDR = 32'h08000000,
    parameter [31:0] OUTPUT_BANK1_ADDR = 32'h08200000,
    parameter [31:0] OUTPUT_LENGTH = 32'd1228800,
    parameter [31:0] DEVICE_ID = 32'h434f4f50,
    parameter [31:0] VERSION = 32'h00010000
) (
    input wire core_clk,
    input wire rst_n,
    input wire input_valid,
    output wire input_ready,
    input wire input_raw_valid,
    input wire [31:0] input_src_addr,
    input wire [31:0] input_source_seq,
    input wire [31:0] input_generation,
    input wire [2:0] input_camera,
    input wire input_camera_bank,
    input wire [63:0] input_lease_token,
    output wire input_claim,
    output wire input_reject,

    output reg cmd_valid,
    input wire cmd_ready,
    output reg [31:0] cmd_src_addr,
    output reg [31:0] cmd_dst_addr,
    output reg [31:0] cmd_frame_id,
    input wire bridge_busy,
    input wire bridge_done,
    input wire bridge_error,
    input wire bridge_cmd_error,

    output reg src_release_valid,
    input wire src_release_ready,
    output reg [31:0] src_release_addr,
    output reg [31:0] src_release_seq,
    output reg [31:0] src_release_generation,
    output reg [2:0] src_release_camera,
    output reg src_release_camera_bank,
    output reg [63:0] src_release_token,
    output wire busy,
    output wire [1:0] bank0_state,
    output wire [1:0] bank1_state,

    input wire [31:0] s_axil_awaddr,
    input wire [2:0] s_axil_awprot,
    input wire s_axil_awvalid,
    output wire s_axil_awready,
    input wire [31:0] s_axil_wdata,
    input wire [3:0] s_axil_wstrb,
    input wire s_axil_wvalid,
    output wire s_axil_wready,
    output reg [1:0] s_axil_bresp,
    output reg s_axil_bvalid,
    input wire s_axil_bready,
    input wire [31:0] s_axil_araddr,
    input wire [2:0] s_axil_arprot,
    input wire s_axil_arvalid,
    output wire s_axil_arready,
    output reg [31:0] s_axil_rdata,
    output reg [1:0] s_axil_rresp,
    output reg s_axil_rvalid,
    input wire s_axil_rready,
    input wire session_fault
);
    localparam [1:0] FREE = 2'd0, WRITING = 2'd1,
                     READY = 2'd2, HOST_READING = 2'd3;
    localparam [1:0] OKAY = 2'b00, SLVERR = 2'b10;
    reg [1:0] bank_state [0:1];
    reg [31:0] bank_seq [0:1];
    reg [31:0] bank_gen [0:1];
    reg [31:0] bank_src [0:1];
    reg [2:0] bank_camera [0:1];
    reg bank_camera_bank [0:1];
    reg [63:0] bank_token [0:1];
    reg active, active_bank, issued, operation_failed, command_rejected;
    reg ready_older, host_valid, host_bank;
    reg [31:0] ack_bank, ack_seq, ack_gen;
    reg [31:0] rejected_ack_count, rejected_claim_count, rejected_raw_count;
    reg [31:0] bridge_failure_count, completed_count, released_count;
    reg [31:0] accepted_count, last_error;
    reg aw_held, w_held;
    reg [31:0] aw_addr, w_data;
    reg [3:0] w_strb;
    integer index;

    wire free_exists = (bank_state[0] == FREE) || (bank_state[1] == FREE);
    wire free_bank = (bank_state[0] != FREE);
    wire ready_exists = (bank_state[0] == READY) || (bank_state[1] == READY);
    wire oldest_bank = ((bank_state[0] == READY) && (bank_state[1] == READY)) ?
                       ready_older : (bank_state[1] == READY);
    wire cmd_fire = cmd_valid && cmd_ready;
    // bridge_cmd_error is the bridge's no-launch command rejection, not an
    // in-flight AXI error. A rejection may only retire once bridge_busy is low.
    wire rejected_idle = (command_rejected || bridge_cmd_error) && !bridge_busy;
    wire operation_finished = active && issued && (bridge_done || rejected_idle);
    wire operation_error = operation_failed || bridge_error ||
                           bridge_cmd_error || command_rejected;

    assign input_ready = rst_n && !active && !cmd_valid && !bridge_busy &&
                         !src_release_valid && free_exists;
    assign input_claim = input_valid && input_ready && input_raw_valid;
    assign input_reject = input_valid && input_ready && !input_raw_valid;
    assign busy = active;
    assign bank0_state = bank_state[0];
    assign bank1_state = bank_state[1];
    // One independent holding slot per write channel, one B outstanding.
    // Channels remain backpressured while B is pending; every accepted beat
    // is retained. B consumption permits the next captures on the next cycle.
    assign s_axil_awready = rst_n && !aw_held && !s_axil_bvalid;
    assign s_axil_wready = rst_n && !w_held && !s_axil_bvalid;
    assign s_axil_arready = rst_n && (!s_axil_rvalid || s_axil_rready);

    function [31:0] merge_bytes;
        input [31:0] original;
        input [31:0] replacement;
        input [3:0] strobes;
        integer byte_index;
        begin
            merge_bytes = original;
            for (byte_index = 0; byte_index < 4; byte_index = byte_index + 1)
                if (strobes[byte_index])
                    merge_bytes[byte_index*8 +: 8] = replacement[byte_index*8 +: 8];
        end
    endfunction

    function valid_read;
        input [31:0] addr;
        begin
            case (addr)
                32'h00, 32'h04, 32'h08, 32'h0c, 32'h10, 32'h14,
                32'h18, 32'h1c, 32'h20, 32'h24, 32'h28, 32'h2c,
                32'h30, 32'h34, 32'h38, 32'h40, 32'h44, 32'h48,
                32'h4c, 32'h50, 32'h54, 32'h58, 32'h5c, 32'h60,
                32'h64, 32'h68, 32'h6c: valid_read = 1'b1;
                default: valid_read = 1'b0;
            endcase
        end
    endfunction

    function [31:0] read_register;
        input [31:0] addr;
        begin
            case (addr)
                32'h00: read_register = DEVICE_ID;
                32'h04: read_register = {18'd0, bank_state[1], bank_state[0],
                    3'd0, ((last_error != 0) || session_fault), bridge_busy, src_release_valid,
                    host_valid, ready_exists, cmd_valid, active};
                32'h08: read_register = VERSION;
                32'h0c: read_register = ready_exists ? {31'd0, oldest_bank} : 32'hffffffff;
                // All descriptor words refer ONLY to the bound host claim.
                32'h10: read_register = host_valid ? {31'd0, host_bank} : 32'hffffffff;
                32'h14: read_register = host_valid ? bank_seq[host_bank] : 32'd0;
                32'h18: read_register = host_valid ? bank_gen[host_bank] : 32'd0;
                32'h1c: read_register = host_valid ? OUTPUT_LENGTH : 32'd0;
                32'h20: read_register = host_valid ?
                    (host_bank ? OUTPUT_BANK1_ADDR : OUTPUT_BANK0_ADDR) : 32'd0;
                32'h24: read_register = host_valid ? {29'd0, bank_camera[host_bank]} : 32'd0;
                32'h28: read_register = host_valid ? {31'd0, bank_camera_bank[host_bank]} : 32'd0;
                32'h2c: read_register = host_valid ? bank_src[host_bank] : 32'd0;
                32'h30: read_register = host_valid ? {31'd0, host_bank} : 32'hffffffff;
                32'h34: read_register = host_valid ? bank_token[host_bank][31:0] : 32'd0;
                32'h38: read_register = host_valid ? bank_token[host_bank][63:32] : 32'd0;
                32'h40: read_register = ack_bank;
                32'h44: read_register = ack_seq;
                32'h48: read_register = ack_gen;
                32'h4c: read_register = 32'd0;
                32'h50: read_register = rejected_ack_count;
                32'h54: read_register = rejected_claim_count;
                32'h58: read_register = rejected_raw_count;
                32'h5c: read_register = bridge_failure_count;
                32'h60: read_register = completed_count;
                32'h64: read_register = released_count;
                32'h68: read_register = accepted_count;
                32'h6c: read_register = session_fault ? 32'h52534647 : last_error;
                default: read_register = 32'd0;
            endcase
        end
    endfunction

    always @(posedge core_clk or negedge rst_n) begin
        if (!rst_n) begin
            for (index = 0; index < 2; index = index + 1) begin
                bank_state[index] <= FREE;
                bank_seq[index] <= 0;
                bank_gen[index] <= 0;
                bank_src[index] <= 0;
                bank_camera[index] <= 0;
                bank_camera_bank[index] <= 0;
                bank_token[index] <= 0;
            end
            active <= 0;
            active_bank <= 0;
            issued <= 0;
            operation_failed <= 0;
            command_rejected <= 0;
            ready_older <= 0;
            host_valid <= 0;
            host_bank <= 0;
            cmd_valid <= 0;
            cmd_src_addr <= 0;
            cmd_dst_addr <= 0;
            cmd_frame_id <= 0;
            src_release_valid <= 0;
            src_release_addr <= 0;
            src_release_seq <= 0;
            src_release_generation <= 0;
            src_release_camera <= 0;
            src_release_camera_bank <= 0;
            src_release_token <= 0;
            ack_bank <= 0;
            ack_seq <= 0;
            ack_gen <= 0;
            rejected_ack_count <= 0;
            rejected_claim_count <= 0;
            rejected_raw_count <= 0;
            bridge_failure_count <= 0;
            completed_count <= 0;
            released_count <= 0;
            accepted_count <= 0;
            last_error <= 0;
            aw_held <= 0;
            w_held <= 0;
            aw_addr <= 0;
            w_data <= 0;
            w_strb <= 0;
            s_axil_bresp <= OKAY;
            s_axil_bvalid <= 0;
            s_axil_rdata <= 0;
            s_axil_rresp <= OKAY;
            s_axil_rvalid <= 0;
        end else begin
            if (src_release_valid && src_release_ready) begin
                src_release_valid <= 0;
                released_count <= released_count + 1;
            end
            if (input_reject) begin
                rejected_raw_count <= rejected_raw_count + 1;
                last_error <= 32'd1;
            end
            if (input_claim) begin
                bank_state[free_bank] <= WRITING;
                bank_seq[free_bank] <= input_source_seq;
                bank_gen[free_bank] <= input_generation;
                bank_src[free_bank] <= input_src_addr;
                bank_camera[free_bank] <= input_camera;
                bank_camera_bank[free_bank] <= input_camera_bank;
                bank_token[free_bank] <= input_lease_token;
                active <= 1;
                active_bank <= free_bank;
                issued <= 0;
                operation_failed <= 0;
                command_rejected <= 0;
                accepted_count <= accepted_count + 1;
                cmd_valid <= 1;
                cmd_src_addr <= input_src_addr;
                cmd_dst_addr <= free_bank ? OUTPUT_BANK1_ADDR : OUTPUT_BANK0_ADDR;
                cmd_frame_id <= input_source_seq;
                src_release_addr <= input_src_addr;
                src_release_seq <= input_source_seq;
                src_release_generation <= input_generation;
                src_release_camera <= input_camera;
                src_release_camera_bank <= input_camera_bank;
                src_release_token <= input_lease_token;
            end
            if (cmd_fire) begin
                cmd_valid <= 0;
                issued <= 1;
            end
            if (active && issued) begin
                if (bridge_error || bridge_cmd_error)
                    operation_failed <= 1;
                if (bridge_cmd_error)
                    command_rejected <= 1;
            end
            if (operation_finished) begin
                active <= 0;
                issued <= 0;
                src_release_valid <= 1;
                if (operation_error) begin
                    bank_state[active_bank] <= FREE;
                    bridge_failure_count <= bridge_failure_count + 1;
                    last_error <= 32'd2;
                end else begin
                    bank_state[active_bank] <= READY;
                    ready_older <= (bank_state[!active_bank] == READY) ?
                                   !active_bank : active_bank;
                    completed_count <= completed_count + 1;
                end
            end

            if (s_axil_bvalid && s_axil_bready)
                s_axil_bvalid <= 0;
            if (s_axil_awvalid && s_axil_awready) begin
                aw_held <= 1;
                aw_addr <= s_axil_awaddr;
            end
            if (s_axil_wvalid && s_axil_wready) begin
                w_held <= 1;
                w_data <= s_axil_wdata;
                w_strb <= s_axil_wstrb;
            end
            if (aw_held && w_held && !s_axil_bvalid) begin
                aw_held <= 0;
                w_held <= 0;
                s_axil_bvalid <= 1;
                s_axil_bresp <= OKAY;
                case (aw_addr)
                    32'h30: if (w_strb[0] && w_data[0]) begin
                        // Bank 1 claim; upper command bits are ignored.
                        if (!host_valid && ready_exists && oldest_bank) begin
                            host_valid <= 1;
                            host_bank <= 1;
                            bank_state[1] <= HOST_READING;
                        end else begin
                            s_axil_bresp <= SLVERR;
                            rejected_claim_count <= rejected_claim_count + 1;
                            last_error <= 32'd3;
                        end
                    end else if (w_strb[0]) begin
                        if (!host_valid && ready_exists && !oldest_bank) begin
                            host_valid <= 1;
                            host_bank <= 0;
                            bank_state[0] <= HOST_READING;
                        end else begin
                            s_axil_bresp <= SLVERR;
                            rejected_claim_count <= rejected_claim_count + 1;
                            last_error <= 32'd3;
                        end
                    end
                    32'h40: ack_bank <= merge_bytes(ack_bank, w_data, w_strb);
                    32'h44: ack_seq <= merge_bytes(ack_seq, w_data, w_strb);
                    32'h48: ack_gen <= merge_bytes(ack_gen, w_data, w_strb);
                    32'h4c: if (w_strb[0] && w_data[0]) begin
                        if (host_valid && (ack_bank == {31'd0, host_bank}) &&
                            (bank_state[host_bank] == HOST_READING) &&
                            (ack_seq == bank_seq[host_bank]) &&
                            (ack_gen == bank_gen[host_bank])) begin
                            bank_state[host_bank] <= FREE;
                            host_valid <= 0;
                        end else begin
                            s_axil_bresp <= SLVERR;
                            rejected_ack_count <= rejected_ack_count + 1;
                            last_error <= 32'd4;
                        end
                    end
                    default: s_axil_bresp <= SLVERR;
                endcase
            end

            // Read current state using THIS accepted AR, never a previous AR.
            // Capture the whole response; no live register mux while stalled.
            if (s_axil_arvalid && s_axil_arready) begin
                s_axil_rvalid <= 1;
                s_axil_rdata <= read_register(s_axil_araddr);
                s_axil_rresp <= valid_read(s_axil_araddr) ? OKAY : SLVERR;
            end else if (s_axil_rvalid && s_axil_rready) begin
                s_axil_rvalid <= 0;
            end
        end
    end
endmodule
