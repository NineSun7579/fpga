`timescale 1ns/1ps
// Four local motion modules and six-slot ABI bank; no vendor top/IP simulation.
module tb_four_motion;
    reg clk=0;
    always #5 clk=~clk;
    reg rst_n=0;
    reg [3:0] valid=0, vs=0;
    reg [15:0] pixel[0:3];
    wire [1919:0] motion_records;
    assign motion_records[1919:1280]=640'b0;
    reg wr_en=0;
    reg [7:0] wr_offset=0, rd_offset=0;
    reg [31:0] wr_data=0;
    reg [3:0] wr_strb=0;
    wire [31:0] rd_data;
    reg success=0;
    integer phase=0, cycles=0, generation=0;
    integer publications[0:3];
    reg [319:0] previous[0:3];
    genvar g;
    generate for(g=0;g<4;g=g+1) begin: cameras
        motion_stream_adapter_tc04 adapter(.clk(clk),.rst_n(rst_n),
            .pixel_rgb565(pixel[g]),.pixel_valid(valid[g]),.vsync(vs[g]),
            .motion_record(motion_records[g*320 +: 320]));
        integer tick=0, end_tick=-100, timing_checks=0;
        reg prior_strobe=0;
        reg [319:0] prior_record=0;
        always @(posedge clk) begin
            tick=tick+1;
            if(rst_n) begin
                if(adapter.overflow_count!=0 || adapter.queued>16)
                    $fatal(1,"camera %0d unexpected FIFO overflow",g);
                if(adapter.core_end) end_tick=tick;
                prior_strobe=adapter.strobe;
                prior_record=motion_records[g*320 +: 320];
                #1;
                if(adapter.strobe !== (tick==end_tick+2))
                    $fatal(1,"camera %0d core publication must be end+2",g);
                if(adapter.strobe) timing_checks=timing_checks+1;
                if((motion_records[g*320 +: 320] !== prior_record) !== prior_strobe)
                    $fatal(1,"camera %0d adapter capture must be end+3",g);
            end
        end
    end endgenerate
    motion_register_bank bank(.clk(clk),.rst_n(rst_n),
        .motion_records(motion_records),.wr_en(wr_en),.wr_offset(wr_offset),
        .wr_data(wr_data),.wr_strb(wr_strb),.rd_offset(rd_offset),.rd_data(rd_data));

    function automatic integer block_id(input integer c);
        case(c)
            0: block_id=0; 1: block_id=17; 2: block_id=34; 3: block_id=51;
            default: block_id=0;
        endcase
    endfunction
    function automatic [319:0] expected(input integer f,input integer c);
        reg [191:0] bitmap;
        reg [31:0] bbox, counts, flags, seq;
        integer b,x,y;
        begin
            bitmap=0; bbox=0; counts=0; flags=1; seq=f;
            case(f)
                1: flags=0;
                3: begin
                    b=block_id(c); x=b%16; y=b/16;
                    bitmap[b]=1; bbox=(y<<12)|(y<<8)|(x<<4)|x;
                    counts=32'h00000801; flags=3;
                end
                4,6,7,9: begin
                    bitmap={192{1'b1}}; bbox=32'h0000b0f0;
                    counts=(f==4)?32'h004af8c0:32'h004b00c0;
                    flags=3;
                    if(f==7 && c==2) seq=6;
                end
                8: if(c==2) flags=4;
                default: begin end
            endcase
            expected={bitmap,bbox,counts,flags,seq};
        end
    endfunction
    // Oracle checks the complete packet at every publication, without DUT work state.
    always @(posedge clk) begin
        cycles=cycles+1;
        if(cycles>10000000) $fatal(1,"10M cycle watchdog");
        #1;
        if(rst_n) begin
            if(motion_records[1919:1280] !== 640'b0)
                $fatal(1,"unused camera indices 4/5 must remain zero");
            for(integer c=0;c<4;c=c+1) begin
                if(motion_records[c*320 +: 320] !== previous[c]) begin
                    if(motion_records[c*320 +: 320] !== expected(phase,c))
                        $fatal(1,"atomic record camera=%0d phase=%0d actual=%h expected=%h",
                            c,phase,motion_records[c*320 +: 320],expected(phase,c));
                    previous[c]=motion_records[c*320 +: 320];
                    publications[c]=publications[c]+1;
                end
            end
        end
    end
    task automatic idle_camera(input integer c,input integer n);
        repeat(n) begin @(negedge clk); valid[c]=0; vs[c]=0; pixel[c]=0; end
    endtask
    task automatic image(input integer c,input integer f);
        integer n,i,x,y,b;
        reg white;
        begin
            // Three distinct intermittent streams and uninterrupted camera 0.
            // Camera 0 starts with VSYNC coincident with pixel zero.
            if(c!=0) begin @(negedge clk); vs[c]=1; valid[c]=0; end
            n=(f==7 && c==2)?123:640*480;
            b=block_id(c);
            for(i=0;i<n;i=i+1) begin
                x=i%640; y=i/640;
                white=(f==4 || f==5 || f==7 || f==8);
                if(f==3) white=(y==(b/16)*40 && x>=(b%16)*40 &&
                    x<(b%16)*40+32 && x%4==0);
                @(negedge clk);
                valid[c]=1; vs[c]=(c==0 && i==0); pixel[c]=white?16'hffff:0;
                if(c>0 && i%(71+c*13)==(c*7)) idle_camera(c,c%3+1);
            end
            idle_camera(c,100);
        end
    endtask
    // Direct bank BFM; separate suite covers AXI bridge.
    task automatic select_word(input integer c,input integer w,input bit capture);
        @(negedge clk);
        wr_en=1; wr_offset=0; wr_strb=15;
        wr_data=(capture?32'h80000000:0)|(c<<8)|w;
        @(negedge clk); wr_en=0; wr_strb=0;
        if(capture) generation=generation+1;
    endtask
    task automatic read_word(input integer c,input integer w,input [319:0] held);
        select_word(c,w,0);
        rd_offset=8'h10; #1;
        if(rd_data !== held[w*32 +: 32])
            $fatal(1,"snapshot camera=%0d word=%0d actual=%h expected=%h",
                c,w,rd_data,held[w*32 +: 32]);
    endtask
    task automatic check_bank(input integer c,input [319:0] held);
        select_word(c,0,1);
        rd_offset=8'h00; #1;
        if(rd_data !== (c<<8)) $fatal(1,"camera selector mapping %0d",c);
        for(integer w=0;w<10;w=w+1) read_word(c,w,held);
        rd_offset=8'h20; #1;
        if(rd_data!==generation) $fatal(1,"capture generation");
    endtask
    task automatic run_images(input integer f);
        fork
            image(0,f); image(1,f); image(2,f); image(3,f);
        join
    endtask
    task automatic held_read(input integer c,input [319:0] held);
        for(integer w=0;w<5;w=w+1) read_word(c,w,held);
        // Span all four live publications with one frozen capture.
        repeat(340000) @(negedge clk);
        if(motion_records[c*320 +: 320] === held)
            $fatal(1,"snapshot did not span a live update camera %0d",c);
        for(integer w=5;w<10;w=w+1) read_word(c,w,held);
        for(integer w=0;w<10;w=w+1) read_word(c,w,held);
        rd_offset=8'h20; #1;
        if(rd_data!==generation) $fatal(1,"selector writes recaptured snapshot");
    endtask
    integer selected;
    reg [319:0] held;
    initial begin
        for(integer c=0;c<4;c=c+1) begin
            pixel[c]=0; previous[c]=0; publications[c]=0;
        end
        repeat(5) @(negedge clk); rst_n=1;
        rd_offset=8'h30; #1;
        if(rd_data!==32'h4d4f5431) $fatal(1,"bank signature");
        rd_offset=8'h40; #1;
        if(rd_data!==32'h01e00280) $fatal(1,"default geometry");
        rd_offset=8'h50; #1;
        if(rd_data!==32'h0c102804) $fatal(1,"default sample/block config");
        for(phase=1;phase<=10;phase=phase+1) begin
            if(phase==1) run_images(phase);
            else begin
                // Phases 2..5 freeze cameras 0..3; camera 2's abort is phase 7.
                selected=(phase-2)%4; held=expected(phase-1,selected);
                select_word(selected,0,1);
                if($test$plusargs("INJECT_FAULT") && phase==2) held[0]=~held[0];
                fork
                    run_images(phase);
                    held_read(selected,held);
                join
            end
            for(integer c=0;c<4;c=c+1) begin
                if(motion_records[c*320 +: 320] !== expected(phase,c))
                    $fatal(1,"final record camera=%0d phase=%0d",c,phase);
                check_bank(c,expected(phase,c));
            end
            check_bank(4,320'b0); check_bank(5,320'b0);
            $display("PASS four-motion phase %0d: four active records, frozen packet words 0..9, unused slots 4/5 zero",phase);
        end
        for(integer c=0;c<4;c=c+1)
            if(publications[c]!=(c==2?9:10)) $fatal(1,"publication count camera %0d",c);
        if(cameras[0].timing_checks!=10 || cameras[1].timing_checks!=10 ||
           cameras[2].timing_checks!=9 || cameras[3].timing_checks!=10)
            $fatal(1,"end+2 timing coverage");
        if(cameras[2].adapter.short_frame_count!=1 ||
           cameras[0].adapter.short_frame_count!=0 || cameras[1].adapter.short_frame_count!=0 ||
           cameras[3].adapter.short_frame_count!=0) $fatal(1,"short-frame channel isolation");
        success=1;
        $display("PASS tb_four_motion: four default 640x480 adapters, independent motion oracle, seed/static/short recovery, atomic records, end+2 core/end+3 capture, four frozen snapshots, unused indices 4/5 zero; cycles=%0d",cycles);
        $finish;
    end
endmodule
