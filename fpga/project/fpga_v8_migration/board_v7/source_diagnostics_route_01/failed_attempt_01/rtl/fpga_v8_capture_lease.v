// Isolated RAW ownership candidate. All interfaces use the capture AXI clock.
// The event inputs MUST come from fpga_v8_capture_ov5640_ddr, not software.
module fpga_v8_capture_lease #(
    parameter [31:0] BANK0_ADDR = 32'h01800000,
    parameter [31:0] BANK1_ADDR = 32'h01a00000,
    parameter [31:0] DDR_LIMIT = 32'h10000000,
    parameter RAW_LENGTH = 614400,
    parameter CAM_DATA_LEN = 38400,
    parameter FRAME_WIDTH = 640,
    parameter FRAME_HEIGHT = 480,
    parameter DATA_WIDTH = 16,
    parameter CAM_ID = 4, // physical cam5, zero-based controller camera index
    parameter HOST_REQUIRED = 1
)(
    input clk, input rst,
    input config_valid, output config_ready, input [31:0] config_generation,
    output reg config_accept, output reg config_reject,
    output reg epoch_start, output reg armed, output config_ok,
    input engine_idle, input capture_bank, input admitted_sof,
    input publish, input [31:0] publish_seq, input retired_error,
    output lease_block,
    output [1:0] bank0_state, output [1:0] bank1_state,
    output reg protocol_fault,

    output reg input_valid, input input_ready, output input_raw_valid,
    output [31:0] input_src_addr, output [31:0] input_length,
    output [31:0] input_seq, output [31:0] input_generation,
    output [2:0] input_camera, output input_bank, output [63:0] input_token,
    input release_valid, output release_ready,
    input [2:0] release_camera, input release_bank,
    input [31:0] release_seq, input [31:0] release_generation,
    input [63:0] release_token,
    output reg release_accept, output reg release_reject,

    output reg host_valid, input host_ready,
    output [31:0] host_src_addr, output [31:0] host_length,
    output [31:0] host_seq, output [31:0] host_generation,
    output [2:0] host_camera, output host_bank, output [63:0] host_token,
    input host_release_valid, output host_release_ready,
    input [2:0] host_release_camera, input host_release_bank,
    input [31:0] host_release_seq, input [31:0] host_release_generation,
    input [63:0] host_release_token,
    output reg host_release_accept, output reg host_release_reject,
    output reg [31:0] published_count, output reg [31:0] failed_count,
    output reg [31:0] rejected_release_count
);
    localparam FREE = 2'd0, WRITING = 2'd1, HELD = 2'd2;
    // Widen BEFORE addition/multiplication, including the 16-byte frame tag.
    localparam [63:0] END0 = {32'd0, BANK0_ADDR} + RAW_LENGTH + 64'd16;
    localparam [63:0] END1 = {32'd0, BANK1_ADDR} + RAW_LENGTH + 64'd16;
    localparam [63:0] GEOMETRY_BYTES = 64'd2 * FRAME_WIDTH * FRAME_HEIGHT;
    localparam PARAM_OK = DATA_WIDTH == 16 && CAM_ID >= 0 && CAM_ID < 6 &&
        (HOST_REQUIRED == 0 || HOST_REQUIRED == 1) &&
        RAW_LENGTH > 0 && FRAME_WIDTH > 0 && FRAME_HEIGHT > 0 &&
        CAM_DATA_LEN >= 2 && (CAM_DATA_LEN % 2) == 0 &&
        RAW_LENGTH == (64'd16 * CAM_DATA_LEN) && RAW_LENGTH == GEOMETRY_BYTES &&
        BANK0_ADDR[3:0] == 0 && BANK1_ADDR[3:0] == 0 &&
        END0 <= {32'd0, DDR_LIMIT} && END1 <= {32'd0, DDR_LIMIT} &&
        (END0 <= {32'd0, BANK1_ADDR} || END1 <= {32'd0, BANK0_ADDR});
    assign config_ok = PARAM_OK;
    reg [1:0] state [0:1];
    reg [31:0] sequence [0:1];
    reg [31:0] generation;
    reg [31:0] next_sequence;
    reg coop_claimed [0:1], coop_released [0:1];
    reg host_claimed [0:1], host_released [0:1];
    reg writing_bank;
    reg coop_offer_bank, host_offer_bank, coop_rr, host_rr;
    wire all_free = state[0] == FREE && state[1] == FREE;
    // config_valid blocks SOF admission, so config and capture cannot race.
    assign config_ready = !rst && all_free && engine_idle && !epoch_start;
    assign lease_block = !PARAM_OK || !armed || protocol_fault || config_valid ||
                         epoch_start || next_sequence == 0 || state[capture_bank] != FREE;
    assign bank0_state = state[0];
    assign bank1_state = state[1];
    assign input_raw_valid = input_valid;
    assign input_bank = coop_offer_bank;
    assign input_src_addr = input_bank ? BANK1_ADDR : BANK0_ADDR;
    assign input_length = RAW_LENGTH;
    assign input_seq = sequence[input_bank];
    assign input_generation = generation;
    assign input_camera = CAM_ID;
    assign input_token = {generation, input_seq};
    assign host_bank = host_offer_bank;
    assign host_src_addr = host_bank ? BANK1_ADDR : BANK0_ADDR;
    assign host_length = RAW_LENGTH;
    assign host_seq = sequence[host_bank];
    assign host_generation = generation;
    assign host_camera = CAM_ID;
    assign host_token = {generation, host_seq};
    assign release_ready = !rst;
    assign host_release_ready = !rst;
    wire coop_match = state[release_bank] == HELD &&
        coop_claimed[release_bank] && !coop_released[release_bank] &&
        release_camera == CAM_ID && release_seq == sequence[release_bank] &&
        release_generation == generation && release_token == {generation, sequence[release_bank]};
    wire host_match = HOST_REQUIRED && state[host_release_bank] == HELD &&
        host_claimed[host_release_bank] && !host_released[host_release_bank] &&
        host_release_camera == CAM_ID && host_release_seq == sequence[host_release_bank] &&
        host_release_generation == generation && host_release_token == {generation, sequence[host_release_bank]};
    wire coop_fire = release_valid && release_ready && coop_match;
    wire host_fire = host_release_valid && host_release_ready && host_match;
    wire coop_available0 = state[0] == HELD && !coop_claimed[0];
    wire coop_available1 = state[1] == HELD && !coop_claimed[1];
    wire host_available0 = HOST_REQUIRED && state[0] == HELD && !host_claimed[0];
    wire host_available1 = HOST_REQUIRED && state[1] == HELD && !host_claimed[1];
    integer i;
    always @(posedge clk) begin
        if (rst) begin
            generation <= 0;
            next_sequence <= 1;
            armed <= 0;
            epoch_start <= 0;
            config_accept <= 0;
            config_reject <= 0;
            protocol_fault <= 0;
            input_valid <= 0;
            host_valid <= 0;
            coop_offer_bank <= 0;
            host_offer_bank <= 0;
            coop_rr <= 0;
            host_rr <= 0;
            writing_bank <= 0;
            release_accept <= 0;
            release_reject <= 0;
            host_release_accept <= 0;
            host_release_reject <= 0;
            published_count <= 0;
            failed_count <= 0;
            rejected_release_count <= 0;
            for (i=0; i<2; i=i+1) begin
                state[i] <= FREE;
                sequence[i] <= 0;
                coop_claimed[i] <= 0;
                coop_released[i] <= 0;
                host_claimed[i] <= 0;
                host_released[i] <= !HOST_REQUIRED;
            end
        end else begin
            epoch_start <= 0;
            config_accept <= 0;
            config_reject <= 0;
            release_accept <= coop_fire;
            release_reject <= release_valid && release_ready && !coop_match;
            host_release_accept <= host_fire;
            host_release_reject <= host_release_valid && host_release_ready && !host_match;
            rejected_release_count <= rejected_release_count +
                (release_valid && release_ready && !coop_match) +
                (host_release_valid && host_release_ready && !host_match);
            if (config_valid && config_ready) begin
                if (PARAM_OK && config_generation != 0 && config_generation != generation && !protocol_fault) begin
                    generation <= config_generation;
                    next_sequence <= 1;
                    armed <= 1;
                    config_accept <= 1;
                    epoch_start <= 1; // idle-only camera datapath epoch restart
                    coop_rr <= 0;
                    host_rr <= 0;
                end else config_reject <= 1;
            end
            if (admitted_sof) begin
                if (!lease_block) begin
                    state[capture_bank] <= WRITING;
                    writing_bank <= capture_bank;
                    coop_claimed[capture_bank] <= 0;
                    coop_released[capture_bank] <= 0;
                    host_claimed[capture_bank] <= 0;
                    host_released[capture_bank] <= !HOST_REQUIRED;
                end else begin protocol_fault <= 1; armed <= 0; end
            end
            if (publish) begin
                if (state[writing_bank] == WRITING && publish_seq == next_sequence && publish_seq != 0) begin
                    state[writing_bank] <= HELD;
                    sequence[writing_bank] <= publish_seq;
                    next_sequence <= next_sequence + 1'b1;
                    published_count <= published_count + 1'b1;
                    if (next_sequence == 32'hffffffff) armed <= 0;
                end else begin protocol_fault <= 1; armed <= 0; end
            end else if (retired_error && state[writing_bank] == WRITING) begin
                state[writing_bank] <= FREE;
                failed_count <= failed_count + 1'b1;
            end
            if (!input_valid && (coop_available0 || coop_available1)) begin
                coop_offer_bank <= coop_available0 && coop_available1 ? coop_rr : !coop_available0;
                input_valid <= 1;
            end else if (input_valid && input_ready) begin
                coop_claimed[input_bank] <= 1;
                input_valid <= 0;
                coop_rr <= !input_bank;
            end
            if (!host_valid && (host_available0 || host_available1)) begin
                host_offer_bank <= host_available0 && host_available1 ? host_rr : !host_available0;
                host_valid <= 1;
            end else if (host_valid && host_ready) begin
                host_claimed[host_bank] <= 1;
                host_valid <= 0;
                host_rr <= !host_bank;
            end
            if (coop_fire) coop_released[release_bank] <= 1;
            if (host_fire) host_released[host_release_bank] <= 1;
            for (i=0; i<2; i=i+1) begin
                if (state[i] == HELD &&
                    (coop_released[i] || (coop_fire && release_bank == i)) &&
                    (host_released[i] || (host_fire && host_release_bank == i))) state[i] <= FREE;
            end
        end
    end
endmodule
