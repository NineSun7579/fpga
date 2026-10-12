`timescale 1ns/1ps
// Passive admitted-stream consumer. Never drives capture signals.
module background_producer #(
    parameter integer WIDTH=640, HEIGHT=480, CAMERA=1, DEPTH=64,
    parameter integer DEADLINE=16777216
) (
    input wire clk, rst, enable, quarantine,
    input wire [1:0] invalidate,
    input wire sof, pixel_valid, source_bad, raw_publish,
    input wire [15:0] pixel,
    input wire [31:0] source_sequence,
    output wire request,
    output wire [31:0] address,
    output wire [7:0] beats_minus_one,
    output wire [127:0] data,
    output wire [15:0] keep,
    input wire grant, take, retire, retire_bad,
    output wire idle,
    output wire [511:0] records
);
    localparam integer PIXELS=WIDTH*HEIGHT, OUT_PIXELS=PIXELS/4;
    // Decimation/last-selected arithmetic supports positive even geometry only.
    // Constant admission guard is synthesizable; unsupported shapes stay idle.
    localparam GEOMETRY_VALID=WIDTH>=2 && HEIGHT>=2 && WIDTH%2==0 && HEIGHT%2==0;
    localparam integer PAYLOAD_BYTES=OUT_PIXELS*2;
    localparam integer SLOT=CAMERA==5 ? 0 : (CAMERA<5 ? CAMERA : 5);
    localparam [31:0] DEST=32'h0a200000+SLOT*32'h80000;
    localparam integer PTR=$clog2(DEPTH);
    reg [127:0] fifo[0:DEPTH-1];
    reg [15:0] masks[0:DEPTH-1];
    reg [PTR-1:0] wr, rd;
    reg [PTR:0] count;
    reg [127:0] partial_word;
    reg [2:0] lane;
    reg active, failed, inflight, inflight_tag, next_bank, bank;
    reg full_frame, output_complete, raw_seen;
    reg [31:0] expected, position, x, y, age, burst_offset;
    reg [31:0] guard0, guard1, seq0, seq1;
    wire selected=active && !failed && !full_frame && pixel_valid && !x[0] && !y[0];
    wire last_selected=position==PIXELS-WIDTH-2;
    wire push=selected && (lane==7 || last_selected);
    wire pop=take && inflight && !inflight_tag;
    wire overflow=push && count==DEPTH && !pop;
    wire fail_now=source_bad || quarantine || overflow || age>=DEADLINE ||
                  (sof && active && !full_frame);
    wire payload_ready=count>=16 || (output_complete && count!=0);
    wire tag_ready=full_frame && raw_seen && count==0 && output_complete;
    wire tag_request=tag_ready && !payload_ready;
    wire [31:0] dst=DEST+(bank ? 32'h40000 : 0);
    assign request=active && !failed && !fail_now && !inflight &&
                   (payload_ready || tag_ready);
    assign address=dst+(tag_request ? ((PAYLOAD_BYTES+255)/256)*256 : burst_offset);
    assign beats_minus_one=tag_request ? 0 : (count>=16 ? 15 : count-1);
    assign data=inflight_tag ? {96'd0,expected} : fifo[rd];
    assign keep=inflight_tag ? 16'hffff : masks[rd];
    assign idle=!active && !inflight;
    wire [31:0] dimensions=(HEIGHT/2)*65536+WIDTH/2;
    localparam [31:0] BYTE_COUNT=PAYLOAD_BYTES, CAMERA_ID=CAMERA;
    assign records={
        DEST+32'h40000+((PAYLOAD_BYTES+255)/256)*256, dimensions,
        BYTE_COUNT, seq1, DEST+32'h40000, 32'd1, CAMERA_ID, guard1,
        DEST+((PAYLOAD_BYTES+255)/256)*256, dimensions,
        BYTE_COUNT, seq0, DEST, 32'd0, CAMERA_ID, guard0};
    always @(posedge clk) begin
        if(rst) begin
            wr<=0; rd<=0; count<=0; partial_word<=0; lane<=0;
            active<=0; failed<=0; inflight<=0; inflight_tag<=0;
            next_bank<=0; bank<=0; full_frame<=0; output_complete<=0; raw_seen<=0;
            expected<=0; position<=0; x<=0; y<=0; age<=0; burst_offset<=0;
            guard0<=0; guard1<=0; seq0<=0; seq1<=0;
        end else begin
            // Legacy on-demand jobs share this allowlist. Their pixels have no
            // autonomous publication record, so invalidate before core launch.
            if(invalidate[0]) guard0<={(guard0[31:2]+30'd1),2'b00};
            if(invalidate[1]) guard1<={(guard1[31:2]+30'd1),2'b00};
            if(GEOMETRY_VALID && sof && enable && !source_bad && !quarantine && !active && !inflight) begin
                active<=1; failed<=0; bank<=next_bank; next_bank<=!next_bank;
                expected<=source_sequence+1; position<=0; x<=0; y<=0; age<=0;
                wr<=0; rd<=0; count<=0; partial_word<=0; lane<=0; burst_offset<=0;
                full_frame<=0; output_complete<=0; raw_seen<=0;
                if(next_bank) begin guard1<={(guard1[31:2]+30'd1),2'b01}; seq1<=source_sequence+1; end
                else begin guard0<={(guard0[31:2]+30'd1),2'b01}; seq0<=source_sequence+1; end
                // SOF may accompany the first admitted pixel. Capture (0,0)
                // here because the active block sees the previous active bit.
                if(pixel_valid) begin
                    position<=1; x<=1;
                    partial_word<={112'd0,pixel}; lane<=1;
                    if(OUT_PIXELS==1) begin
                        fifo[0]<={112'd0,pixel}; masks[0]<=16'h0003;
                        wr<=1; count<=1; partial_word<=0; lane<=0;
                        output_complete<=1;
                    end
                end
            end
            if(active) begin
                if(age<DEADLINE) age<=age+1;
                if(raw_publish && source_sequence==expected) raw_seen<=1;
                if(fail_now) failed<=1;
                if(pixel_valid && !failed && !full_frame) begin
                    position<=position+1;
                    if(x==WIDTH-1) begin x<=0; y<=y+1; end else x<=x+1;
                    if(position==PIXELS-1) full_frame<=1;
                    if(selected) begin
                        partial_word[lane*16 +:16]<=pixel;
                        if(push && !overflow) begin
                            fifo[wr]<=partial_word & ((128'd1 << (lane*16))-1) |
                                      ({112'd0,pixel} << (lane*16));
                            masks[wr]<=16'hffff >> ((7-lane)*2);
                            wr<=wr+1; partial_word<=0; lane<=0;
                        end else lane<=lane+1;
                        if(last_selected) output_complete<=1;
                    end
                end
                if(pop) rd<=rd+1;
                case({push && !overflow && !failed, pop})
                    2'b10: count<=count+1;
                    2'b01: count<=count-1;
                    default: ;
                endcase
                if(grant) begin inflight<=1; inflight_tag<=tag_request; end
                if(retire) begin
                    inflight<=0;
                    if(retire_bad) failed<=1;
                    else if(inflight_tag && !failed && !fail_now) begin
                        active<=0;
                        if(bank) guard1[1:0]<=2'b10; else guard0[1:0]<=2'b10;
                    end else burst_offset<=burst_offset+256;
                end
                // Only discard FIFO after the announced burst has retired.
                if((failed || fail_now || (retire && retire_bad)) &&
                   (!inflight || retire)) begin
                    active<=0; count<=0; lane<=0;
                    if(bank) guard1[1:0]<=0; else guard0[1:0]<=0;
                end
            end
        end
    end
endmodule
