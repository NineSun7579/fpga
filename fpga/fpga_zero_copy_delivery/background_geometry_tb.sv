`timescale 1ns/1ps
module background_geometry_tb;
    reg clk=0; always #5 clk=!clk;
    reg rst=1, sof=0, valid=0;
    wire [3:0] idle, request;
    wire [2047:0] records;
    genvar c;
    generate for(c=0;c<4;c=c+1) begin: shape
        // Odd width, odd height, zero width and zero height must stay idle.
        localparam W=c==0 ? 3 : (c==2 ? 0 : 4);
        localparam H=c==1 ? 3 : (c==3 ? 0 : 4);
        background_producer #(.WIDTH(W),.HEIGHT(H),.DEADLINE(64)) dut (
            .clk(clk),.rst(rst),.enable(1'b1),.quarantine(1'b0),.invalidate(2'd0),
            .sof(sof),.pixel_valid(valid),.source_bad(1'b0),.raw_publish(1'b1),
            .pixel(16'habcd),.source_sequence(32'd1),.request(request[c]),
            .grant(1'b0),.take(1'b0),.retire(1'b0),.retire_bad(1'b0),
            .idle(idle[c]),.records(records[c*512+:512]));
        always @(negedge clk) if(!rst) begin
            if(!idle[c] || request[c] || records[c*512+:32]!=0 || records[c*512+256+:32]!=0)
                $fatal(1,"unsupported geometry admitted frame W=%0d H=%0d",W,H);
        end
    end endgenerate
    initial begin
        repeat(4)@(negedge clk);rst=0;
        repeat(3) begin
            @(negedge clk);sof=1;valid=1;
            @(negedge clk);sof=0;
            repeat(32)@(negedge clk);valid=0;
        end
        $display("PASS background geometry: odd/zero width/height reject admission");
        $finish;
    end
endmodule
