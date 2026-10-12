`timescale 1ns/1ps
// Six passive producers and one fair, single-outstanding burst writer.
module background_six #(parameter WIDTH=640, HEIGHT=480, DEADLINE=16777216) (
    input wire clk, rst, enable,
    input wire [11:0] invalidate,
    input wire [5:0] sof, pixel_valid, source_bad, raw_publish,
    input wire [95:0] pixels,
    input wire [191:0] source_sequence,
    output wire quiescent,
    output reg quarantine,
    output wire [3071:0] records,
    output reg [31:0] awaddr,
    output reg [7:0] awlen,
    output wire awvalid,
    input wire awready,
    output wire [127:0] wdata,
    output wire [15:0] wstrb,
    output wire wvalid, wlast,
    input wire wready,
    input wire [1:0] bresp,
    input wire bvalid,
    output wire bready
);
    // One AXI-clock tap boundary: data and its frame/publication identity travel
    // together. This passive stage never feeds back into the RAW capture path.
    reg [5:0] tap_sof, tap_valid, tap_bad, tap_publish;
    reg [95:0] tap_pixels;
    reg [191:0] tap_sequence;
    always @(posedge clk) begin
        if(rst) begin
            tap_sof<=0; tap_valid<=0; tap_bad<=0; tap_publish<=0;
            tap_pixels<=0; tap_sequence<=0;
        end else begin
            tap_sof<=sof; tap_valid<=pixel_valid; tap_bad<=source_bad;
            tap_publish<=raw_publish; tap_pixels<=pixels;
            tap_sequence<=source_sequence;
        end
    end
    wire [5:0] request, producer_idle;
    wire [191:0] address;
    wire [47:0] lengths;
    wire [767:0] data;
    wire [95:0] keep;
    reg active, aw_pending, w_pending;
    reg [2:0] owner, next_camera;
    reg [7:0] beat;
    reg [2:0] choice;
    reg found;
    integer k, candidate;
    always @* begin
        found=0; choice=0; candidate=0;
        for(k=0;k<6;k=k+1) begin
            candidate=next_camera+k;
            if(candidate>=6) candidate=candidate-6;
            if(!found && request[candidate]) begin choice=candidate; found=1; end
        end
    end
    wire launch=!active && !quarantine && found;
    wire retire=active && bvalid && bready;
    assign awvalid=active && aw_pending;
    assign wvalid=active && w_pending;
    assign wdata=data[owner*128 +:128];
    assign wstrb=keep[owner*16 +:16];
    assign wlast=beat==awlen;
    assign bready=active && !aw_pending && !w_pending;
    assign quiescent=&producer_idle && !active;
    genvar c;
    generate for(c=0;c<6;c=c+1) begin: cameras
        background_producer #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.CAMERA(c+1),.DEADLINE(DEADLINE)) producer (
            .clk(clk),.rst(rst),.enable(enable),.quarantine(quarantine),
            .invalidate(invalidate[c*2 +:2]),
            .sof(tap_sof[c]),.pixel_valid(tap_valid[c]),.source_bad(tap_bad[c]),
            .pixel(tap_pixels[c*16 +:16]),.raw_publish(tap_publish[c]),
            .source_sequence(tap_sequence[c*32 +:32]),
            .request(request[c]),.address(address[c*32 +:32]),
            .beats_minus_one(lengths[c*8 +:8]),.data(data[c*128 +:128]),
            .keep(keep[c*16 +:16]),.idle(producer_idle[c]),
            .records(records[c*512 +:512]),
            .grant(launch && choice==c),.take(wvalid && wready && owner==c),
            .retire(retire && owner==c),.retire_bad(bresp!=0));
    end endgenerate
    always @(posedge clk) begin
        if(rst) begin
            quarantine<=0; active<=0; aw_pending<=0; w_pending<=0;
            owner<=0; next_camera<=0; beat<=0; awaddr<=0; awlen<=0;
        end else begin
            if(launch) begin
                active<=1; owner<=choice; aw_pending<=1; w_pending<=1; beat<=0;
                awaddr<=address[choice*32 +:32]; awlen<=lengths[choice*8 +:8];
                next_camera<=choice==5 ? 0 : choice+1;
            end
            if(awvalid && awready) aw_pending<=0;
            if(wvalid && wready) begin
                if(wlast) w_pending<=0; else beat<=beat+1;
            end
            if(retire) begin active<=0; if(bresp!=0) quarantine<=1; end
        end
    end
endmodule
