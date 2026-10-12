`timescale 1ns/1ps
module background_tb #(parameter W=32,H=16,FIRST_ON_SOF=0);
    localparam PIXELS=W*H, THUMB_PIXELS=PIXELS/4, PAYLOAD_BYTES=THUMB_PIXELS*2;
    reg clk=0; always #5 clk=!clk;
    reg rst=1, enable=0;
    reg [5:0] sof=0, valid=0, bad=0, pub=0;
    reg [95:0] pixels=0;
    reg [191:0] seq=0;
    wire quiet, quarantine;
    wire [3071:0] records;
    wire [31:0] awaddr;
    wire [7:0] awlen;
    wire av, wv, wl, br;
    wire [127:0] wd;
    wire [15:0] ws;
    reg ar=1, wr=1, bv=0;
    reg [1:0] resp=0;
    integer remaining=0, camera, bank, c, p, beat, n, index, expected, tags=0;
    reg [31:0] saved_address;
    reg waiting=0, inject=0;
    reg frame_bank=0;
    background_six #(.WIDTH(W),.HEIGHT(H),.DEADLINE(PIXELS+4096)) dut (
        .clk(clk),.rst(rst),.enable(enable),.invalidate(12'd0),.sof(sof),.pixel_valid(valid),
        .source_bad(bad),.raw_publish(pub),.pixels(pixels),.source_sequence(seq),
        .quiescent(quiet),.quarantine(quarantine),.records(records),
        .awaddr(awaddr),.awlen(awlen),.awvalid(av),.awready(ar),
        .wdata(wd),.wstrb(ws),.wvalid(wv),.wlast(wl),.wready(wr),
        .bresp(resp),.bvalid(bv),.bready(br));
    task tick; @(negedge clk); endtask
    reg [5:0] prev_sof=0, prev_valid=0, prev_bad=0, prev_pub=0;
    reg [95:0] prev_pixels=0;
    reg [191:0] prev_seq=0;
    always @(posedge clk) begin
        if(rst) begin
            prev_sof=0; prev_valid=0; prev_bad=0; prev_pub=0;
            prev_pixels=0; prev_seq=0;
        end else begin
            if({dut.tap_sof,dut.tap_valid,dut.tap_bad,dut.tap_publish,dut.tap_pixels,dut.tap_sequence}
               !=={prev_sof,prev_valid,prev_bad,prev_pub,prev_pixels,prev_seq})
                $fatal(1,"six-camera tap tuple lost one-clock alignment");
            prev_sof=sof; prev_valid=valid; prev_bad=bad; prev_pub=pub;
            prev_pixels=pixels; prev_seq=seq;
        end
    end
    task check(input bit condition, input string message);
        if(!condition) $fatal(1,"%s",message);
    endtask
    always @(posedge clk) begin
        if(rst) begin remaining=0; waiting=0; bv<=0; tags=0; end
        else begin
            if(av && ar) begin
                check(remaining==0 && !waiting,"overlapping writer transactions");
                saved_address=awaddr; remaining=awlen+1; beat=0;
                case((awaddr-32'h0a200000)/32'h80000)
                    0:camera=5; 1:camera=1; 2:camera=2; 3:camera=3; 4:camera=4; 5:camera=6;
                    default:$fatal(1,"destination outside allowlist");
                endcase
                bank=((awaddr-32'h0a200000)%32'h80000)/32'h40000;
                check(records[((camera-1)*2+bank)*256 +:2]==1,"guard did not invalidate BEFORE AW");
            end
            if(wv && wr) begin
                check(remaining>0,"W without announced AW in test");
                check(wl==(remaining==1),"incorrect WLAST");
                if((saved_address%32'h40000)==((PAYLOAD_BYTES+255)/256)*256) begin
                    check(ws==16'hffff,"incorrect tag strobe");
                    check(wd[31:0]==seq[(camera-1)*32 +:32],"tag sequence mismatch");
                    tags=tags+1;
                end else begin
                    for(n=0;n<8;n=n+1) begin
                        index=((saved_address%32'h40000)/256)*128+beat*8+n;
                        expected=(camera*1000+(index/(W/2))*W*2+(index%(W/2))*2)%65536;
                        check(ws[n*2 +:2]==(index<THUMB_PIXELS ? 3 : 0),"partial payload strobes");
                        if(index<THUMB_PIXELS)check(wd[n*16 +:16]==expected,"pixel decimation/order mismatch");
                    end
                end
                remaining=remaining-1; beat=beat+1;
                if(remaining==0) waiting=1;
            end
            if(waiting && !bv) begin bv<=1; resp<=inject ? 2 : 0; inject=0; end
            if(bv && br) begin bv<=0; waiting=0; end
        end
    end
    task frame(input bit disable_midway);
        tick();
        if(!FIRST_ON_SOF) begin sof=6'h3f; tick(); sof=0; end
        for(p=0;p<PIXELS;p=p+1) begin
            sof=(FIRST_ON_SOF && p==0) ? 6'h3f : 0;
            valid=6'h3f;
            for(c=0;c<6;c=c+1) pixels[c*16 +:16]=(c+1)*1000+p;
            if(disable_midway && p==16) enable=0;
            tick();
            if(p==PIXELS-W) for(c=0;c<6;c=c+1)
                check(records[c*512+frame_bank*256 +:2]!=2,"published before odd tail row");
        end
        valid=0; sof=0;
        repeat(64) tick();
        for(c=0;c<6;c=c+1) begin
            check(records[c*512+frame_bank*256 +:2]!=2,"published before RAW success");
            seq[c*32 +:32]=seq[c*32 +:32]+1;
        end
        pub=6'h3f; tick(); pub=0;
        repeat(512) tick();
        frame_bank=!frame_bank;
    endtask
    // Independent unserviceable consumer exercises overflow without RAW control.
    reg os=0, ov=0;
    wire oi;
    wire [511:0] orecs;
    background_producer #(.WIDTH(32),.HEIGHT(32),.DEPTH(4),.DEADLINE(2048)) overflow (
        .clk(clk),.rst(rst),.enable(1'b1),.quarantine(1'b0),.invalidate(2'd0),.sof(os),
        .pixel_valid(ov),.pixel(16'h1234),.source_bad(1'b0),.raw_publish(1'b0),
        .source_sequence(32'd0),.grant(1'b0),.take(1'b0),.retire(1'b0),
        .retire_bad(1'b0),.idle(oi),.records(orecs));
    reg ds=0;
    wire di; wire [511:0] drecs;
    background_producer #(.WIDTH(4),.HEIGHT(4),.DEADLINE(32)) deadline (
        .clk(clk),.rst(rst),.enable(1'b1),.quarantine(1'b0),.invalidate(2'd0),.sof(ds),
        .pixel_valid(1'b0),.pixel(16'd0),.source_bad(1'b0),.raw_publish(1'b0),
        .source_sequence(32'd0),.grant(1'b0),.take(1'b0),.retire(1'b0),
        .retire_bad(1'b0),.idle(di),.records(drecs));
    initial begin
        repeat(4) tick(); rst=0; enable=1;
        frame(1);
        check(quiet && !quarantine && tags==6,"disable did not drain all six fairly");
        for(c=0;c<6;c=c+1) check(records[c*512 +:32]==6,"bank0 valid generation");
        enable=1; seq={6{32'hffffffff}};
        frame(0);
        check(quiet && tags==12,"wrapped sequence frame incomplete");
        for(c=0;c<6;c=c+1) begin
            check(records[c*512+256 +:32]==6,"bank1 valid generation");
            check(records[c*512+384 +:32]==0,"sequence zero rejected");
        end
        inject=1;
        frame(0);
        check(quarantine && quiet,"bad B did not quarantine/drain");
        for(c=0;c<6;c=c+1) check(records[c*512 +:2]==0,"bad B left attempted bank valid");
        os=1; ds=1; tick(); os=0; ds=0; ov=1;
        repeat(1100) tick(); ov=0;
        check(oi && orecs[1:0]==0 && orecs[31:2]==1,"overflow validity failure");
        check(di && drecs[1:0]==0,"deadline validity failure");
        $display("PASS background: six fairness, RGB565, full tail, RAW barrier, disable drain, sequence0, badB, overflow, deadline");
        $finish;
    end
    initial begin #(40*PIXELS+200000); $fatal(1,"timeout"); end
endmodule
