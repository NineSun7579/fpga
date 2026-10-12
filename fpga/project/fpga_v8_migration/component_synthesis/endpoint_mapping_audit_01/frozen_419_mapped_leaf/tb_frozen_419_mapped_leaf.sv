`timescale 1ns/1ps
module tb_frozen_419_mapped_leaf;
    reg clk = 0; always #5 clk = !clk;
    reg rst_n = 0;
    reg [6:0] awid=0, arid=0;
    reg [31:0] awaddr=0, araddr=0;
    reg [7:0] awlen=0, arlen=0;
    reg [2:0] awsize=0, arsize=0, awprot=0, arprot=0;
    reg [1:0] awburst=0, arburst=0;
    reg awlock=0, arlock=0, awvalid=0, wvalid=0, arvalid=0;
    reg [127:0] wdata=0;
    reg [15:0] wstrb=0;
    reg wlast=0, bready=0, rready=0;
    wire awready,wready,bvalid,arready,rvalid,rlast;
    wire [6:0] bid,rid;
    wire [1:0] bresp,rresp;
    wire [127:0] rdata;
    wire [31:0] ma,md,ra;
    wire [2:0] mp,rp;
    wire [3:0] ms;
    wire mav,mwv,mbr,mrv,mrr,mar,mwr,mbv,mrar,mrrv;
    wire [1:0] mbp,mrp;
    wire [31:0] mrd;
    wire ca_ready,cw_ready,car_ready,cb_valid,cr_valid;
    wire [1:0] cb_resp,cr_resp;
    wire [31:0] cr_data;
    integer cycle=0,op=0,trace,stim,rc,code,seq=0;
    reg [31:0] a[0:11];
    reg block_aw=0,block_w=0,block_b=0,block_ar=0,block_r=0;
    wire ga=!block_aw && cycle%7>=3;
    wire gw=!block_w && cycle%11>=6;
    wire gb=!block_b && cycle%13>=8;
    wire gr_a=!block_ar && cycle%5==0;
    wire gr=!block_r && cycle%17>=11;
    assign mar=ca_ready && ga;
    assign mwr=cw_ready && gw;
    assign mbv=cb_valid && gb;
    assign mbp=cb_resp;
    assign mrar=car_ready && gr_a;
    assign mrrv=cr_valid && gr;
    assign mrd=cr_data; assign mrp=cr_resp;

    reg input_valid=0,input_raw_valid=1;
    reg [31:0] input_src_addr=0,input_source_seq=0,input_generation=0;
    reg [2:0] input_camera=0;
    reg input_camera_bank=0;
    reg [63:0] input_lease_token=0;
    wire input_ready,input_claim,input_reject,cmd_valid;
    reg cmd_ready=1,bridge_busy=0,bridge_done=0;
    wire [31:0] cmd_src_addr,cmd_dst_addr,cmd_frame_id;
    wire release_valid,busy;
    wire [31:0] release_addr,release_seq,release_gen;
    wire [2:0] release_camera;
    wire release_bank;
    wire [63:0] release_token;
    wire [1:0] bank0,bank1;

    fpga_v8_coop_axi128_endpoint dut (
        .clk(clk),.rst_n(rst_n),
        .s_axi_awid(awid),.s_axi_awaddr(awaddr),.s_axi_awlen(awlen),
        .s_axi_awsize(awsize),.s_axi_awburst(awburst),.s_axi_awlock(awlock),
        .s_axi_awcache(4'hf),.s_axi_awprot(awprot),.s_axi_awqos(4'hb),.s_axi_awregion(4'h5),
        .s_axi_awvalid(awvalid),.s_axi_awready(awready),
        .s_axi_wdata(wdata),.s_axi_wstrb(wstrb),.s_axi_wlast(wlast),
        .s_axi_wvalid(wvalid),.s_axi_wready(wready),
        .s_axi_bid(bid),.s_axi_bresp(bresp),.s_axi_bvalid(bvalid),.s_axi_bready(bready),
        .s_axi_arid(arid),.s_axi_araddr(araddr),.s_axi_arlen(arlen),
        .s_axi_arsize(arsize),.s_axi_arburst(arburst),.s_axi_arlock(arlock),
        .s_axi_arcache(4'hf),.s_axi_arprot(arprot),.s_axi_arqos(4'hc),.s_axi_arregion(4'h6),
        .s_axi_arvalid(arvalid),.s_axi_arready(arready),
        .s_axi_rid(rid),.s_axi_rdata(rdata),.s_axi_rresp(rresp),
        .s_axi_rlast(rlast),.s_axi_rvalid(rvalid),.s_axi_rready(rready),
        .m_axil_awaddr(ma),.m_axil_awprot(mp),.m_axil_awvalid(mav),.m_axil_awready(mar),
        .m_axil_wdata(md),.m_axil_wstrb(ms),.m_axil_wvalid(mwv),.m_axil_wready(mwr),
        .m_axil_bresp(mbp),.m_axil_bvalid(mbv),.m_axil_bready(mbr),
        .m_axil_araddr(ra),.m_axil_arprot(rp),.m_axil_arvalid(mrv),.m_axil_arready(mrar),
        .m_axil_rdata(mrd),.m_axil_rresp(mrp),.m_axil_rvalid(mrrv),.m_axil_rready(mrr)
    );
    fpga_v8_coop_control_axil control (
        .core_clk(clk),.rst_n(rst_n),
        .input_valid(input_valid),.input_ready(input_ready),.input_raw_valid(input_raw_valid),
        .input_src_addr(input_src_addr),.input_source_seq(input_source_seq),
        .input_generation(input_generation),.input_camera(input_camera),
        .input_camera_bank(input_camera_bank),.input_lease_token(input_lease_token),
        .input_claim(input_claim),.input_reject(input_reject),
        .cmd_valid(cmd_valid),.cmd_ready(cmd_ready),.cmd_src_addr(cmd_src_addr),
        .cmd_dst_addr(cmd_dst_addr),.cmd_frame_id(cmd_frame_id),
        .bridge_busy(bridge_busy),.bridge_done(bridge_done),.bridge_error(1'b0),.bridge_cmd_error(1'b0),
        .src_release_valid(release_valid),.src_release_ready(1'b1),
        .src_release_addr(release_addr),.src_release_seq(release_seq),
        .src_release_generation(release_gen),.src_release_camera(release_camera),
        .src_release_camera_bank(release_bank),.src_release_token(release_token),
        .busy(busy),.bank0_state(bank0),.bank1_state(bank1),
        .s_axil_awaddr(ma),.s_axil_awprot(mp),.s_axil_awvalid(mav && ga),.s_axil_awready(ca_ready),
        .s_axil_wdata(md),.s_axil_wstrb(ms),.s_axil_wvalid(mwv && gw),.s_axil_wready(cw_ready),
        .s_axil_bresp(cb_resp),.s_axil_bvalid(cb_valid),.s_axil_bready(mbr && gb),
        .s_axil_araddr(ra),.s_axil_arprot(rp),.s_axil_arvalid(mrv && gr_a),.s_axil_arready(car_ready),
        .s_axil_rdata(cr_data),.s_axil_rresp(cr_resp),.s_axil_rvalid(cr_valid),.s_axil_rready(mrr && gr)
    );

    reg bs=0,rs=0,as=0,ws=0,ars=0,cbs=0,crs=0;
    reg [8:0] bsave;
    reg [137:0] rsave;
    reg [34:0] asave,arsave;
    reg [35:0] wsave;
    reg [1:0] cbsave;
    reg [33:0] crsave;
    reg external_aw=0,external_bad=0,pre_aw_last=0,external_eligible=0;
    integer external_wcount=0,external_total=0;
    reg external_ar=0,external_read_eligible=0;
    integer external_rcount=0,external_rtotal=0;
    reg caw_seen=0,cw_seen=0;
    integer caw_first=0,cw_first=0;
    always @(negedge clk) cycle=cycle+1;
    always @(posedge clk) begin
        if (cycle>150000) $fatal(1,"watchdog op %0d",op);
        // Check every bit even while VALID=0 and during common reset.
        if (cycle>1) begin
            if ((^{awready,wready,bid,bresp,bvalid,arready,rid,rdata,rresp,rlast,rvalid,
                  ma,mp,mav,md,ms,mwv,mbr,ra,rp,mrv,mrr,
                  ca_ready,cw_ready,cb_valid,cb_resp,car_ready,cr_valid,cr_resp,cr_data,
                  input_ready,input_claim,input_reject,cmd_valid,cmd_src_addr,cmd_dst_addr,cmd_frame_id,
                  release_valid,release_addr,release_seq,release_gen,release_camera,release_bank,
                  release_token,busy,bank0,bank1}) === 1'bx) $fatal(1,"X/Z output op %0d",op);
        end
        if (rst_n) begin
            // Input-only protocol scoreboard: no DUT hierarchy or metadata.
            if (awvalid && awready) begin
                if(external_aw) $fatal(1,"next AW accepted before B consumption");
                external_aw=1;external_total=awlen+1;
                external_eligible=(awlen==0 && awsize==4 && awburst<2 &&
                    awaddr[3:0]==0 && awaddr>=32'h40010000 && awaddr<=32'h40010ff0);
                external_bad=external_wcount!=0 && pre_aw_last!=(external_total==1);
            end
            if(wvalid && wready) begin
                external_wcount=external_wcount+1;
                pre_aw_last=wlast;
                if(external_aw && wlast!=(external_wcount==external_total)) external_bad=1;
            end
            if((mav || mwv) && (!external_aw || !external_eligible || external_bad ||
                external_wcount!=external_total)) $fatal(1,"premature/invalid controller write side effect");
            if(bvalid && (!external_aw || external_wcount!=external_total)) $fatal(1,"B before promised W drain");
            if(bvalid && bready) begin
                external_aw=0;external_wcount=0;external_bad=0;
            end
            if(arvalid && arready) begin
                if(external_ar) $fatal(1,"next AR accepted before final R consumption");
                external_ar=1;external_rcount=0;external_rtotal=arlen+1;
                external_read_eligible=(arlen==0 && arsize==4 && arburst<2 &&
                    araddr[3:0]==0 && araddr>=32'h40010000 && araddr<=32'h40010ff0);
            end
            if(mrv && (!external_ar || !external_read_eligible)) $fatal(1,"invalid controller read side effect");
            if(rvalid && rready) begin
                external_rcount=external_rcount+1;
                if(!external_ar || rlast!=(external_rcount==external_rtotal)) $fatal(1,"wrong R count/LAST");
                if(rlast) external_ar=0;
            end
            if(mav && mar && !cw_seen && !(mwv && mwr)) caw_first=caw_first+1;
            if(mwv && mwr && !caw_seen && !(mav && mar)) cw_first=cw_first+1;
            if(mav && mar) caw_seen=1;
            if(mwv && mwr) cw_seen=1;
            if(cb_valid && mbr && gb) begin caw_seen=0;cw_seen=0;end
            if (bs && (!bvalid || {bid,bresp}!==bsave)) $fatal(1,"B changed under stall");
            if (rs && (!rvalid || {rid,rdata,rresp,rlast}!==rsave)) $fatal(1,"R changed under stall");
            if (as && (!mav || {ma,mp}!==asave)) $fatal(1,"ctrl AW changed under stall");
            if (ws && (!mwv || {md,ms}!==wsave)) $fatal(1,"ctrl W changed under stall");
            if (ars && (!mrv || {ra,rp}!==arsave)) $fatal(1,"ctrl AR changed under stall");
            if (cbs && (!cb_valid || cb_resp!==cbsave)) $fatal(1,"controller B changed under stall");
            if (crs && (!cr_valid || {cr_data,cr_resp}!==crsave)) $fatal(1,"controller R changed under stall");
            if (awvalid && awready) $fdisplay(trace,"%0d AW %x %x %x %x %x %x %x",op,awid,awaddr,awlen,awsize,awburst,awprot,awlock);
            if (wvalid && wready) $fdisplay(trace,"%0d W %x %x %x",op,wdata,wstrb,wlast);
            if (mav && mar) $fdisplay(trace,"%0d CAW %x %x",op,ma,mp);
            if (mwv && mwr) $fdisplay(trace,"%0d CW %x %x",op,md,ms);
            if (cb_valid && mbr && gb) $fdisplay(trace,"%0d CB %x",op,cb_resp);
            if (bvalid && bready) $fdisplay(trace,"%0d B %x %x",op,bid,bresp);
            if (arvalid && arready) $fdisplay(trace,"%0d AR %x %x %x %x %x %x %x",op,arid,araddr,arlen,arsize,arburst,arprot,arlock);
            if (mrv && mrar) $fdisplay(trace,"%0d CAR %x %x",op,ra,rp);
            if (cr_valid && mrr && gr) $fdisplay(trace,"%0d CR %x %x",op,cr_data,cr_resp);
            if (rvalid && rready) $fdisplay(trace,"%0d R %x %x %x %x",op,rid,rdata,rresp,rlast);
            if (input_claim || input_reject) $fdisplay(trace,"%0d DESC %x %x %x %x %x %x %x",op,input_raw_valid,input_src_addr,input_source_seq,input_generation,input_camera,input_camera_bank,input_lease_token);
            if (cmd_valid && cmd_ready) $fdisplay(trace,"%0d CMD %x %x %x",op,cmd_src_addr,cmd_dst_addr,cmd_frame_id);
            if (release_valid) $fdisplay(trace,"%0d RELEASE %x %x %x %x %x %x",op,release_addr,release_seq,release_gen,release_camera,release_bank,release_token);
        end else begin
            external_aw=0;external_wcount=0;external_bad=0;
            external_ar=0;external_rcount=0;
            caw_seen=0;cw_seen=0;
        end
        bs=rst_n && bvalid && !bready; bsave={bid,bresp};
        rs=rst_n && rvalid && !rready; rsave={rid,rdata,rresp,rlast};
        as=rst_n && mav && !mar; asave={ma,mp};
        ws=rst_n && mwv && !mwr; wsave={md,ms};
        ars=rst_n && mrv && !mrar; arsave={ra,rp};
        cbs=rst_n && cb_valid && !(mbr && gb); cbsave=cb_resp;
        crs=rst_n && cr_valid && !(mrr && gr); crsave={cr_data,cr_resp};
    end

    task tick(input integer n); repeat(n) @(negedge clk); endtask
    task reset_all;
        begin
            @(negedge clk); rst_n=0; awvalid=0; wvalid=0; arvalid=0;
            bready=0; rready=0; input_valid=0; bridge_busy=0; bridge_done=0;
            block_aw=0;block_w=0;block_b=0;block_ar=0;block_r=0;
            tick(4); rst_n=1; tick(3); $fdisplay(trace,"%0d RESET",op);
        end
    endtask
    task aw_send(input [31:0] addr,input integer len,size,burst,id,prot,delay_n);
        begin
            tick(delay_n); awaddr=addr;awlen=len;awsize=size;awburst=burst;
            awid=id;awprot=prot;awlock=id&1;awvalid=1;
            do @(posedge clk); while(!awready);
            @(negedge clk);awvalid=0;
            awaddr=32'hdeadbeef;awlen=8'hff;awsize=0;awburst=3;awid=7'h7f;awprot=7;awlock=0;
        end
    endtask
    function [127:0] payload(input [31:0] low,input integer beat);
        // Seeded pseudo-random upper 96 bits; independent Python duplicates only
        // the stimulus recipe, never reads any endpoint/controller internals.
        reg [31:0] x,y,z;
        begin
            x=32'hb71c249d ^ low ^ (beat*32'h9e3779b9);
            x=x ^ (x<<13);x=x ^ (x>>17);x=x ^ (x<<5);
            y=x ^ (x<<13);y=y ^ (y>>17);y=y ^ (y<<5);
            z=y ^ (y<<13);z=z ^ (z>>17);z=z ^ (z<<5);
            payload={x,y,z,low+beat};
        end
    endfunction
    task w_send(input integer len,input [31:0] low,input [15:0] strb,input integer lastmode,delay_n);
        integer i;
        begin
            tick(delay_n);
            for(i=0;i<=len;i=i+1) begin
                wdata=payload(low,i);wstrb=strb;
                wlast=(lastmode==0) ? i==len : ((lastmode==1) ? 1'b0 : i==0);
                wvalid=1;do @(posedge clk);while(!wready);
                @(negedge clk);wvalid=0;
            end
            wdata=128'hf00d;wstrb=0;wlast=0;
        end
    endtask
    task take_b(input integer hold_n);
        begin
            wait(bvalid);tick(hold_n);bready=1;
            do @(posedge clk);while(!bvalid);
            @(negedge clk);bready=0;
        end
    endtask
    task write_one(input [31:0] addr,input integer len,size,burst,id,input [31:0] low,
                   input [15:0] strb,input integer order_n,lastmode,prot,hold_n);
        begin
            fork
                aw_send(addr,len,size,burst,id,prot,order_n==1 ? 7 : 0);
                w_send(len,low,strb,lastmode,order_n==2 ? 7 : 0);
                take_b(hold_n);
            join
        end
    endtask
    task ar_send(input [31:0] addr,input integer len,size,burst,id,prot);
        begin
            araddr=addr;arlen=len;arsize=size;arburst=burst;arid=id;arprot=prot;arlock=id&1;arvalid=1;
            do @(posedge clk);while(!arready);
            @(negedge clk);arvalid=0;
            araddr=32'hbad00bad;arlen=8'hff;arsize=0;arburst=3;arid=7'h7f;arprot=7;arlock=0;
        end
    endtask
    task take_r(input integer len,hold_n);
        integer i;
        begin
            for(i=0;i<=len;i=i+1) begin
                wait(rvalid);tick(hold_n+(i%3));rready=1;
                do @(posedge clk);while(!rvalid);
                @(negedge clk);rready=0;
            end
        end
    endtask
    task read_one(input [31:0] addr,input integer len,size,burst,id,prot,hold_n);
        fork ar_send(addr,len,size,burst,id,prot);take_r(len,hold_n);join
    endtask

    initial begin
        trace=$fopen("actual.trace","w");stim=$fopen("stimulus.txt","r");
        if(!trace || !stim) $fatal(1,"files");
        while(!$feof(stim)) begin
            rc=$fscanf(stim,"%d %h %h %h %h %h %h %h %h %h %h %h %h\n",code,
                a[0],a[1],a[2],a[3],a[4],a[5],a[6],a[7],a[8],a[9],a[10],a[11]);
            if(rc!=13) $fatal(1,"bad stimulus %0d",rc);
            @(negedge clk);op=op+1;
            case(code)
                0: reset_all();
                1: write_one(a[0],a[1],a[2],a[3],a[4],a[5],a[6],a[7],a[8],a[9],a[10]);
                2: read_one(a[0],a[1],a[2],a[3],a[4],a[5],a[6]);
                3: begin
                    input_src_addr=a[0];input_source_seq=a[1];input_generation=a[2];
                    input_camera=a[3];input_camera_bank=a[4];input_lease_token={a[6],a[5]};
                    input_raw_valid=a[7];input_valid=1;
                    do @(posedge clk);while(!input_ready);
                    @(negedge clk);input_valid=0;
                    if(a[7]) begin wait(!cmd_valid);@(negedge clk);bridge_busy=1;end
                    tick(3);
                end
                4: begin bridge_busy=0;bridge_done=1;tick(1);bridge_done=0;tick(4);end
                5: tick(a[0]);
                6: begin
                    // Second AW/W are asserted while the first B is stalled.
                    fork
                        begin aw_send(a[0],0,4,1,a[4],3,0);aw_send(a[1],0,4,0,a[4]+1,5,0);end
                        begin w_send(0,a[2],16'hffff,0,0);w_send(0,a[3],16'hffff,0,0);end
                        begin take_b(25);take_b(19);end
                    join
                end
                7: begin
                    // Common reset abandons only the specifically staged request.
                    case(a[0])
                        0: w_send(0,32'hcafebabe,16'hffff,0,0);
                        1,2: begin
                            block_b=(a[0]==2);
                            fork aw_send(32'h40010100,0,4,1,7'h21,6,0);w_send(0,32'habcdef01,16'hffff,0,0);join
                            if(a[0]==1) wait(bvalid);else wait(cb_valid);
                        end
                        3,4: begin
                            block_r=(a[0]==3);
                            ar_send(32'h40010000,0,4,1,7'h22,4);
                            if(a[0]==3) wait(cr_valid);else wait(rvalid);
                        end
                        5: begin
                            block_w=1;
                            fork aw_send(32'h40010100,0,4,1,7'h23,2,0);w_send(0,32'h12345678,16'hffff,0,0);join
                            wait(!ca_ready);tick(40);
                        end
                        6: fork
                            aw_send(32'h40010130,255,4,1,7'h24,1,0);
                            w_send(31,1,16'hffff,2,0);
                        join
                        7: aw_send(32'h40010100,0,4,1,7'h25,3,0);
                    endcase
                    tick(31);reset_all();
                end
                8: fork
                    write_one(a[0],0,4,1,a[4],a[1],16'hffff,0,0,2,23);
                    read_one(a[2],0,4,1,a[5],6,21);
                join
                9: begin
                    // Keep the controller's real B/R outstanding for 80 cycles.
                    block_b=1;block_r=1;
                    fork
                        aw_send(32'h40010110,0,4,1,a[0],7,0);
                        w_send(0,a[1],16'hffff,0,0);
                        ar_send(32'h40010020,0,4,1,a[2],1);
                    join
                    wait(cb_valid && cr_valid);tick(80);block_b=0;block_r=0;
                    fork take_b(17);take_r(0,19);join
                end
                10: begin
                    // Pending next AW throughout the invalid 256-beat drain;
                    // the following W is presented immediately after beat 256.
                    fork
                        begin aw_send(32'h40010130,255,4,1,7'h30,4,0);aw_send(32'h40010100,0,4,1,7'h31,2,0);end
                        begin w_send(255,1,16'hffff,2,0);w_send(0,32'h13572468,16'hffff,0,0);end
                        begin take_b(27);take_b(23);end
                    join
                end
                11: begin
                    // Snapshot a live STATUS before completion, then change the
                    // live banks while the full R remains stalled.
                    ar_send(a[0],0,4,1,a[1],a[2]);wait(rvalid);tick(7);
                    bridge_busy=0;bridge_done=1;tick(1);bridge_done=0;tick(23);
                    take_r(0,7);
                end
                12: fork
                    begin ar_send(32'h400100c0,255,4,1,7'h32,3);ar_send(32'h40010000,0,4,0,7'h33,5);end
                    begin take_r(255,1);take_r(0,13);end
                join
                default: $fatal(1,"opcode");
            endcase
            tick(3);
            $fdisplay(trace,"%0d STATE %x %x %x %x",op,bank0,bank1,busy,input_ready);
        end
        tick(5);$fclose(trace);$fclose(stim);
        if(caw_first==0 || cw_first==0) $fatal(1,"missing independent controller AW/W ordering coverage");
        $display("ENDPOINT_TB_PASS ops=%0d cycles=%0d ctrl_AW_first=%0d ctrl_W_first=%0d",op,cycle,caw_first,cw_first);$finish;
    end
endmodule
