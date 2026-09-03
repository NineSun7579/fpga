`default_nettype none

/**
 * @file rgb565_pg2l50h_pcie_tx_request_arbiter.sv
 * @brief Arbitrate the complete native TX request bundle and one camera MWR32 source.
 *
 * @details
 * The canonical DMA controller shares one length/address/data bundle across
 * MWR32, MWR64, MRD32, and MRD64 requests. This project-owned boundary keeps
 * that complete native bundle atomic while allowing the camera path to inject
 * a full-DWORD user-defined MWR32 request. Vendor-generated RTL is not changed.
 *
 * Both sources must hold request and fields until their routed ACK is sampled.
 * Native input must assert at most one request type. Ownership remains locked
 * through the matching TX ACK; simultaneous idle requests alternate by the
 * previously completed owner, with native selected first after reset.
 * The vendor MWR controller continues to sample user-defined-data mode after
 * ACK, so that mode is captured on each MWR handshake and retained until the
 * next MWR handshake replaces it.
 *
 * ACK means that the downstream TX controller accepted a request. It does not
 * prove TLP transmission, PCIe link success, or host-memory completion.
 */
module rgb565_pg2l50h_pcie_tx_request_arbiter (
    input  wire logic        rst_n,
    input  wire logic        clk,

    input  wire logic        native_user_define_data_flag,
    input  wire logic        native_mwr32_req,
    output logic             native_mwr32_req_ack,
    input  wire logic        native_mwr64_req,
    output logic             native_mwr64_req_ack,
    input  wire logic        native_mrd32_req,
    output logic             native_mrd32_req_ack,
    input  wire logic        native_mrd64_req,
    output logic             native_mrd64_req_ack,
    input  wire logic [9:0]  native_req_length,
    input  wire logic [63:0] native_req_addr,
    input  wire logic [31:0] native_req_data,

    input  wire logic        camera_mwr32_req,
    output logic             camera_mwr32_req_ack,
    input  wire logic [9:0]  camera_req_length,
    input  wire logic [63:0] camera_req_addr,
    input  wire logic [31:0] camera_req_data,

    output logic             tx_user_define_data_flag,
    output logic             tx_mwr32_req,
    input  wire logic        tx_mwr32_req_ack,
    output logic             tx_mwr64_req,
    input  wire logic        tx_mwr64_req_ack,
    output logic             tx_mrd32_req,
    input  wire logic        tx_mrd32_req_ack,
    output logic             tx_mrd64_req,
    input  wire logic        tx_mrd64_req_ack,
    output logic [9:0]       tx_req_length,
    output logic [63:0]      tx_req_addr,
    output logic [31:0]      tx_req_data
);
    typedef enum logic [1:0] {
        OWNER_IDLE,
        OWNER_NATIVE,
        OWNER_CAMERA
    } owner_t;

    owner_t owner;
    logic   last_grant_camera;
    logic   mwr_user_define_data_mode;
    logic   native_any_req;
    logic   native_handshake;
    logic   native_mwr_handshake;
    logic   camera_handshake;

    always_comb begin
        native_any_req = native_mwr32_req || native_mwr64_req ||
                         native_mrd32_req || native_mrd64_req;
        native_handshake = (tx_mwr32_req && tx_mwr32_req_ack) ||
                           (tx_mwr64_req && tx_mwr64_req_ack) ||
                           (tx_mrd32_req && tx_mrd32_req_ack) ||
                           (tx_mrd64_req && tx_mrd64_req_ack);
        native_mwr_handshake = (tx_mwr32_req && tx_mwr32_req_ack) ||
                               (tx_mwr64_req && tx_mwr64_req_ack);
        camera_handshake = tx_mwr32_req && tx_mwr32_req_ack;
    end

    // Intent: expose only the selected source and return ACK only to its owner.
    // Invariant: owner cannot change before the selected request handshake.
    always_comb begin
        tx_user_define_data_flag = mwr_user_define_data_mode;
        tx_mwr32_req = 1'b0;
        tx_mwr64_req = 1'b0;
        tx_mrd32_req = 1'b0;
        tx_mrd64_req = 1'b0;
        tx_req_length = 10'd0;
        tx_req_addr = 64'd0;
        tx_req_data = 32'd0;

        native_mwr32_req_ack = 1'b0;
        native_mwr64_req_ack = 1'b0;
        native_mrd32_req_ack = 1'b0;
        native_mrd64_req_ack = 1'b0;
        camera_mwr32_req_ack = 1'b0;

        unique case (owner)
            OWNER_NATIVE: begin
                tx_mwr32_req = native_mwr32_req;
                tx_mwr64_req = native_mwr64_req;
                tx_mrd32_req = native_mrd32_req;
                tx_mrd64_req = native_mrd64_req;
                tx_req_length = native_req_length;
                tx_req_addr = native_req_addr;
                tx_req_data = native_req_data;
                native_mwr32_req_ack = tx_mwr32_req_ack;
                native_mwr64_req_ack = tx_mwr64_req_ack;
                native_mrd32_req_ack = tx_mrd32_req_ack;
                native_mrd64_req_ack = tx_mrd64_req_ack;
            end

            OWNER_CAMERA: begin
                tx_mwr32_req = camera_mwr32_req;
                tx_req_length = camera_req_length;
                tx_req_addr = camera_req_addr;
                tx_req_data = camera_req_data;
                camera_mwr32_req_ack = tx_mwr32_req_ack;
            end

            default: begin
            end
        endcase
    end

    // FSM: TX request owner
    // Type: Moore; selected request outputs are combinational from owner.
    // Encoding: auto; no implementation depends on a fixed encoding.
    // Reset state: OWNER_IDLE, with native first on the initial simultaneous race.
    // Illegal-state policy: return to OWNER_IDLE and restore native-first priority.
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            owner <= OWNER_IDLE;
            last_grant_camera <= 1'b1;
            mwr_user_define_data_mode <= 1'b0;
        end else begin
            unique case (owner)
                OWNER_IDLE: begin
                    if (native_any_req && camera_mwr32_req) begin
                        if (last_grant_camera)
                            owner <= OWNER_NATIVE;
                        else
                            owner <= OWNER_CAMERA;
                    end else if (native_any_req) begin
                        owner <= OWNER_NATIVE;
                    end else if (camera_mwr32_req) begin
                        owner <= OWNER_CAMERA;
                    end
                end

                OWNER_NATIVE: begin
                    if (native_handshake) begin
                        owner <= OWNER_IDLE;
                        last_grant_camera <= 1'b0;
                        if (native_mwr_handshake)
                            mwr_user_define_data_mode <= native_user_define_data_flag;
                    end
                end

                OWNER_CAMERA: begin
                    if (camera_handshake) begin
                        owner <= OWNER_IDLE;
                        last_grant_camera <= 1'b1;
                        mwr_user_define_data_mode <= 1'b1;
                    end
                end

                default: begin
                    owner <= OWNER_IDLE;
                    last_grant_camera <= 1'b1;
                    mwr_user_define_data_mode <= 1'b0;
                end
            endcase
        end
    end
endmodule

`default_nettype wire
