`timescale 1ns/1ps
module background_adapter_tb #(parameter FAULT=0);
    reg clk=0; always #5 clk=!clk;
    reg rst=1;
    reg [5:0] sof=0, pv=0, publish=0;
    reg [95:0] pixels=0;
    reg [191:0] raw_sequence={6{32'd1}};
    wire [5:0] hold;
    reg [31:0] host_awaddr=0,host_araddr=0;
    reg [127:0] host_wdata=0;
    reg [15:0] host_wstrb=16'hffff;
    reg host_awvalid=0,host_wvalid=0,host_arvalid=0;
    wire host_awready,host_wready,host_bvalid,host_arready,host_rvalid;
    wire [1:0] host_bresp,host_rresp;
    wire [127:0] host_rdata;
    wire [31:0] ra,wa;
    wire [7:0] rl,wl;
    wire rav,wav,wv,wlast,bready,rready;
    wire [127:0] wd;
    wire [15:0] ws;
    reg rv=0,bv=0;
    reg [1:0] bresp=0;
    reg [7:0] rleft=0;
    integer cycle=0,left=0,beat=0,bdelay=0,camera=0,slot=0,offset=0;
    integer rgb_beats=0,bg_beats=0,tags=0,aws=0,bs=0;
    reg transaction=0;
    reg legacy_thumbnail=0;
    reg [31:0] saved_address;
    wire arready=!rv && cycle%3!=0;
    wire awready=!transaction && !bv && cycle%5!=0;
    wire wready=transaction && left>0 && cycle%4!=0;
    wire [1:0] record_guard=dut.bg_records[(camera-1)*512 +:2];
    delivery_top_adapter #(.WIDTH(32),.HEIGHT(16),.OUT_HEIGHT(16),.TOP_ROWS(0)) dut (
        .clk(clk),.rst(rst),.capture_hold(hold),
        .bg_sof(sof),.bg_valid(pv),.bg_bad(6'd0),.bg_raw_publish(publish),.bg_pixels(pixels),
        .camera_prev_base({32'h01c00000,32'h01800000,32'h01400000,32'h01000000,32'h00c00000,32'h00800000}),
        .camera_bank0({32'h01c00000,32'h01800000,32'h01400000,32'h01000000,32'h00c00000,32'h00800000}),
        .camera_bank1({32'h01e00000,32'h01a00000,32'h01600000,32'h01200000,32'h00e00000,32'h00a00000}),
        .camera_sequence(raw_sequence),.camera_published(12'hfff),.camera_writer_idle(6'h3f),
        .camera_pending(6'd0),.camera_flush(6'd0),.camera_dma_idle(6'h3f),
        .camera_cmd_valid(6'd0),.camera_awvalid(6'd0),.camera_wvalid(6'd0),.camera_abort(6'd0),
        .s_axi_awid(7'd0),.s_axi_awaddr(host_awaddr),.s_axi_awlen(8'd0),.s_axi_awsize(3'd4),
        .s_axi_awburst(2'd1),.s_axi_awlock(1'b0),.s_axi_awcache(4'd0),.s_axi_awprot(3'd0),
        .s_axi_awqos(4'd0),.s_axi_awregion(4'd0),.s_axi_awvalid(host_awvalid),.s_axi_awready(host_awready),
        .s_axi_wdata(host_wdata),.s_axi_wstrb(host_wstrb),.s_axi_wlast(1'b1),
        .s_axi_wvalid(host_wvalid),.s_axi_wready(host_wready),.s_axi_bresp(host_bresp),
        .s_axi_bvalid(host_bvalid),.s_axi_bready(1'b1),
        .s_axi_arid(7'd0),.s_axi_araddr(host_araddr),.s_axi_arlen(8'd0),.s_axi_arsize(3'd4),
        .s_axi_arburst(2'd1),.s_axi_arlock(1'b0),.s_axi_arcache(4'd0),.s_axi_arprot(3'd0),
        .s_axi_arqos(4'd0),.s_axi_arregion(4'd0),.s_axi_arvalid(host_arvalid),.s_axi_arready(host_arready),
        .s_axi_rdata(host_rdata),.s_axi_rresp(host_rresp),.s_axi_rvalid(host_rvalid),.s_axi_rready(1'b1),
        .m_axi_araddr(ra),.m_axi_arlen(rl),.m_axi_arvalid(rav),.m_axi_arready(arready),
        .m_axi_rdata({8{16'hf800}}),.m_axi_rresp(2'd0),.m_axi_rlast(rleft==1),
        .m_axi_rvalid(rv && cycle%7!=0),.m_axi_rready(rready),
        .m_axi_awaddr(wa),.m_axi_awlen(wl),.m_axi_awvalid(wav),.m_axi_awready(awready),
        .m_axi_wdata(wd),.m_axi_wstrb(ws),.m_axi_wlast(wlast),.m_axi_wvalid(wv),.m_axi_wready(wready),
        .m_axi_bresp(bresp),.m_axi_bvalid(bv),.m_axi_bready(bready));
    task tick; @(negedge clk); endtask
    task check(input bit condition,input string message);
        if(!condition) $fatal(1,"%s",message);
    endtask
    task write_reg(input integer address,input integer value,input integer response=0);
        bit a,w;
        tick(); host_awaddr=32'h40020000+address; host_wdata=value;
        host_awvalid=1;host_wvalid=1;a=0;w=0;
        while(!a || !w) begin
            @(posedge clk); if(host_awready)a=1;if(host_wready)w=1;
            tick();if(a)host_awvalid=0;if(w)host_wvalid=0;
        end
        while(!host_bvalid) tick();
        check(host_bresp==response,"MMIO write response");tick();
    endtask
    task read_reg(input integer address,output reg [127:0] value);
        tick();host_araddr=32'h40020000+address;host_arvalid=1;
        do @(posedge clk); while(!host_arready);
        tick();host_arvalid=0;
        while(!host_rvalid) tick();
        check(host_rresp==0,"MMIO read response");value=host_rdata;tick();
    endtask
    reg aw_held=0,w_held=0;
    reg [39:0] saved_aw;
    reg [144:0] saved_w;
    integer i,idx,expected;
    always @(posedge clk) begin
        cycle<=cycle+1;
        if(rst) begin rv<=0;bv<=0;transaction<=0;aw_held<=0;w_held<=0;end
        else begin
            if(aw_held)check(wav && {wa,wl}===saved_aw,"AW changed during stall");
            if(w_held)check(wv && {wd,ws,wlast}===saved_w,"W changed during stall");
            aw_held<=wav && !awready;saved_aw<={wa,wl};
            w_held<=wv && !wready;saved_w<={wd,ws,wlast};
            if(rav && arready)begin rv<=1;rleft<=rl+1;end
            if(rv && cycle%7!=0 && rready)begin rleft<=rleft-1;if(rleft==1)rv<=0;end
            if(wav && awready)begin
                transaction<=1;left=wl+1;beat=0;saved_address=wa;aws=aws+1;
                if(wa>=32'h0a200000)begin
                    slot=(wa-32'h0a200000)/32'h80000;
                    camera=slot==0 ? 5 : (slot==5 ? 6 : slot);
                    offset=(wa-32'h0a200000)%32'h80000;
                    check(dut.bg_records[(camera-1)*512 +:2]==(legacy_thumbnail ? 0 : 1),"guard not invalid before shared AW");
                    check(offset<=256,"thumbnail escaped bank");
                end
            end
            if(wv && wready)begin
                check(left>0 && wlast==(left==1),"shared write ledger");
                check(ws==16'hffff,"shared write strobes");
                if(saved_address>=32'h0a200000)begin
                    if(legacy_thumbnail)begin
                        check(wd=={8{16'hf800}},"legacy thumbnail payload changed");
                        check(dut.bg_records[(camera-1)*512 +:32]==8,"legacy reuse did not increment generation");
                    end else if(offset==256)begin check(wd==128'd2,"thumbnail tag");tags=tags+1;end
                    else begin
                        for(i=0;i<8;i=i+1)begin
                            idx=beat*8+i;expected=camera*1000+(idx/16)*64+(idx%16)*2;
                            check(wd[i*16 +:16]==expected,"shared thumbnail pixel order");
                        end
                        bg_beats=bg_beats+1;
                    end
                end else begin
                    for(i=0;i<16;i=i+1)check(wd[i*8 +:8]==((rgb_beats*16+i)%3==0 ? 255 : 0),"RGB payload changed");
                    rgb_beats=rgb_beats+1;
                end
                beat=beat+1;left=left-1;
                if(left==0)begin
                    bdelay=offset==256 && saved_address>=32'h0a200000 ? 32 : 5;
                    bresp<=FAULT && saved_address>=32'h0a200000 && offset==256 ? 2 : 0;
                end
            end
            if(bdelay>0)begin
                bdelay=bdelay-1;
                if(saved_address>=32'h0a200000 && offset==256)check(record_guard==1,"valid before final tag B");
                if(bdelay==0)bv<=1;
            end
            if(bv && bready)begin bv<=0;transaction<=0;bs=bs+1;end
        end
    end
    reg [127:0] value;
    integer p,c;
    initial begin
        repeat(5)tick();rst=0;
        read_reg('h180,value);check(value==2,"reset disable/quiescence");
        host_wstrb=1;write_reg('h180,1,2);host_wstrb=16'hffff;
        write_reg('h180,2,2);write_reg('h180,1);
        write_reg('hb0,1);write_reg('h20,1,2); // destination lease conflicts
        write_reg('hb0,0);write_reg('h20,1);
        repeat(40)tick();if(!FAULT)write_reg('h20,3); // concurrent RGB command
        tick();sof=6'h3f;tick();sof=0;
        for(p=0;p<512;p=p+1)begin
            pv=6'h3f;for(c=0;c<6;c=c+1)pixels[c*16 +:16]=(c+1)*1000+p;
            tick();
        end
        pv=0;raw_sequence={6{32'd2}};publish=6'h3f;tick();publish=0;
        if(FAULT)write_reg('h20,3); // RGB remains active across bad thumbnail tag B
        write_reg('h180,0);
        repeat(1400)tick();
        read_reg('h180,value);check(value==(FAULT ? 6 : 2),"disable drain/quarantine status");
        read_reg('h10,value);check(value[3] && !value[2] && !value[4],"RGB command failed during background");
        check(rgb_beats==96 && aws==bs,"RGB/full B ledger");
        check(bg_beats==96 && tags==(FAULT ? 1 : 6),"six producers starved or fault failed to isolate");
        for(c=0;c<6;c=c+1)begin
            read_reg('h200+c*64,value);
            check(value[1:0]==(FAULT ? 0 : 2),"record publication after final B");
            check(value[63:32]==c+1 && value[95:64]==0,"record physical indexing");
            read_reg('h210+c*64,value);check(value[31:0]==2,"record RAW identity");
        end
        write_reg('h20,0);check(hold==0,"RGB lease not released");
        legacy_thumbnail=1;
        write_reg('hb0,1);write_reg('h20,1);
        write_reg('h180,1,2); // cannot steal an on-demand destination lease
        repeat(40)tick();write_reg('h20,3);
        repeat(600)tick();
        read_reg('h10,value);check(value[3] && !value[2] && !value[4],"legacy thumbnail behavior changed");
        read_reg('h300,value);check(value[31:0]==8,"legacy record stayed valid after overwrite");
        write_reg('h20,0);write_reg('hb0,0);
        $display("PASS background adapter fault=%0d: MMIO, full records, shared RGB pixels, six fairness, finalB, disable, quarantine",FAULT);
        $finish;
    end
    initial begin #1000000;$fatal(1,"adapter timeout");end
endmodule
