`timescale 1ns/1ps
// Public-port driver adapted from cooperative_endpoint's frozen regression.
// Compile this same TB independently against the RTL wrapper and mapped top.
module tb_endpoint_wrapper;
    reg clk=0; always #5 clk=!clk;
    reg rst_n=0;
    reg [6:0] awid=0,arid=0;
    reg [31:0] awaddr=0,araddr=0;
    reg [7:0] awlen=0,arlen=0;
    reg [2:0] awsize=0,arsize=0,awprot=0,arprot=0;
    reg [1:0] awburst=0,arburst=0;
    reg awlock=0,arlock=0,awvalid=0,wvalid=0,arvalid=0;
    reg [127:0] wdata=0;
    reg [15:0] wstrb=0;
    reg wlast=0,bready=0,rready=0;
    wire awready,wready,bvalid,arready,rvalid,rlast;
    wire [6:0] bid,rid;
    wire [1:0] bresp,rresp;
    wire [127:0] rdata;
    reg input_valid=0,input_raw_valid=1;
    reg [31:0] input_src_addr=0,input_source_seq=0,input_generation=0;
    reg [2:0] input_camera=0;
    reg input_camera_bank=0;
    reg [63:0] input_lease_token=0;
    wire input_ready,input_claim,input_reject,cmd_valid;
    reg cmd_ready=1,bridge_busy=0,bridge_done=0,release_ready=1;
    wire [31:0] cmd_src_addr,cmd_dst_addr,cmd_frame_id;
    wire release_valid,busy;
    wire [31:0] release_addr,release_seq,release_gen;
    wire [2:0] release_camera;
    wire release_bank;
    wire [63:0] release_token;
    wire [1:0] bank0,bank1;
    integer cycle=0,op=0,trace,stim,rc,code,checks;
    reg [31:0] a[0:11];

    fpga_v8_endpoint_ctrl_synth dut (
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
        .input_valid(input_valid),.input_ready(input_ready),.input_raw_valid(input_raw_valid),
        .input_src_addr(input_src_addr),.input_source_seq(input_source_seq),
        .input_generation(input_generation),.input_camera(input_camera),
        .input_camera_bank(input_camera_bank),.input_lease_token(input_lease_token),
        .input_claim(input_claim),.input_reject(input_reject),
        .cmd_valid(cmd_valid),.cmd_ready(cmd_ready),.cmd_src_addr(cmd_src_addr),
        .cmd_dst_addr(cmd_dst_addr),.cmd_frame_id(cmd_frame_id),
        .bridge_busy(bridge_busy),.bridge_done(bridge_done),.bridge_error(1'b0),.bridge_cmd_error(1'b0),
        .src_release_valid(release_valid),.src_release_ready(release_ready),
        .src_release_addr(release_addr),.src_release_seq(release_seq),
        .src_release_generation(release_gen),.src_release_camera(release_camera),
        .src_release_camera_bank(release_bank),.src_release_token(release_token),
        .busy(busy),.bank0_state(bank0),.bank1_state(bank1)
    );

    reg bs=0,rs=0,cs=0,ls=0;
    reg [8:0] bsave;
    reg [137:0] rsave;
    reg [95:0] csave;
    reg [163:0] lsave;
    reg external_aw=0,external_ar=0;
    integer wcount=0,wtotal=0,rcount=0,rtotal=0;
    integer b_stall=0,r_stall=0,cmd_stall=0,release_stall=0,protocol_errors=0;
    integer claim_count=0,reject_count=0;
    task check_fail(input [511:0] message);
        begin
            protocol_errors=protocol_errors+1;
            $fdisplay(checks,"FAIL op=%0d cycle=%0d %0s",op,cycle,message);
        end
    endtask
    always @(negedge clk) cycle=cycle+1;
    always @(posedge clk) begin
        if(cycle>150000) $fatal(1,"watchdog op %0d",op);
        // Public outputs only: the mapped netlist has no forced/tied internal nets.
        if(cycle>1 && (^{awready,wready,bid,bresp,bvalid,arready,rid,rdata,rresp,rlast,rvalid,
            input_ready,input_claim,input_reject,cmd_valid,cmd_src_addr,cmd_dst_addr,cmd_frame_id,
            release_valid,release_addr,release_seq,release_gen,release_camera,release_bank,
            release_token,busy,bank0,bank1})===1'bx) check_fail("X/Z public output");
        if(rst_n) begin
            if(awvalid && awready) begin
                if(external_aw) check_fail("AW accepted before prior B consumption");
                external_aw=1;wtotal=awlen+1;
            end
            if(wvalid && wready) wcount=wcount+1;
            if(bvalid && (!external_aw || wcount!=wtotal)) check_fail("B before promised W drain");
            if(bvalid && bready) begin external_aw=0;wcount=0;end
            if(arvalid && arready) begin
                if(external_ar) check_fail("AR accepted before prior final R consumption");
                external_ar=1;rcount=0;rtotal=arlen+1;
            end
            if(rvalid && rready) begin
                rcount=rcount+1;
                if(!external_ar || rlast!=(rcount==rtotal)) check_fail("wrong R count/LAST");
                if(rlast) external_ar=0;
            end
            if(bs && (!bvalid || {bid,bresp}!==bsave)) check_fail("B changed under stall");
            if(rs && (!rvalid || {rid,rdata,rresp,rlast}!==rsave)) check_fail("R changed under stall");
            if(cs && (!cmd_valid || {cmd_src_addr,cmd_dst_addr,cmd_frame_id}!==csave)) check_fail("CMD changed under stall");
            if(ls && (!release_valid || {release_addr,release_seq,release_gen,release_camera,
                release_bank,release_token}!==lsave)) check_fail("RELEASE changed under stall");
            if(bvalid && !bready) b_stall=b_stall+1;
            if(rvalid && !rready) r_stall=r_stall+1;
            if(cmd_valid && !cmd_ready) cmd_stall=cmd_stall+1;
            if(release_valid && !release_ready) release_stall=release_stall+1;
            if(awvalid && awready) $fdisplay(trace,"%0d AW %x %x %x %x %x %x %x",op,awid,awaddr,awlen,awsize,awburst,awprot,awlock);
            if(wvalid && wready) $fdisplay(trace,"%0d W %x %x %x",op,wdata,wstrb,wlast);
            if(bvalid && bready) $fdisplay(trace,"%0d B %x %x",op,bid,bresp);
            if(arvalid && arready) $fdisplay(trace,"%0d AR %x %x %x %x %x %x %x",op,arid,araddr,arlen,arsize,arburst,arprot,arlock);
            if(rvalid && rready) $fdisplay(trace,"%0d R %x %x %x %x",op,rid,rdata,rresp,rlast);
            if(input_claim || input_reject) $fdisplay(trace,"%0d DESC %x %x %x %x %x %x %x",op,input_raw_valid,input_src_addr,input_source_seq,input_generation,input_camera,input_camera_bank,input_lease_token);
            if(input_claim) claim_count=claim_count+1;
            if(input_reject) reject_count=reject_count+1;
            if(cmd_valid && cmd_ready) $fdisplay(trace,"%0d CMD %x %x %x",op,cmd_src_addr,cmd_dst_addr,cmd_frame_id);
            if(release_valid && release_ready) $fdisplay(trace,"%0d RELEASE %x %x %x %x %x %x",op,release_addr,release_seq,release_gen,release_camera,release_bank,release_token);
        end else begin external_aw=0;external_ar=0;wcount=0;rcount=0;end
        bs=rst_n && bvalid && !bready;bsave={bid,bresp};
        rs=rst_n && rvalid && !rready;rsave={rid,rdata,rresp,rlast};
        cs=rst_n && cmd_valid && !cmd_ready;csave={cmd_src_addr,cmd_dst_addr,cmd_frame_id};
        ls=rst_n && release_valid && !release_ready;
        lsave={release_addr,release_seq,release_gen,release_camera,release_bank,release_token};
    end

    task tick(input integer n); repeat(n) @(negedge clk); endtask
    task reset_all;
        begin
            @(negedge clk);rst_n=0;awvalid=0;wvalid=0;arvalid=0;
            bready=0;rready=0;input_valid=0;bridge_busy=0;bridge_done=0;
            cmd_ready=1;release_ready=1;
            tick(4);rst_n=1;tick(3);$fdisplay(trace,"%0d RESET",op);
        end
    endtask
    task aw_send(input [31:0] addr,input integer len,size,burst,id,prot,delay_n);
        begin
            tick(delay_n);awaddr=addr;awlen=len;awsize=size;awburst=burst;
            awid=id;awprot=prot;awlock=id&1;awvalid=1;
            do @(posedge clk);while(!awready);
            @(negedge clk);awvalid=0;
            awaddr=32'hdeadbeef;awlen=8'hff;awsize=0;awburst=3;awid=7'h7f;awprot=7;awlock=0;
        end
    endtask
    function [127:0] payload(input [31:0] low,input integer beat);
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
    task finish_bridge(input integer release_hold);
        begin
            release_ready=0;bridge_busy=0;bridge_done=1;tick(1);bridge_done=0;
            wait(release_valid);tick(release_hold);release_ready=1;tick(4);
        end
    endtask

    initial begin
        trace=$fopen("actual.trace","w");stim=$fopen("stimulus.txt","r");
        checks=$fopen("protocol_checks.txt","w");
        if(!trace || !stim || !checks) $fatal(1,"files");
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
                    cmd_ready=0;input_raw_valid=a[7];input_valid=1;
                    do @(posedge clk);while(!input_ready);
                    @(negedge clk);input_valid=0;
                    if(a[7]) begin wait(cmd_valid);tick(a[8]);cmd_ready=1;wait(!cmd_valid);@(negedge clk);bridge_busy=1;end
                    else cmd_ready=1;
                    tick(3);
                end
                4: finish_bridge(a[0]);
                5: tick(a[0]);
                6: fork
                    begin aw_send(a[0],0,4,1,a[4],3,0);aw_send(a[1],0,4,0,a[4]+1,5,0);end
                    begin w_send(0,a[2],16'hffff,0,0);w_send(0,a[3],16'hffff,0,0);end
                    begin take_b(25);take_b(19);end
                join
                7: begin
                    // Only reset stages achievable through the wrapper ports.
                    case(a[0])
                        0: w_send(0,32'hcafebabe,16'hffff,0,0);
                        1: begin
                            fork aw_send(32'h40010100,0,4,1,7'h21,6,0);w_send(0,32'habcdef01,16'hffff,0,0);join
                            wait(bvalid);
                        end
                        4: begin ar_send(32'h40010000,0,4,1,7'h22,4);wait(rvalid);end
                        6: fork aw_send(32'h40010130,255,4,1,7'h24,1,0);w_send(31,1,16'hffff,2,0);join
                        7: aw_send(32'h40010100,0,4,1,7'h25,3,0);
                        default: $fatal(1,"unreachable internal reset phase");
                    endcase
                    tick(31);reset_all();
                end
                8: fork
                    write_one(a[0],0,4,1,a[4],a[1],16'hffff,0,0,2,23);
                    read_one(a[2],0,4,1,a[5],6,21);
                join
                9: begin
                    fork
                        aw_send(32'h40010110,0,4,1,a[0],7,0);
                        w_send(0,a[1],16'hffff,0,0);
                        ar_send(32'h40010020,0,4,1,a[2],1);
                    join
                    wait(bvalid && rvalid);tick(80);
                    fork take_b(17);take_r(0,19);join
                end
                10: fork
                    begin aw_send(32'h40010130,255,4,1,7'h30,4,0);aw_send(32'h40010100,0,4,1,7'h31,2,0);end
                    begin w_send(255,1,16'hffff,2,0);w_send(0,32'h13572468,16'hffff,0,0);end
                    begin take_b(27);take_b(23);end
                join
                11: begin
                    ar_send(a[0],0,4,1,a[1],a[2]);wait(rvalid);tick(7);
                    finish_bridge(23);take_r(0,7);
                end
                12: fork
                    begin ar_send(32'h400100c0,255,4,1,7'h32,3);ar_send(32'h40010000,0,4,0,7'h33,5);end
                    begin take_r(255,1);take_r(0,13);end
                join
                default: $fatal(1,"opcode");
            endcase
            tick(3);$fdisplay(trace,"%0d STATE %x %x %x %x",op,bank0,bank1,busy,input_ready);
        end
        tick(5);$fclose(trace);$fclose(stim);
        $fdisplay(checks,"errors=%0d B_stall=%0d R_stall=%0d CMD_stall=%0d RELEASE_stall=%0d claims=%0d rejects=%0d",protocol_errors,b_stall,r_stall,cmd_stall,release_stall,claim_count,reject_count);
        $fclose(checks);
        $display("WRAPPER_TB_COMPLETE ops=%0d cycles=%0d protocol_errors=%0d B_stall=%0d R_stall=%0d CMD_stall=%0d RELEASE_stall=%0d claims=%0d rejects=%0d",op,cycle,protocol_errors,b_stall,r_stall,cmd_stall,release_stall,claim_count,reject_count);
        $finish;
    end
endmodule
