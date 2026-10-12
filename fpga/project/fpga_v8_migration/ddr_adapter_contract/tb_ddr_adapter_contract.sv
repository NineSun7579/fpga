`timescale 1ns/1ps
module tb_ddr_adapter_contract;
    reg clk=0,rst_n=0;
    always #5 clk=~clk;
    reg [3:0] awid=0;
    reg [31:0] awaddr=0,araddr=0;
    reg [7:0] awlen=0,arlen=0;
    reg [2:0] awsize=4,arsize=4;
    reg [1:0] awburst=1,arburst=1;
    reg awvalid=0,wvalid=0,wlast=0,bready=0,arvalid=0,rready=0;
    reg [127:0] wdata=0;
    reg [15:0] wstrb=16'hffff;
    reg [6:0] arid=0;
    wire awready,wready,bvalid,arready,rvalid,rlast;
    wire [3:0] bid;
    wire [1:0] bresp,rresp;
    wire [6:0] rid;
    wire [127:0] rdata;
    wire [7:0] flags;
    wire [4:0] water;
    wire wf_full,wf_empty,rf_full,rf_empty,wb,rb;
    wire [3:0] v_awid,v_awlen,v_wid,v_arid,v_arlen,v_rid;
    wire [27:0] v_awaddr,v_araddr;
    wire v_awvalid,v_awready,v_wready,v_wlast,v_arvalid,v_arready,v_rvalid,v_rlast;
    wire [127:0] v_wdata,v_rdata;
    wire [15:0] v_wstrb;
    reg hold_aw=0,hold_ar=0,hold_w=0,hold_r=0;
    reg corrupt_wid=0;
    wire vendor_wactive,vendor_ractive;
    fpga_v8_ddr_adapter dut (
        .clk(clk),.rst_n(rst_n),.s_awid(awid),.s_awaddr(awaddr),.s_awlen(awlen),
        .s_awsize(awsize),.s_awburst(awburst),.s_awvalid(awvalid),.s_awready(awready),
        .s_wdata(wdata),.s_wstrb(wstrb),.s_wlast(wlast),.s_wvalid(wvalid),.s_wready(wready),
        .s_bid(bid),.s_bresp(bresp),.s_bvalid(bvalid),.s_bready(bready),
        .s_arid(arid),.s_araddr(araddr),.s_arlen(arlen),.s_arsize(arsize),.s_arburst(arburst),.s_arvalid(arvalid),.s_arready(arready),
        .s_rid(rid),.s_rdata(rdata),.s_rresp(rresp),.s_rlast(rlast),.s_rvalid(rvalid),.s_rready(rready),
        .v_awid(v_awid),.v_awaddr(v_awaddr),.v_awlen(v_awlen),.v_awvalid(v_awvalid),.v_awready(v_awready),
        .v_wdata(v_wdata),.v_wstrb(v_wstrb),.v_wready(v_wready),.v_wlast(v_wlast),.v_wid(v_wid ^ (corrupt_wid?4'd8:4'd0)),
        .v_arid(v_arid),.v_araddr(v_araddr),.v_arlen(v_arlen),.v_arvalid(v_arvalid),.v_arready(v_arready),
        .v_rid(v_rid),.v_rdata(v_rdata),.v_rlast(v_rlast),.v_rvalid(v_rvalid),
        .error_flags(flags),.write_water_level(water),.write_fifo_full(wf_full),.write_fifo_empty(wf_empty),
        .read_fifo_full(rf_full),.read_fifo_empty(rf_empty),.write_busy(wb),.read_busy(rb)
    );
    fpga_v8_vendor_ddr_stub vendor (
        .clk(clk),.rst_n(rst_n),.awid(v_awid),.awaddr(v_awaddr),.awlen(v_awlen),.awvalid(v_awvalid),.awready(v_awready),
        .wdata(v_wdata),.wstrb(v_wstrb),.wready(v_wready),.wlast(v_wlast),.wid(v_wid),
        .arid(v_arid),.araddr(v_araddr),.arlen(v_arlen),.arvalid(v_arvalid),.arready(v_arready),
        .rid(v_rid),.rdata(v_rdata),.rlast(v_rlast),.rvalid(v_rvalid),
        .hold_aw(hold_aw),.hold_ar(hold_ar),.hold_w(hold_w),.hold_r(hold_r),.hold_final_output(1'b0),
        .write_active(vendor_wactive),.read_active(vendor_ractive),.consumed_words(),.emitted_words()
    );
    // The original top's ungated wr_en path using the actual generated FIFO.
    reg old_we=0,old_re=0;
    reg [143:0] old_wdata=0;
    wire [143:0] old_rdata;
    wire old_full,old_empty;
    wire [4:0] old_water;
    ddr_fifo16_w original_wfifo (
        .clk(clk),.rst(!rst_n),.wr_data(old_wdata),.wr_en(old_we),.wr_water_level(old_water),
        .full(old_full),.almost_full(),.rd_data(old_rdata),.rd_en(old_re),.empty(old_empty),.almost_empty()
    );
    reg [6:0] old_arid=0;
    reg [31:0] old_araddr=0;
    reg [7:0] old_arlen=0;
    reg old_arvalid=0,old_rready=0,old_varready=0,old_vrvalid=0,old_vrlast=0;
    reg [3:0] old_vrid=0;
    reg [127:0] old_vrdata=0;
    wire old_arready,old_varvalid,old_rlast,old_rvalid,old_rfull,old_rempty,old_inflight;
    wire [3:0] old_varid,old_varlen;
    wire [27:0] old_varaddr;
    wire [6:0] old_rid;
    wire [127:0] old_data;
    fpga_v8_top_read_route_snapshot original_read (
        .clk(clk),.rst_n(rst_n),.arid(old_arid),.araddr(old_araddr),.arlen(old_arlen),.arvalid(old_arvalid),.arready(old_arready),
        .vendor_arid(old_varid),.vendor_araddr(old_varaddr),.vendor_arlen(old_varlen),.vendor_arvalid(old_varvalid),.vendor_arready(old_varready),
        .vendor_rid(old_vrid),.vendor_rdata(old_vrdata),.vendor_rlast(old_vrlast),.vendor_rvalid(old_vrvalid),
        .rid(old_rid),.rdata(old_data),.rlast(old_rlast),.rvalid(old_rvalid),.rready(old_rready),
        .full(old_rfull),.empty(old_rempty),.rd_inflight(old_inflight)
    );
    integer cycles=0,write_tests=0,read_words=0,original_read_words=0,rejections=0,resets=0;
    integer f, n,phase;
    reg [127:0] held_data;
    reg [6:0] held_id;
    reg held_last;
    reg stalled_b=0,stalled_r=0,stalled_aw=0,stalled_ar=0;
    reg [5:0] held_b;
    reg [137:0] held_r;
    reg [35:0] held_aw,held_ar;
    function [127:0] word(input integer tx,beat);
        integer lane;
        for(lane=0;lane<16;lane=lane+1) word[lane*8+:8]=(tx*31+beat*7+lane*5)&255;
    endfunction
    function [127:0] expected_read(input [31:0] address);
        integer lane;
        for(lane=0;lane<16;lane=lane+1) expected_read[lane*8+:8]=((address>>4)*13+lane*17+31)&255;
    endfunction
    task tick(input integer count); repeat(count) @(negedge clk); endtask
    task reset_all;
        begin
            @(negedge clk); rst_n=0; awvalid=0; wvalid=0; bready=0; arvalid=0; rready=0;
            hold_aw=0;hold_ar=0;hold_w=0;hold_r=0; old_we=0;old_re=0;old_arvalid=0;
            corrupt_wid=0;
            old_rready=0;old_varready=0;old_vrvalid=0;old_vrlast=0;
            tick(5);rst_n=1;tick(3);resets=resets+1;
            if(wb || rb || bvalid || rvalid || !wf_empty || !rf_empty || flags!==0) $fatal(1,"common reset not clean");
        end
    endtask
    always @(posedge clk) begin
        cycles<=cycles+1;
        if(!rst_n) begin stalled_b=0;stalled_r=0;stalled_aw=0;stalled_ar=0; end
        else begin
            if($isunknown({awready,wready,bvalid,arready,rvalid,flags,water,wf_full,wf_empty,rf_full,rf_empty,wb,rb,v_awvalid,v_arvalid})) $fatal(1,"unknown adapter output");
            if(stalled_b && (!bvalid || {bid,bresp}!==held_b)) $fatal(1,"B unstable");
            if(stalled_r && (!rvalid || {rid,rdata,rresp,rlast}!==held_r)) $fatal(1,"R ID/data/response/last unstable");
            if(stalled_aw && (!v_awvalid || {v_awid,v_awaddr,v_awlen}!==held_aw)) $fatal(1,"vendor AW unstable");
            if(stalled_ar && (!v_arvalid || {v_arid,v_araddr,v_arlen}!==held_ar)) $fatal(1,"vendor AR unstable");
            stalled_b=bvalid&&!bready;held_b={bid,bresp};
            stalled_r=rvalid&&!rready;held_r={rid,rdata,rresp,rlast};
            stalled_aw=v_awvalid&&!v_awready;held_aw={v_awid,v_awaddr,v_awlen};
            stalled_ar=v_arvalid&&!v_arready;held_ar={v_arid,v_araddr,v_arlen};
            if(v_awvalid && water<({1'b0,v_awlen}+5'd1)) $fatal(1,"AW not fully staged");
            if(v_wready && wf_empty) $fatal(1,"vendor empty FIFO read");
            if(v_rvalid && rf_full) $fatal(1,"vendor R FIFO overflow");
        end
    end
    task accept_aw(input integer id,tx,beats);
        begin
            @(negedge clk);awid=id;awaddr=32'h00200000+tx*256;awlen=beats-1;awsize=4;awburst=1;awvalid=1;
            do @(posedge clk);while(!awready);
            @(negedge clk);awvalid=0;awid=0;awaddr=32'hdeadbeef;awlen=255;
        end
    endtask
    task send_words(input integer tx,beats, input bit bad_last);
        integer b;
        begin
            for(b=0;b<beats;b=b+1) begin
                tick(1+(b%3)); wdata=word(tx,b);wstrb=(b+1==beats)?16'h07ff:16'hffff;
                wlast=(b+1==beats)^bad_last;wvalid=1;
                do @(posedge clk);while(!wready);
                @(negedge clk);wvalid=0;
                if(b+1<beats && (v_awvalid || vendor_wactive || bvalid)) $fatal(1,"vendor started before complete W burst");
            end
        end
    endtask
    task retire_b(input integer id, input [1:0] response);
        begin
            wait(bvalid);@(negedge clk);
            repeat(13) begin tick(1);if(!bvalid || bid!==id || bresp!==response || awready) $fatal(1,"held B ID/response/ownership");end
            bready=1;tick(1);bready=0;tick(2);write_tests=write_tests+1;
        end
    endtask
    task write_burst(input integer id,tx,beats);
        begin
            accept_aw(id,tx,beats);tick(9);
            if(v_awvalid || vendor_wactive || bvalid) $fatal(1,"AW before W pulse staging");
            send_words(tx,beats,0);retire_b(id,0);
        end
    endtask
    task full_fifo_queued_write;
        begin
            hold_aw=1;accept_aw(1,20,16);send_words(20,16,0);wait(v_awvalid);tick(3);
            if(!wf_full || water!==16) $fatal(1,"candidate 16-word full staging");
            awid=4;awaddr='h00201500;awlen=0;awvalid=1;
            wdata=word(21,0);wstrb=16'h07ff;wlast=1;wvalid=1;
            tick(9);if(awready || wready || water!==16) $fatal(1,"queued AW/W captured into full current burst");
            hold_aw=0;wait(bvalid);tick(7);
            if(awready || wready || bid!==1 || bresp!==0) $fatal(1,"queued AW/W bypassed held B ownership");
            bready=1;tick(1);bready=0;write_tests=write_tests+1;
            do @(posedge clk);while(!awready);
            @(negedge clk);awvalid=0;
            do @(posedge clk);while(!wready);
            @(negedge clk);wvalid=0;
            retire_b(4,0);
        end
    endtask
    task accept_ar(input [6:0] id,input [31:0] addr,input integer beats);
        begin
            @(negedge clk);arid=id;araddr=addr;arlen=beats-1;arsize=4;arburst=1;arvalid=1;
            do @(posedge clk);while(!arready);
            @(negedge clk);arvalid=0;arid=7'h7f;araddr=32'hdeadbeef;arlen=255;
        end
    endtask
    task drain_read(input [6:0] id,input [31:0] addr,input integer beats);
        integer b;
        begin
            for(b=0;b<beats;b=b+1) begin
                rready=0;wait(rvalid);@(negedge clk);tick(2+b%3);
                if(rid!==id || rdata!==expected_read(addr+b*16) || rlast!==(b+1==beats) || rresp!==0) $fatal(1,"complete R route/data/last");
                $fwrite(f,"R %02x %08x %032x %0d\n",rid,addr+b*16,rdata,rlast);
                rready=1;@(posedge clk);@(negedge clk);rready=0;read_words=read_words+1;
            end
        end
    endtask
    task read_pair;
        begin
            accept_ar(7'h01,32'h00300000,16);
            wait(!vendor_ractive && vendor.emitted_words==16 && !v_rvalid);tick(4);
            if(!rf_full || !rb) $fatal(1,"16 unthrottleable R beats not safely buffered");
            arid=7'h21;araddr=32'h00300100;arlen=2;arvalid=1;
            tick(20);if(arready || rid!==7'h01 || !rb) $fatal(1,"late SID request retagged held R");
            drain_read(7'h01,32'h00300000,16);
            do @(posedge clk);while(!arready);
            @(negedge clk);arvalid=0;arid=7'h7f;
            drain_read(7'h21,32'h00300100,3);tick(3);
            accept_ar(7'h54,32'h00300200,2);drain_read(7'h54,32'h00300200,2);tick(3);
            accept_ar(7'h2f,32'h00300300,1);drain_read(7'h2f,32'h00300300,1);tick(3);
        end
    endtask
    task original_fifo_full;
        integer b;
        begin
            for(b=0;b<16;b=b+1) begin old_we=1;old_wdata={16'hffff,word(99,b)};tick(1);end
            if(!old_full || old_water!==16) $fatal(1,"official write FIFO capacity");
            old_wdata={16'hffff,128'hdeadbeef};tick(9);old_we=0;
            if(old_water!==16) $fatal(1,"ungated wr_en advanced full FIFO");
            for(b=0;b<16;b=b+1) begin
                if(old_rdata!=={16'hffff,word(99,b)}) $fatal(1,"ungated full write corrupted FIFO");
                old_re=1;tick(1);
            end
            old_re=0;tick(2);if(!old_empty) $fatal(1,"official FIFO full-stall drain");
            $display("ORIGINAL_WREN_FULL_SAFE words=16 blocked_valid_cycles=9 internal_full_gating=verified");
        end
    endtask
    task original_route;
        integer b;
        begin
            old_arid=7'h01;old_araddr='h00300000;old_arlen=15;old_arvalid=1;
            do @(posedge clk);while(!old_arready);
            @(negedge clk);old_arvalid=0;old_varready=1;tick(3);old_varready=0;
            for(b=0;b<16;b=b+1) begin
                old_vrid=1;old_vrdata=expected_read('h00300000+b*16);old_vrlast=b==15;old_vrvalid=1;tick(1);
            end
            old_vrvalid=0;old_vrlast=0;tick(3);
            if(old_inflight || !old_rfull || old_rempty) $fatal(1,"original route final vendor beat/full condition");
            old_arid=7'h54;old_araddr='h00301000;old_arlen=0;old_arvalid=1;
            tick(12);if(old_arready || old_rid!==7'h01) $fatal(1,"original FIFO gate failed to retain SID");
            for(b=0;b<16;b=b+1) begin
                tick(2);
                if(old_arready || old_rid!==7'h01 || old_data!==expected_read('h00300000+b*16) || old_rlast!==(b==15)) $fatal(1,"original held route data/last");
                old_rready=1;tick(1);old_rready=0;original_read_words=original_read_words+1;
            end
            do @(posedge clk);while(!old_arready);
            @(negedge clk);old_arvalid=0;old_varready=1;tick(3);old_varready=0;
            old_vrid=4;old_vrdata=expected_read('h00301000);old_vrlast=1;old_vrvalid=1;tick(1);old_vrvalid=0;tick(2);
            if(old_rid!==7'h54 || old_data!==expected_read('h00301000) || !old_rlast) $fatal(1,"original next SID route");
            old_rready=1;tick(1);old_rready=0;original_read_words=original_read_words+1;
            $display("ORIGINAL_READ_ROUTE_SAFE words=17 vendor_last_clears_inflight=1 fifo_empty_prevents_SID_reuse=1");
        end
    endtask
    task invalid_requests;
        integer which;
        begin
            for(which=0;which<6;which=which+1) begin
                awid=1;awaddr='h00200000;awlen=0;awsize=4;awburst=1;
                arid='h21;araddr='h00300000;arlen=0;arsize=4;arburst=1;
                case(which)
                    0:begin awlen=16;arlen=16;end
                    1:begin awaddr='h10000000;araddr='h10000000;end
                    2:begin awaddr='h00200001;araddr='h00300001;end
                    3:begin awsize=3;arsize=3;end
                    4:begin awburst=0;arburst=0;end
                    5:begin awaddr='h00200ff0;araddr='h00300ff0;awlen=1;arlen=1;end
                endcase
                awvalid=1;arvalid=1;tick(7);
                if(awready || arready || v_awvalid || v_arvalid || flags[1:0]!==3) $fatal(1,"invalid request truncated/launched");
                awvalid=0;arvalid=0;rejections=rejections+2;reset_all();
            end
            // Exact physical end is legal and preserves all 28 address bits.
            awid=15;awaddr='h0ffffff0;awlen=0;awsize=4;awburst=1;awvalid=1;
            do @(posedge clk);while(!awready);@(negedge clk);awvalid=0;
            send_words(5,1,0);wait(v_awvalid);if(v_awaddr!==28'hffffff0) $fatal(1,"physical upper address bits lost");
            retire_b(15,0);
        end
    endtask
    initial begin
        f=$fopen("read_trace.txt","w");reset_all();
        original_fifo_full();original_route();reset_all();
        // Concurrent independent reads/writes exercise FIFO directions together.
        fork
            begin write_burst(1,0,1);write_burst(4,1,2);write_burst(7,2,3);write_burst(15,3,16);end
            read_pair();
        join
        if(flags!==0) $fatal(1,"legal traffic diagnostics");
        full_fifo_queued_write();
        invalid_requests();
        corrupt_wid=1;accept_aw(4,22,2);send_words(22,2,0);retire_b(4,2);
        if(!flags[4]) $fatal(1,"vendor returned wrong ID not diagnosed");
        $display("VENDOR_ID_FAULT_PASS accepted_awid=4 vendor_wid=12 returned_bid=4 bresp=SLVERR");reset_all();
        // WLAST diagnostics do not mint B until the vendor has consumed its last beat.
        hold_w=1;accept_aw(1,6,3);send_words(6,3,1);wait(vendor_wactive);tick(8);
        if(bvalid) $fatal(1,"upstream WLAST minted early B");
        hold_w=0;retire_b(1,2);if(!flags[2]) $fatal(1,"WLAST error not flagged");reset_all();
        for(phase=0;phase<5;phase=phase+1) begin
            case(phase)
                0:begin accept_aw(1,7,3);send_words(7,1,0);end
                1:begin hold_aw=1;accept_aw(1,8,2);send_words(8,2,0);wait(v_awvalid);end
                2:begin hold_w=1;accept_aw(1,9,2);send_words(9,2,0);wait(vendor_wactive);end
                3:begin hold_r=1;accept_ar('h21,'h00300400,16);wait(vendor_ractive);end
                4:begin write_burst(1,10,1);accept_ar('h54,'h00300500,16);wait(!vendor_ractive && !v_rvalid);end
            endcase
            tick(6);reset_all();tick(9);if(bvalid || rvalid) $fatal(1,"ghost completion after reset");
        end
        write_burst(1,11,3);accept_ar('h21,'h00300600,16);drain_read('h21,'h00300600,16);
        accept_ar('h5f,'h0ffffff0,1);drain_read('h5f,'h0ffffff0,1);tick(3);
        // Final B outstanding reset independently of the earlier staging phases.
        accept_aw(4,12,1);send_words(12,1,0);wait(bvalid);tick(8);reset_all();
        write_burst(1,13,1);
        if(flags!==0 || wb || rb || !wf_empty || !rf_empty) $fatal(1,"final state not idle");
        $fclose(f);
        $display("ADAPTER_DIRECTED_PASS writes=%0d read_words=%0d original_read_words=%0d unsupported_rejections=%0d common_resets=%0d cycles=%0d",write_tests,read_words,original_read_words,rejections,resets,cycles);
        $finish;
    end
    initial begin repeat(100000) @(posedge clk);$fatal(1,"directed watchdog");end
endmodule
