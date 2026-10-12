`timescale 1ns/1ps
// Isolated Verilog-2001 candidate. All ports share clk and common reset.
// Manager port names match fpga_v8_capture_lease exactly; invert rst_n for rst.
module fpga_v8_capture_control_axil #(
    parameter [31:0] LOCAL_BASE = 32'h00000100
) (
    input wire clk, input wire rst_n,
    output wire config_valid, input wire config_ready,
    output wire [31:0] config_generation,
    input wire config_accept, input wire config_reject,
    input wire epoch_start, input wire armed, input wire config_ok,
    input wire protocol_fault,
    input wire [1:0] bank0_state, input wire [1:0] bank1_state,
    input wire host_valid, output wire host_ready,
    input wire [31:0] host_src_addr, input wire [31:0] host_length,
    input wire [31:0] host_seq, input wire [31:0] host_generation,
    input wire [2:0] host_camera, input wire host_bank,
    input wire [63:0] host_token,
    output wire host_release_valid, input wire host_release_ready,
    output wire [2:0] host_release_camera, output wire host_release_bank,
    output wire [31:0] host_release_seq,
    output wire [31:0] host_release_generation,
    output wire [63:0] host_release_token,
    input wire host_release_accept, input wire host_release_reject,
    input wire [31:0] published_count, input wire [31:0] failed_count,
    input wire [31:0] rejected_release_count,
    input wire [31:0] s_axil_awaddr, input wire [2:0] s_axil_awprot,
    input wire s_axil_awvalid, output wire s_axil_awready,
    input wire [31:0] s_axil_wdata, input wire [3:0] s_axil_wstrb,
    input wire s_axil_wvalid, output wire s_axil_wready,
    output reg [1:0] s_axil_bresp, output reg s_axil_bvalid,
    input wire s_axil_bready,
    input wire [31:0] s_axil_araddr, input wire [2:0] s_axil_arprot,
    input wire s_axil_arvalid, output wire s_axil_arready,
    output reg [31:0] s_axil_rdata, output reg [1:0] s_axil_rresp,
    output reg s_axil_rvalid, input wire s_axil_rready
);
    localparam [1:0] NONE=0, ARM_WAIT=1, RELEASE_WAIT=2;
    localparam PARAM_OK = LOCAL_BASE[1:0]==0 && LOCAL_BASE<=32'hffffff80;
    reg aw_held, w_held;
    reg [31:0] aw_addr, w_data;
    reg [3:0] w_strb;
    reg [1:0] pending;
    reg [31:0] staged_generation, accepted_generation;
    reg host_bound;
    reg bound_bank;
    reg [31:0] bound_seq,bound_generation,bound_length,bound_addr;
    reg [2:0] bound_camera;
    reg [63:0] bound_token;
    reg [31:0] ack_bank,ack_seq,ack_generation,ack_token_low,ack_token_high,ack_camera;
    reg [31:0] rejected_claims,bad_acks,rejected_configs;
    reg [31:0] accepted_configs,accepted_claims,accepted_releases;
    wire commit = rst_n && aw_held && w_held && !s_axil_bvalid && pending==NONE;
    wire [31:0] wr_offset=aw_addr-LOCAL_BASE;
    wire wr_in_range=PARAM_OK && aw_addr>=LOCAL_BASE &&
        {1'b0,aw_addr}<({1'b0,LOCAL_BASE}+33'h80) && aw_addr[1:0]==0;
    wire doorbell=w_strb[0] && w_data[0];
    wire key_match=host_bound && ack_bank=={31'd0,bound_bank} &&
        ack_seq==bound_seq && ack_generation==bound_generation &&
        {ack_token_high,ack_token_low}==bound_token &&
        ack_camera=={29'd0,bound_camera};

    assign s_axil_awready=rst_n && !aw_held && !s_axil_bvalid && pending==NONE;
    assign s_axil_wready=rst_n && !w_held && !s_axil_bvalid && pending==NONE;
    assign s_axil_arready=rst_n && (!s_axil_rvalid || s_axil_rready);
    // Ready-dependent, single-edge dispatch from immutable holding slots.
    // This asserts lease_block BEFORE that edge's wrapper SOF admission.
    // No unaccepted valid is queued, so a busy ARM cannot strand host ACK.
    assign config_valid=commit && wr_in_range && wr_offset==32'h10 &&
        doorbell && !host_bound && config_ready;
    assign config_generation=staged_generation;
    assign host_ready=commit && wr_in_range && wr_offset==32'h14 &&
        w_strb[0] && !host_bound && host_valid &&
        w_data=={31'd0,host_bank};
    assign host_release_valid=commit && wr_in_range && wr_offset==32'h50 &&
        doorbell && key_match && host_release_ready;
    assign host_release_camera=bound_camera;
    assign host_release_bank=bound_bank;
    assign host_release_seq=bound_seq;
    assign host_release_generation=bound_generation;
    assign host_release_token=bound_token;

    function [31:0] merge_bytes;
        input [31:0] old_data,new_data;
        input [3:0] strobes;
        integer b;
        begin
            merge_bytes=old_data;
            for(b=0;b<4;b=b+1) if(strobes[b]) merge_bytes[b*8 +: 8]=new_data[b*8 +: 8];
        end
    endfunction
    function valid_read;
        input [31:0] addr;
        begin
            // All 32 aligned words in this exact range are documented below.
            valid_read=PARAM_OK && addr>=LOCAL_BASE &&
                {1'b0,addr}<({1'b0,LOCAL_BASE}+33'h80) && addr[1:0]==0;
        end
    endfunction
    function [31:0] read_register;
        input [31:0] addr;
        begin
            read_register=0;
            if(valid_read(addr)) case(addr-LOCAL_BASE)
                32'h00: read_register=32'h4341504c; // CAPL
                32'h04: read_register={21'd0,(host_valid && host_bank),epoch_start,host_release_ready,config_ready,
                    (pending==RELEASE_WAIT),(pending==ARM_WAIT),host_valid,
                    host_bound,protocol_fault,config_ok,armed};
                32'h08: read_register=32'h00010000;
                32'h0c: read_register=staged_generation;
                32'h10: read_register=0;
                32'h14,32'h18: read_register=host_bound ? {31'd0,bound_bank} : 32'hffffffff;
                32'h1c: read_register=host_bound ? bound_seq : 0;
                32'h20: read_register=host_bound ? bound_generation : 0;
                32'h24: read_register=host_bound ? bound_length : 0;
                32'h28: read_register=host_bound ? bound_addr : 0;
                32'h2c: read_register=host_bound ? {29'd0,bound_camera} : 0;
                32'h30: read_register=host_bound ? bound_token[31:0] : 0;
                32'h34: read_register=host_bound ? bound_token[63:32] : 0;
                32'h38: read_register=ack_bank;
                32'h3c: read_register=ack_seq;
                32'h40: read_register=ack_generation;
                32'h44: read_register=ack_token_low;
                32'h48: read_register=ack_token_high;
                32'h4c: read_register=ack_camera;
                32'h50: read_register=0;
                32'h54: read_register=rejected_claims;
                32'h58: read_register=bad_acks;
                32'h5c: read_register=rejected_configs;
                32'h60: read_register=published_count;
                32'h64: read_register=failed_count;
                32'h68: read_register=rejected_release_count;
                32'h6c: read_register={28'd0,bank1_state,bank0_state};
                32'h70: read_register=accepted_generation;
                32'h74: read_register=accepted_configs;
                32'h78: read_register=accepted_releases;
                32'h7c: read_register=accepted_claims;
                default: read_register=0;
            endcase
        end
    endfunction

    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            aw_held<=0;w_held<=0;aw_addr<=0;w_data<=0;w_strb<=0;pending<=NONE;
            s_axil_bresp<=0;s_axil_bvalid<=0;
            s_axil_rdata<=0;s_axil_rresp<=0;s_axil_rvalid<=0;
            staged_generation<=0;accepted_generation<=0;
            host_bound<=0;bound_bank<=0;bound_seq<=0;bound_generation<=0;
            bound_length<=0;bound_addr<=0;bound_camera<=0;bound_token<=0;
            ack_bank<=0;ack_seq<=0;ack_generation<=0;
            ack_token_low<=0;ack_token_high<=0;ack_camera<=0;
            rejected_claims<=0;bad_acks<=0;rejected_configs<=0;
            accepted_configs<=0;accepted_claims<=0;accepted_releases<=0;
        end else begin
            if(s_axil_bvalid && s_axil_bready) s_axil_bvalid<=0;
            if(s_axil_awvalid && s_axil_awready) begin aw_held<=1;aw_addr<=s_axil_awaddr;end
            if(s_axil_wvalid && s_axil_wready) begin w_held<=1;w_data<=s_axil_wdata;w_strb<=s_axil_wstrb;end
            if(commit) begin
                aw_held<=0;w_held<=0;
                s_axil_bvalid<=1;s_axil_bresp<=0;
                if(!wr_in_range) s_axil_bresp<=2;
                else case(wr_offset)
                    32'h0c: staged_generation<=merge_bytes(staged_generation,w_data,w_strb);
                    32'h10: if(doorbell) begin
                        if(config_valid) begin pending<=ARM_WAIT;s_axil_bvalid<=0;end
                        else begin s_axil_bresp<=2;rejected_configs<=rejected_configs+1'b1;end
                    end
                    32'h14: if(w_strb[0]) begin
                        if(host_ready) begin
                            host_bound<=1;bound_bank<=host_bank;
                            bound_seq<=host_seq;bound_generation<=host_generation;
                            bound_length<=host_length;bound_addr<=host_src_addr;
                            bound_camera<=host_camera;bound_token<=host_token;
                            accepted_claims<=accepted_claims+1'b1;
                        end else begin s_axil_bresp<=2;rejected_claims<=rejected_claims+1'b1;end
                    end
                    32'h38: ack_bank<=merge_bytes(ack_bank,w_data,w_strb);
                    32'h3c: ack_seq<=merge_bytes(ack_seq,w_data,w_strb);
                    32'h40: ack_generation<=merge_bytes(ack_generation,w_data,w_strb);
                    32'h44: ack_token_low<=merge_bytes(ack_token_low,w_data,w_strb);
                    32'h48: ack_token_high<=merge_bytes(ack_token_high,w_data,w_strb);
                    32'h4c: ack_camera<=merge_bytes(ack_camera,w_data,w_strb);
                    32'h50: if(doorbell) begin
                        if(host_release_valid) begin pending<=RELEASE_WAIT;s_axil_bvalid<=0;end
                        else begin s_axil_bresp<=2;bad_acks<=bad_acks+1'b1;end
                    end
                    default: s_axil_bresp<=2;
                endcase
            end
            // Registered manager acceptance is authoritative, not READY alone.
            if(pending==ARM_WAIT && (config_accept || config_reject)) begin
                pending<=NONE;s_axil_bvalid<=1;
                s_axil_bresp<=config_accept && !config_reject ? 0 : 2;
                if(config_accept && !config_reject) begin
                    accepted_generation<=staged_generation;accepted_configs<=accepted_configs+1'b1;
                end else rejected_configs<=rejected_configs+1'b1;
            end
            if(pending==RELEASE_WAIT && (host_release_accept || host_release_reject)) begin
                pending<=NONE;s_axil_bvalid<=1;
                s_axil_bresp<=host_release_accept && !host_release_reject ? 0 : 2;
                if(host_release_accept && !host_release_reject) begin
                    host_bound<=0;accepted_releases<=accepted_releases+1'b1;
                end else bad_acks<=bad_acks+1'b1;
            end
            if(s_axil_arvalid && s_axil_arready) begin
                s_axil_rvalid<=1;s_axil_rdata<=read_register(s_axil_araddr);
                s_axil_rresp<=valid_read(s_axil_araddr) ? 0 : 2;
            end else if(s_axil_rvalid && s_axil_rready) s_axil_rvalid<=0;
        end
    end
    // PROT is accepted and ignored, like the existing cooperative controller.
endmodule
