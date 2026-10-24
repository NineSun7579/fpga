// Passive motion subsystem and coherent descriptor in the writer AXI clock.
// Source sequence and RAW retired tag have independent origins. Bit1 remains
// clear until a future per-bank association implementation proves alignment.
module motion_runtime_tap #(
    parameter integer WIDTH=640, HEIGHT=480,
    parameter [31:0] TRANSPORT_GEOMETRY=32'h028001e0,
    parameter [31:0] FRAME_BYTES=32'd614400
) (
    input wire clk, rst_n,
    input wire hd_mode, vga_mode, parked,
    input wire [15:0] pixel_rgb565,
    input wire pixel_valid, vsync,
    input wire [31:0] raw_retired_tag,
    input wire [1:0] published_banks,
    output wire [319:0] motion_record,
    output wire [191:0] frame_metadata
);
    wire disabled=hd_mode || parked;
    wire [319:0] latest;
    reg disabled_q;
    reg [31:0] epoch;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin disabled_q<=0; epoch<=0; end
        else begin
            disabled_q<=disabled;
            if(disabled_q!=disabled) epoch<=epoch+1'b1;
        end
    end
    // Registered disable cuts the lease decode out of async reset fanout.
    // Release may coincide with VSYNC/pixel0: wait for low, then a fresh start.
    // Otherwise a lost pixel plus tolerated trailing dummy can shift history.
    reg motion_armed;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) motion_armed<=0;
        else if(disabled || disabled_q) motion_armed<=0;
        else if(!vsync) motion_armed<=1;
    end
    motion_stream_adapter #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) adapter (
        .clk(clk),.rst_n(rst_n && !disabled_q),.pixel_rgb565(pixel_rgb565),
        .pixel_valid(pixel_valid && motion_armed),.vsync(vsync && motion_armed),.motion_record(latest));
    assign motion_record=disabled ? 320'b0 : latest;
    assign frame_metadata={epoch,30'b0,published_banks,
        28'b0,parked,hd_mode,1'b0,!disabled,
        (hd_mode ? 32'd1843200 : (vga_mode ? 32'd614400 : FRAME_BYTES)),
        (hd_mode ? 32'h050002d0 : (vga_mode ? 32'h028001e0 : TRANSPORT_GEOMETRY)),raw_retired_tag};
endmodule
