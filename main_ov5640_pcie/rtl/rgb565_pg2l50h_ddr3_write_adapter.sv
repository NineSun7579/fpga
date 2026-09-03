`default_nettype none

/**
 * @file rgb565_pg2l50h_ddr3_write_adapter.sv
 * @brief Map one normalized 128-bit write record to the PG2L50H DDR3 user port.
 *
 * @details
 * The adapter owns one transaction at a time. It pre-captures a held source
 * record, sends one address command, and keeps the write data stable until the
 * DDR3 core consumes it with `axi_wready`. Upstream completion is deliberately
 * delayed to that data-consume edge so frame commit cannot precede the DDR3
 * user-port acceptance represented by this boundary.
 *
 * This module does not instantiate the DDR3 core, decode physical addresses,
 * allocate frame slots, or prove memory persistence and calibration.
 *
 * @par Interface contract
 * - The source asserts `in_valid` and holds all fields until `in_ready`.
 * - `ddr_init_done` is synchronized through two `clk` stages, matching the
 *   generated example design, before a request may be pre-captured.
 * - `axi_awvalid` and all AW fields remain stable until `axi_awready`.
 * - Every request is exactly one 128-bit beat, so `axi_awlen=0`.
 * - `axi_wdata/axi_wstrb` remain stable through AW and W phases.
 * - `in_ready` is asserted only when the single data beat is consumed; AW and
 *   W may complete on the same clock edge.
 *
 * @par Parameters
 * - `REQUEST_ID` is the fixed four-bit ID returned by the core sideband path.
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
 * - The two-stage synchronizer increases resolution time; project CDC/RDC and
 *   recovery/removal signoff remain required for the final integrated reset tree.
 * - The source obeys ready/valid stability while the adapter pre-captures it.
 *
 * @warning
 * The canonical interface has no B channel. `in_ready` proves only that this
 * user-port data beat was consumed, not that DDR3 storage or readback passed.
 */
module rgb565_pg2l50h_ddr3_write_adapter #(
    parameter logic [3:0] REQUEST_ID = 4'd0
) (
    input  wire logic         rst_n,
    input  wire logic         clk,
    input  wire logic         ddr_init_done,
    input  wire logic         in_valid,
    output logic              in_ready,
    input  wire logic [27:0]  in_addr,
    input  wire logic [127:0] in_data,
    input  wire logic [15:0]  in_strb,
    output logic [27:0]       axi_awaddr,
    output logic              axi_awuser_ap,
    output logic [3:0]        axi_awuser_id,
    output logic [3:0]        axi_awlen,
    output logic              axi_awvalid,
    input  wire logic         axi_awready,
    output logic [127:0]      axi_wdata,
    output logic [15:0]       axi_wstrb,
    input  wire logic         axi_wready,
    output logic              busy
);
    typedef enum logic [1:0] {
        ST_IDLE,
        ST_AW,
        ST_W
    } state_t;

    state_t       state_reg;
    logic [1:0]   init_sync_reg;
    logic [27:0]  addr_reg;
    logic [127:0] data_reg;
    logic [15:0]  strb_reg;

    // CDC: ddr_init_done
    // Source domain: DDR3 core status generation domain
    // Destination domain: clk / DDR3 core application domain
    // Event model: stable single-bit level
    // Mechanism: two-stage destination-domain synchronizer, matching the vendor example
    // Latency: two to three clk edges before write admission
    // Assumption: ddr_init_done stays asserted after calibration completes
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            init_sync_reg <= 2'b00;
        else
            init_sync_reg <= {init_sync_reg[0], ddr_init_done};
    end

    always_comb begin
        axi_awaddr = addr_reg;
        axi_awuser_ap = 1'b0;
        axi_awuser_id = REQUEST_ID;
        axi_awlen = 4'd0;
        axi_awvalid = (state_reg == ST_AW);
        axi_wdata = data_reg;
        axi_wstrb = strb_reg;
        busy = (state_reg != ST_IDLE);

        in_ready = 1'b0;
        if (state_reg == ST_AW)
            in_ready = axi_awready && axi_wready;
        else if (state_reg == ST_W)
            in_ready = axi_wready;
    end

    /**
     * Intent: Sequence one canonical AW command and one write-data consume edge.
     * FSM: Mixed output, three-state, auto encoding. `axi_awvalid` is state-only;
     *      `in_ready` additionally depends on the core ready inputs.
     * Invariant: A captured record is immutable until its data beat is consumed.
     * Latency: AW begins one cycle after pre-capture; completion is core-ready dependent.
     * Illegal-state policy: Return to idle without reporting a completed write.
     */
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_reg <= ST_IDLE;
            addr_reg <= 28'd0;
            data_reg <= 128'd0;
            strb_reg <= 16'd0;
        end else begin
            case (state_reg)
                ST_IDLE: begin
                    if (init_sync_reg[1] && in_valid) begin
                        addr_reg <= in_addr;
                        data_reg <= in_data;
                        strb_reg <= in_strb;
                        state_reg <= ST_AW;
                    end
                end
                ST_AW: begin
                    if (axi_awready) begin
                        if (axi_wready)
                            state_reg <= ST_IDLE;
                        else
                            state_reg <= ST_W;
                    end
                end
                ST_W: begin
                    if (axi_wready)
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
