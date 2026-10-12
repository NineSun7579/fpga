`timescale 1ns/1ps
// Exact M02 slot, 16-byte register stride for existing PCIe DMA register access.
module delivery_regs #(
    parameter [31:0] BASE=32'h40020000,
    parameter [31:0] DEST=32'h0a000000,
    parameter integer WIDTH=640, HEIGHT=480, OUT_HEIGHT=640
) (
    input wire clk, rst,
    input wire [31:0] s_awaddr, s_wdata, s_araddr,
    input wire [3:0] s_wstrb,
    input wire s_awvalid, s_wvalid, s_bready, s_arvalid, s_rready,
    output wire s_awready, s_wready, s_arready,
    output reg s_bvalid, s_rvalid,
    output reg [1:0] s_bresp, s_rresp,
    output reg [31:0] s_rdata,
    output reg capture_hold,
    input wire [31:0] camera_state, camera_prev_base,
    input wire [1:0] camera_published,
    input wire camera_cmd_valid, camera_awvalid, camera_wvalid, camera_abort,
    output reg cmd_valid,
    input wire cmd_ready, core_busy, core_done, core_error, core_config_error,
    output wire [31:0] cmd_src,
    output reg [31:0] cmd_dst
);
    reg aw_have, w_have;
    reg [31:0] aw_addr, w_data;
    reg [3:0] w_strb;
    reg frozen, completed, failed;
    reg [5:0] quiet;
    reg [31:0] frozen_base, epoch, cycles, last_cycles, jobs_done;
    wire drain_idle=camera_state==1 && !camera_cmd_valid &&
        !camera_awvalid && !camera_wvalid && !camera_abort;
    wire published=(camera_prev_base==32'h01800000 && camera_published[0]) ||
        (camera_prev_base==32'h01a00000 && camera_published[1]);
    wire busy=core_busy || cmd_valid;
    wire quarantined=!core_busy && !cmd_valid && !cmd_ready && !core_config_error;
    assign cmd_src=frozen_base;
    assign s_awready=!rst && !aw_have && !s_bvalid;
    assign s_wready=!rst && !w_have && !s_bvalid;
    assign s_arready=!rst && !s_rvalid;
    integer lane;
    always @(posedge clk) begin
        if (rst) begin
            aw_have<=0; w_have<=0; s_bvalid<=0; s_rvalid<=0;
            s_bresp<=0; s_rresp<=0; s_rdata<=0;
            aw_addr<=0; w_data<=0; w_strb<=0;
            capture_hold<=0; frozen<=0; quiet<=0; frozen_base<=0;
            completed<=0; failed<=0; epoch<=0; cycles<=0; last_cycles<=0; jobs_done<=0;
            cmd_valid<=0; cmd_dst<=DEST;
        end else begin
            if (s_awvalid && s_awready) begin aw_have<=1; aw_addr<=s_awaddr; end
            if (s_wvalid && s_wready) begin w_have<=1; w_data<=s_wdata; w_strb<=s_wstrb; end
            if (s_bvalid && s_bready) s_bvalid<=0;
            if (s_rvalid && s_rready) s_rvalid<=0;
            if (cmd_valid && cmd_ready) cmd_valid<=0;
            if (!capture_hold) begin frozen<=0; quiet<=0; end
            else if (!frozen) begin
                if (!drain_idle) quiet<=0;
                else if (quiet<32) quiet<=quiet+1;
                else if (published) begin frozen<=1; frozen_base<=camera_prev_base; end
            end
            if (core_busy) cycles<=cycles+1;
            if (core_done) begin
                completed<=1; failed<=core_error; last_cycles<=cycles; jobs_done<=jobs_done+1;
            end
            if (aw_have && w_have && !s_bvalid) begin
                aw_have<=0; w_have<=0; s_bvalid<=1; s_bresp<=0;
                case (aw_addr)
                    BASE+32'h20: begin
                        if (w_strb[0]) begin
                            if (!w_data[0] && (busy || quarantined)) s_bresp<=2;
                            else if (w_data[1] && (!w_data[0] || !frozen || !cmd_ready || busy)) s_bresp<=2;
                            else begin
                                capture_hold<=w_data[0];
                                if (w_data[0] && !capture_hold) epoch<=epoch+1;
                                if (w_data[1]) begin
                                    cmd_valid<=1; completed<=0; failed<=0; cycles<=0;
                                end
                            end
                        end
                    end
                    BASE+32'h40: begin
                        // This clone reserves one destination only; no arbitrary DDR writes.
                        if (busy || w_strb!=4'hf || w_data!=DEST) s_bresp<=2;
                        else cmd_dst<=w_data;
                    end
                    default: s_bresp<=2;
                endcase
            end
            if (s_arvalid && s_arready) begin
                s_rvalid<=1; s_rresp<=0;
                case (s_araddr)
                    BASE+32'h00: s_rdata<=32'h444c5632; // DLV2, actual RTL signature
                    BASE+32'h10: s_rdata<={25'd0,quarantined,core_config_error,failed,
                                          completed,busy,frozen,capture_hold};
                    BASE+32'h20: s_rdata<={31'd0,capture_hold};
                    BASE+32'h30: s_rdata<=frozen_base;
                    BASE+32'h40: s_rdata<=cmd_dst;
                    BASE+32'h50: s_rdata<=epoch;
                    BASE+32'h60: s_rdata<=WIDTH*OUT_HEIGHT*3;
                    BASE+32'h70: s_rdata<=last_cycles;
                    BASE+32'h80: s_rdata<=WIDTH*HEIGHT*2;
                    BASE+32'h90: s_rdata<=jobs_done;
                    default: begin s_rdata<=0; s_rresp<=2; end
                endcase
            end
        end
    end
endmodule
