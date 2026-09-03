`default_nettype none

/**
 * @file rgb565_pg2l50h_ddr3_read_adapter.sv
 * @brief Map one PG2L50H DDR3 read beat to one normalized 32-bit record.
 *
 * @details
 * The adapter owns one command and one response at a time. It pre-captures a
 * held normalized address, sends a single-beat canonical AR command, and stores
 * the returned 128-bit beat in an output register because the DDR3 user port has
 * no RREADY input. Payload occupies the low DWORD; record metadata is restored
 * from byte lane 4 using the layout written by
 * `rgb565_axis4_ddr3_write_descriptor`.
 *
 * This module does not instantiate the DDR3 core, decode physical addresses,
 * allocate frame slots, or prove memory persistence and calibration.
 *
 * @par Interface contract
 * - The command source asserts `in_valid` and holds `in_addr` until `in_ready`.
 * - `ddr_init_done` is synchronized through two `clk` stages before admission.
 * - `axi_arvalid` and all AR fields remain stable until `axi_arready`.
 * - Every command is exactly one 128-bit beat, so `axi_arlen=0`.
 * - `in_ready` is asserted only on the canonical AR handshake.
 * - The canonical port may return `axi_rvalid` on the AR handshake edge.
 * - Returned data and metadata remain stable until `out_valid && out_ready`.
 * - A mismatched RID or deasserted RLAST marks the normalized response as a
 *   protocol error; unsolicited or duplicate RVALID raises `port_fault_pulse`.
 *
 * @par Parameters
 * - `REQUEST_ID` is the fixed four-bit AR ID expected on the returned RID.
 *
 * @par Clock and reset
 * - Clock: `clk`, connected to the DDR3 core `core_clk`.
 * - Reset: `rst_n`, active-low asynchronous assertion; the integration layer
 *   must release it synchronously to `clk`.
 *
 * @par Assumptions
 * - The 28-bit input address is already encoded in canonical DDR3 user-port
 *   units; this adapter does not define byte, beat, bank, row, or column units.
 * - `ddr_init_done` remains high for the lifetime of an accepted transaction.
 * - The core returns exactly one RVALID event for an accepted ARLEN=0 command.
 * - The writer and reader use the same metadata bit layout and low-lane order.
 *
 * @warning
 * The canonical DDR3 read port cannot be backpressured. The single output
 * register is therefore part of the protocol boundary, not an optional
 * performance buffer. A second response while it is occupied is unrecoverable
 * data loss and is reported by `port_fault_pulse`.
 */
module rgb565_pg2l50h_ddr3_read_adapter #(
    parameter logic [3:0] REQUEST_ID = 4'd0
) (
    input  wire logic         rst_n,
    input  wire logic         clk,
    input  wire logic         ddr_init_done,
    input  wire logic         in_valid,
    output logic              in_ready,
    input  wire logic [27:0]  in_addr,
    output logic [27:0]       axi_araddr,
    output logic              axi_aruser_ap,
    output logic [3:0]        axi_aruser_id,
    output logic [3:0]        axi_arlen,
    output logic              axi_arvalid,
    input  wire logic         axi_arready,
    input  wire logic [127:0] axi_rdata,
    input  wire logic [3:0]   axi_rid,
    input  wire logic         axi_rlast,
    input  wire logic         axi_rvalid,
    output logic              out_valid,
    input  wire logic         out_ready,
    output logic [31:0]       out_data,
    output logic [3:0]        out_keep,
    output logic              out_last,
    output logic              out_frame_end,
    output logic              out_protocol_error,
    output logic              port_fault_pulse,
    output logic              busy
);
    typedef enum logic [1:0] {
        ST_IDLE,
        ST_AR,
        ST_R,
        ST_OUT
    } state_t;

    state_t       state_reg;
    logic [1:0]   init_sync_reg;
    logic [27:0]  addr_reg;
    logic [31:0]  data_reg;
    logic [3:0]   keep_reg;
    logic         last_reg;
    logic         frame_end_reg;
    logic         protocol_error_reg;
    logic         ar_accepted;

    // CDC: ddr_init_done
    // Source domain: DDR3 core status generation domain
    // Destination domain: clk / DDR3 core application domain
    // Event model: stable single-bit level
    // Mechanism: two-stage destination-domain synchronizer, matching the vendor example
    // Latency: two to three clk edges before read admission
    // Assumption: ddr_init_done stays asserted after calibration completes
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            init_sync_reg <= 2'b00;
        else
            init_sync_reg <= {init_sync_reg[0], ddr_init_done};
    end

    always_comb begin
        axi_araddr = addr_reg;
        axi_aruser_ap = 1'b0;
        axi_aruser_id = REQUEST_ID;
        axi_arlen = 4'd0;
        axi_arvalid = (state_reg == ST_AR);
        ar_accepted = axi_arvalid && axi_arready;
        in_ready = ar_accepted;
        out_valid = (state_reg == ST_OUT);
        out_data = data_reg;
        out_keep = keep_reg;
        out_last = last_reg;
        out_frame_end = frame_end_reg;
        out_protocol_error = protocol_error_reg;
        busy = (state_reg != ST_IDLE);
    end

    /**
     * Intent: Serialize one canonical AR command, an unbackpressured R beat, and
     *         one backpressured normalized output record.
     * FSM: Mixed-output, four-state, auto encoding. ARVALID and OUT_VALID are
     *      state-only; command ready additionally depends on canonical ARREADY.
     * Invariant: No new AR command is admitted while a response is outstanding.
     * Latency: AR begins one cycle after pre-capture; output follows the R edge.
     * Illegal-state policy: Return to idle and discard incomplete state.
     */
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_reg          <= ST_IDLE;
            addr_reg           <= 28'd0;
            data_reg           <= 32'd0;
            keep_reg           <= 4'd0;
            last_reg           <= 1'b0;
            frame_end_reg      <= 1'b0;
            protocol_error_reg <= 1'b0;
            port_fault_pulse   <= 1'b0;
        end else begin
            port_fault_pulse <= 1'b0;

            case (state_reg)
                ST_IDLE: begin
                    if (axi_rvalid)
                        port_fault_pulse <= 1'b1;
                    if (init_sync_reg[1] && in_valid) begin
                        addr_reg <= in_addr;
                        state_reg <= ST_AR;
                    end
                end
                ST_AR: begin
                    if (axi_rvalid && !ar_accepted)
                        port_fault_pulse <= 1'b1;
                    if (ar_accepted) begin
                        if (axi_rvalid) begin
                            data_reg <= axi_rdata[31:0];
                            keep_reg <= axi_rdata[35:32];
                            last_reg <= axi_rdata[36];
                            frame_end_reg <= axi_rdata[37];
                            protocol_error_reg <= axi_rdata[38] |
                                                  (axi_rid != REQUEST_ID) |
                                                  !axi_rlast;
                            state_reg <= ST_OUT;
                        end else begin
                            state_reg <= ST_R;
                        end
                    end
                end
                ST_R: begin
                    if (axi_rvalid) begin
                        data_reg <= axi_rdata[31:0];
                        keep_reg <= axi_rdata[35:32];
                        last_reg <= axi_rdata[36];
                        frame_end_reg <= axi_rdata[37];
                        protocol_error_reg <= axi_rdata[38] |
                                              (axi_rid != REQUEST_ID) |
                                              !axi_rlast;
                        state_reg <= ST_OUT;
                    end
                end
                ST_OUT: begin
                    if (axi_rvalid)
                        port_fault_pulse <= 1'b1;
                    if (out_ready)
                        state_reg <= ST_IDLE;
                end
                default: begin
                    state_reg <= ST_IDLE;
                end
            endcase
        end
    end
endmodule

`default_nettype wire
