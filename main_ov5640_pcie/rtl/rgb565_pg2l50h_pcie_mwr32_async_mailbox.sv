`default_nettype none

/**
 * @file rgb565_pg2l50h_pcie_mwr32_async_mailbox.sv
 * @brief Transfer one held MWR32 request between asynchronous clock domains.
 *
 * @details
 * The source captures one length/address/data bundle and flips a request token.
 * The destination synchronizes that token, waits one additional destination
 * cycle, captures the stable bundled payload, and holds the request until the
 * downstream ACK. The completed token then returns to the source. Only one
 * transaction may be outstanding.
 *
 * The local online handshake makes each reset visible to the peer before a
 * domain rejoins the channel. An idle single-domain reset therefore rebases the
 * token pair without creating a request. If either domain resets while a
 * transaction is active, the retained peer reports a sticky fault and blocks
 * further traffic until both domains receive a coordinated reset.
 *
 * @par Interface contract
 * - Source request and fields are synchronous to `src_clk` and remain asserted
 *   until `src_mwr32_req_ack` is observed.
 * - Destination request and fields are synchronous to `dst_clk` and remain
 *   stable until `dst_mwr32_req_ack` is sampled.
 * - Source ACK remains asserted until the source request is removed.
 * - Destination ACK may remain high after request removal; a new request is
 *   forbidden until ACK returns low.
 * - `src_channel_ready` and `dst_channel_ready` indicate an idle, aligned local
 *   view. They are status outputs, not a substitute for request/ACK handshakes.
 *
 * @par Clock and reset
 * - `src_rst_n` and `dst_rst_n` assert asynchronously.
 * - Each reset must be released synchronously to its local clock by the board
 *   reset tree; both clocks must run during channel recovery.
 * - An idle reset must remain asserted long enough for the peer to observe its
 *   online level low. The online acknowledgement keeps rejoin blocked until
 *   that observation occurs.
 *
 * @par CDC classification
 * - Request and completion tokens: single-bit events using three-stage toggle
 *   synchronizers. Peer-online uses two stages so reset loss is observed before
 *   a reset-induced token change can be consumed by transaction logic.
 * - Request payload: atomic multi-bit bundled data using a stable-data MCP.
 * - Reset/online/fault levels: stable single-bit levels using two-stage
 *   destination-domain synchronizers.
 * - Payload must be constrained with reviewed max-delay/bus-skew limits from
 *   source holding registers to destination capture registers. Do not declare
 *   the complete payload bus false-path.
 *
 * @warning
 * RTL simulation cannot prove metastability resolution or inter-bit skew. The
 * `ASYNC_REG` attributes are placement hints that require confirmation in the
 * target Pango/PDS flow and do not prove CDC protocol correctness.
 *
 * @warning
 * A reset during an active transaction has an indeterminate external result:
 * the PCIe request may or may not have been accepted. This module does not
 * replay it and cannot guarantee exactly-once delivery without transaction IDs
 * and receiver-side duplicate suppression.
 */
module rgb565_pg2l50h_pcie_mwr32_async_mailbox (
    input  wire logic        src_rst_n,
    input  wire logic        src_clk,
    input  wire logic        src_mwr32_req,
    output logic             src_mwr32_req_ack,
    input  wire logic [9:0]  src_req_length,
    input  wire logic [63:0] src_req_addr,
    input  wire logic [31:0] src_req_data,
    output logic             src_channel_ready,
    output logic             src_fault_pulse,
    output logic             src_fault_sticky,

    input  wire logic        dst_rst_n,
    input  wire logic        dst_clk,
    output logic             dst_mwr32_req,
    input  wire logic        dst_mwr32_req_ack,
    output logic [9:0]       dst_req_length,
    output logic [63:0]      dst_req_addr,
    output logic [31:0]      dst_req_data,
    output logic             dst_channel_ready,
    output logic             dst_fault_pulse,
    output logic             dst_fault_sticky
);
    typedef enum logic [1:0] {
        SRC_IDLE,
        SRC_WAIT_ACK,
        SRC_WAIT_REQ_LOW
    } src_state_t;

    typedef enum logic [1:0] {
        DST_IDLE,
        DST_CAPTURE_WAIT,
        DST_WAIT_ACK,
        DST_WAIT_ACK_LOW
    } dst_state_t;

    src_state_t src_state;
    dst_state_t dst_state;

    logic src_online;
    logic dst_online;
    logic src_seen_dst_down;
    logic dst_seen_src_down;

    logic req_toggle;
    logic ack_toggle;
    logic captured_req_toggle;

    logic [9:0]  src_payload_length;
    logic [63:0] src_payload_addr;
    logic [31:0] src_payload_data;

    (* ASYNC_REG = "TRUE" *) logic dst_online_src_sync1;
    (* ASYNC_REG = "TRUE" *) logic dst_online_src_sync2;
    (* ASYNC_REG = "TRUE" *) logic dst_seen_src_down_src_sync1;
    (* ASYNC_REG = "TRUE" *) logic dst_seen_src_down_src_sync2;
    (* ASYNC_REG = "TRUE" *) logic ack_toggle_src_sync1;
    (* ASYNC_REG = "TRUE" *) logic ack_toggle_src_sync2;
    (* ASYNC_REG = "TRUE" *) logic ack_toggle_src_sync3;
    (* ASYNC_REG = "TRUE" *) logic dst_fault_src_sync1;
    (* ASYNC_REG = "TRUE" *) logic dst_fault_src_sync2;
    (* ASYNC_REG = "TRUE" *) logic dst_channel_ready_src_sync1;
    (* ASYNC_REG = "TRUE" *) logic dst_channel_ready_src_sync2;

    (* ASYNC_REG = "TRUE" *) logic src_online_dst_sync1;
    (* ASYNC_REG = "TRUE" *) logic src_online_dst_sync2;
    (* ASYNC_REG = "TRUE" *) logic src_seen_dst_down_dst_sync1;
    (* ASYNC_REG = "TRUE" *) logic src_seen_dst_down_dst_sync2;
    (* ASYNC_REG = "TRUE" *) logic req_toggle_dst_sync1;
    (* ASYNC_REG = "TRUE" *) logic req_toggle_dst_sync2;
    (* ASYNC_REG = "TRUE" *) logic req_toggle_dst_sync3;
    (* ASYNC_REG = "TRUE" *) logic src_fault_dst_sync1;
    (* ASYNC_REG = "TRUE" *) logic src_fault_dst_sync2;

    logic src_session_ready;
    logic dst_session_ready;

    always_comb begin
        src_session_ready = src_online && dst_online_src_sync2 &&
                            !src_seen_dst_down && !dst_fault_src_sync2 &&
                            !src_fault_sticky;
        dst_session_ready = dst_online && src_online_dst_sync2 &&
                            !dst_seen_src_down && !src_fault_dst_sync2 &&
                            !dst_fault_sticky;

        src_channel_ready = src_session_ready && (src_state == SRC_IDLE) &&
                            (ack_toggle_src_sync3 == req_toggle) &&
                            dst_channel_ready_src_sync2;
        dst_channel_ready = dst_session_ready && (dst_state == DST_IDLE) &&
                            (req_toggle_dst_sync3 == ack_toggle) &&
                            !dst_mwr32_req_ack;

        src_mwr32_req_ack = (src_state == SRC_WAIT_REQ_LOW) &&
                            !src_fault_sticky;
        dst_mwr32_req = (dst_state == DST_WAIT_ACK) &&
                        !dst_fault_sticky;
    end

    // CDC: peer online, reset acknowledgement, completion token, and fault.
    // Destination domain: src_clk. All signals are stable single-bit levels or
    // a toggle event; only the second synchronizer stage is consumed.
    always_ff @(posedge src_clk or negedge src_rst_n) begin
        if (!src_rst_n) begin
            dst_online_src_sync1 <= 1'b0;
            dst_online_src_sync2 <= 1'b0;
            dst_seen_src_down_src_sync1 <= 1'b0;
            dst_seen_src_down_src_sync2 <= 1'b0;
            ack_toggle_src_sync1 <= 1'b0;
            ack_toggle_src_sync2 <= 1'b0;
            ack_toggle_src_sync3 <= 1'b0;
            dst_fault_src_sync1 <= 1'b0;
            dst_fault_src_sync2 <= 1'b0;
            dst_channel_ready_src_sync1 <= 1'b0;
            dst_channel_ready_src_sync2 <= 1'b0;
        end else begin
            dst_online_src_sync1 <= dst_online;
            dst_online_src_sync2 <= dst_online_src_sync1;
            dst_seen_src_down_src_sync1 <= dst_seen_src_down;
            dst_seen_src_down_src_sync2 <= dst_seen_src_down_src_sync1;
            ack_toggle_src_sync1 <= ack_toggle;
            ack_toggle_src_sync2 <= ack_toggle_src_sync1;
            ack_toggle_src_sync3 <= ack_toggle_src_sync2;
            dst_fault_src_sync1 <= dst_fault_sticky;
            dst_fault_src_sync2 <= dst_fault_src_sync1;
            dst_channel_ready_src_sync1 <= dst_channel_ready;
            dst_channel_ready_src_sync2 <= dst_channel_ready_src_sync1;
        end
    end

    // CDC: peer online, reset acknowledgement, request token, and fault.
    // Destination domain: dst_clk. The request token is observed before a
    // separate capture-wait state samples the stable bundled payload.
    always_ff @(posedge dst_clk or negedge dst_rst_n) begin
        if (!dst_rst_n) begin
            src_online_dst_sync1 <= 1'b0;
            src_online_dst_sync2 <= 1'b0;
            src_seen_dst_down_dst_sync1 <= 1'b0;
            src_seen_dst_down_dst_sync2 <= 1'b0;
            req_toggle_dst_sync1 <= 1'b0;
            req_toggle_dst_sync2 <= 1'b0;
            req_toggle_dst_sync3 <= 1'b0;
            src_fault_dst_sync1 <= 1'b0;
            src_fault_dst_sync2 <= 1'b0;
        end else begin
            src_online_dst_sync1 <= src_online;
            src_online_dst_sync2 <= src_online_dst_sync1;
            src_seen_dst_down_dst_sync1 <= src_seen_dst_down;
            src_seen_dst_down_dst_sync2 <= src_seen_dst_down_dst_sync1;
            req_toggle_dst_sync1 <= req_toggle;
            req_toggle_dst_sync2 <= req_toggle_dst_sync1;
            req_toggle_dst_sync3 <= req_toggle_dst_sync2;
            src_fault_dst_sync1 <= src_fault_sticky;
            src_fault_dst_sync2 <= src_fault_dst_sync1;
        end
    end

    // Intent: keep each reset visible until the peer acknowledges seeing the
    // local online level low. This closes idle single-domain reset recovery.
    always_ff @(posedge src_clk or negedge src_rst_n) begin
        if (!src_rst_n) begin
            src_online <= 1'b0;
            src_seen_dst_down <= 1'b0;
        end else begin
            if (!dst_online_src_sync2)
                src_seen_dst_down <= 1'b1;
            else if (src_online)
                src_seen_dst_down <= 1'b0;

            if (!src_online && dst_seen_src_down_src_sync2)
                src_online <= 1'b1;
        end
    end

    always_ff @(posedge dst_clk or negedge dst_rst_n) begin
        if (!dst_rst_n) begin
            dst_online <= 1'b0;
            dst_seen_src_down <= 1'b0;
        end else begin
            if (!src_online_dst_sync2)
                dst_seen_src_down <= 1'b1;
            else if (dst_online)
                dst_seen_src_down <= 1'b0;

            if (!dst_online && src_seen_dst_down_dst_sync2)
                dst_online <= 1'b1;
        end
    end

    // FSM: source transaction owner
    // Type: Moore; ACK is decoded from SRC_WAIT_REQ_LOW.
    // Encoding: auto; no interface behavior depends on a fixed encoding.
    // Reset state: SRC_IDLE with request token zero.
    // Illegal-state policy: return to SRC_IDLE without toggling a token.
    // Hazard: any peer fault blocks the channel until coordinated reset.
    always_ff @(posedge src_clk or negedge src_rst_n) begin
        if (!src_rst_n) begin
            src_state <= SRC_IDLE;
            req_toggle <= 1'b0;
            src_payload_length <= 10'd0;
            src_payload_addr <= 64'd0;
            src_payload_data <= 32'd0;
            src_fault_pulse <= 1'b0;
            src_fault_sticky <= 1'b0;
        end else begin
            src_fault_pulse <= 1'b0;

            if (!src_fault_sticky && dst_fault_src_sync2) begin
                src_fault_pulse <= 1'b1;
                src_fault_sticky <= 1'b1;
            end else if (!src_fault_sticky && !dst_online_src_sync2 &&
                         (src_state != SRC_IDLE)) begin
                src_fault_pulse <= 1'b1;
                src_fault_sticky <= 1'b1;
            end else if (!src_fault_sticky) begin
                unique case (src_state)
                    SRC_IDLE: begin
                        if (src_channel_ready && src_mwr32_req) begin
                            src_payload_length <= src_req_length;
                            src_payload_addr <= src_req_addr;
                            src_payload_data <= src_req_data;
                            req_toggle <= ~req_toggle;
                            src_state <= SRC_WAIT_ACK;
                        end
                    end

                    SRC_WAIT_ACK: begin
                        if (ack_toggle_src_sync3 == req_toggle)
                            src_state <= SRC_WAIT_REQ_LOW;
                    end

                    SRC_WAIT_REQ_LOW: begin
                        if (!src_mwr32_req)
                            src_state <= SRC_IDLE;
                    end

                    default: begin
                        src_state <= SRC_IDLE;
                    end
                endcase
            end
        end
    end

    // FSM: destination transaction owner
    // Type: Moore; request is decoded from DST_WAIT_ACK.
    // Encoding: auto; no interface behavior depends on a fixed encoding.
    // Reset state: DST_IDLE with completion token zero.
    // Output timing: one explicit cycle separates synchronized-token detection
    // from atomic payload capture; ACK completion removes request on the next
    // destination edge, then waits for ACK low before returning idle.
    // Hazard: a peer reset while non-idle is an abort, never an auto-replay.
    always_ff @(posedge dst_clk or negedge dst_rst_n) begin
        if (!dst_rst_n) begin
            dst_state <= DST_IDLE;
            ack_toggle <= 1'b0;
            captured_req_toggle <= 1'b0;
            dst_req_length <= 10'd0;
            dst_req_addr <= 64'd0;
            dst_req_data <= 32'd0;
            dst_fault_pulse <= 1'b0;
            dst_fault_sticky <= 1'b0;
        end else begin
            dst_fault_pulse <= 1'b0;

            if (!dst_fault_sticky && src_fault_dst_sync2) begin
                dst_fault_pulse <= 1'b1;
                dst_fault_sticky <= 1'b1;
                dst_state <= DST_IDLE;
            end else if (!src_online_dst_sync2) begin
                if (!dst_fault_sticky && (dst_state != DST_IDLE)) begin
                    dst_fault_pulse <= 1'b1;
                    dst_fault_sticky <= 1'b1;
                end
                dst_state <= DST_IDLE;
                ack_toggle <= req_toggle_dst_sync3;
            end else if (!dst_online) begin
                dst_state <= DST_IDLE;
                ack_toggle <= req_toggle_dst_sync3;
            end else if (!dst_fault_sticky) begin
                unique case (dst_state)
                    DST_IDLE: begin
                        if (dst_session_ready && !dst_mwr32_req_ack &&
                            (req_toggle_dst_sync3 != ack_toggle)) begin
                            captured_req_toggle <= req_toggle_dst_sync3;
                            dst_state <= DST_CAPTURE_WAIT;
                        end
                    end

                    DST_CAPTURE_WAIT: begin
                        dst_req_length <= src_payload_length;
                        dst_req_addr <= src_payload_addr;
                        dst_req_data <= src_payload_data;
                        dst_state <= DST_WAIT_ACK;
                    end

                    DST_WAIT_ACK: begin
                        if (dst_mwr32_req_ack) begin
                            ack_toggle <= captured_req_toggle;
                            dst_state <= DST_WAIT_ACK_LOW;
                        end
                    end

                    DST_WAIT_ACK_LOW: begin
                        if (!dst_mwr32_req_ack)
                            dst_state <= DST_IDLE;
                    end

                    default: begin
                        dst_state <= DST_IDLE;
                    end
                endcase
            end
        end
    end
endmodule

`default_nettype wire
