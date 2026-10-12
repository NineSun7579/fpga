`timescale 1ns/1ps
module tb_connected_mapping;
    reg clk=0;always #5 clk=!clk;
    reg rst_n=0;
    reg [6:0] awid=0,arid=0;
    reg [31:0] awaddr=0,araddr=0;
    reg [7:0] awlen=0,arlen=0;
    reg [2:0] awsize=4,arsize=4;
    reg [1:0] awburst=1,arburst=1;
    reg awvalid=0,wvalid=0,arvalid=0,bready=0,rready=0,wlast=0;
    reg [127:0] wdata=0;
    reg [15:0] wstrb=16'hffff;
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
    reg cmd_ready=0,bridge_busy=0,bridge_done=0;
    wire [31:0] cmd_src_addr,cmd_dst_addr,cmd_frame_id;
    wire release_valid,busy;
    wire [31:0] release_addr,release_seq,release_gen;
    wire [2:0] release_camera;
    wire release_bank;
    wire [63:0] release_token;
    wire [1:0] bank0,bank1;
    integer cycle=0,op=0,trace,stim,rc,code;
    integer bcount=0,rcount=0,desc_count=0,cmd_count=0,release_count=0;
    reg [31:0] a[0:11];
    fpga_v8_endpoint_ctrl_synth dut (
        .clk(clk),.rst_n(rst_n),
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
        .s_axi_awid(awid),.s_axi_awaddr(awaddr),.s_axi_awlen(awlen),
        .s_axi_awsize(awsize),.s_axi_awburst(awburst),.s_axi_awlock(1'b0),
        .s_axi_awcache(4'hf),.s_axi_awprot(3'h5),.s_axi_awqos(4'hb),.s_axi_awregion(4'h5),
        .s_axi_awvalid(awvalid),.s_axi_awready(awready),
        .s_axi_wdata(wdata),.s_axi_wstrb(wstrb),.s_axi_wlast(wlast),
        .s_axi_wvalid(wvalid),.s_axi_wready(wready),
        .s_axi_bid(bid),.s_axi_bresp(bresp),.s_axi_bvalid(bvalid),.s_axi_bready(bready),
        .s_axi_arid(arid),.s_axi_araddr(araddr),.s_axi_arlen(arlen),
        .s_axi_arsize(arsize),.s_axi_arburst(arburst),.s_axi_arlock(1'b0),
        .s_axi_arcache(4'hf),.s_axi_arprot(3'h6),.s_axi_arqos(4'hc),.s_axi_arregion(4'h6),
        .s_axi_arvalid(arvalid),.s_axi_arready(arready),
        .s_axi_rid(rid),.s_axi_rdata(rdata),.s_axi_rresp(rresp),
        .s_axi_rlast(rlast),.s_axi_rvalid(rvalid),.s_axi_rready(rready)
    );
    always @(negedge clk) cycle=cycle+1;
    always @(posedge clk) begin
        if(cycle>3000000) $fatal(1,"watchdog op=%0d",op);
        if(cycle>2 && (^{awready,wready,bvalid,bid,bresp,arready,rvalid,rid,rdata,rresp,rlast,
            input_ready,input_claim,input_reject,cmd_valid,cmd_src_addr,cmd_dst_addr,cmd_frame_id,
            release_valid,release_addr,release_seq,release_gen,release_camera,release_bank,release_token,
            bank0,bank1,busy})===1'bx) $fatal(1,"unknown public output op=%0d",op);
        if(rst_n) begin
            if(bvalid && bready) begin bcount=bcount+1;$fdisplay(trace,"%0d B %h %h",op,bid,bresp);end
            if(rvalid && rready) begin rcount=rcount+1;$fdisplay(trace,"%0d R %h %h %h %h",op,rid,rdata,rresp,rlast);end
            if(input_claim) begin desc_count=desc_count+1;$fdisplay(trace,"%0d DESC %h %h %h",op,input_src_addr,input_source_seq,input_generation);end
            if(cmd_valid && cmd_ready) begin cmd_count=cmd_count+1;$fdisplay(trace,"%0d CMD %h %h %h",op,cmd_src_addr,cmd_dst_addr,cmd_frame_id);end
            if(release_valid) begin release_count=release_count+1;$fdisplay(trace,"%0d RELEASE %h %h %h",op,release_addr,release_seq,release_gen);end
        end
    end
    task tick(input integer n);repeat(n) @(negedge clk);endtask
    task aw_send;
        begin
            tick(a[7]==1 ? 4 : 0);awaddr=a[0];awlen=a[1];awsize=a[2];awburst=a[3];awid=a[4];awvalid=1;
            do @(posedge clk);while(!awready);
            @(negedge clk);awvalid=0;awaddr=32'hdeadbeef;
        end
    endtask
    task w_send;
        integer i;
        begin
            tick(a[7]==2 ? 4 : 0);
            for(i=0;i<=a[1];i=i+1) begin
                wdata={96'hc7a41b236d195fe09124aa77,a[5]};wstrb=16'hffff;
                wlast=a[6]==0 ? i==a[1] : (a[6]==1 ? 1'b0 : i==0);wvalid=1;
                do @(posedge clk);while(!wready);
                @(negedge clk);wvalid=0;
            end
        end
    endtask
    task take_b;
        reg [8:0] frozen;
        begin
            wait(bvalid);frozen={bid,bresp};
            repeat(a[8]) begin @(negedge clk);if(!bvalid || {bid,bresp}!==frozen) $fatal(1,"B stall");end
            if(bid!==a[4] || bresp!==a[9]) $fatal(1,"B op=%0d addr=%h expected=%h actual=%h",op,a[0],a[9],bresp);
            bready=1;@(posedge clk);@(negedge clk);bready=0;
        end
    endtask
    task read_one;
        integer i;
        reg [137:0] frozen;
        begin
            araddr=a[0];arlen=a[1];arsize=a[2];arburst=a[3];arid=a[4];arvalid=1;
            do @(posedge clk);while(!arready);
            @(negedge clk);arvalid=0;araddr=32'hbad00bad;
            for(i=0;i<=a[1];i=i+1) begin
                wait(rvalid);frozen={rid,rdata,rresp,rlast};
                repeat(a[8]) begin @(negedge clk);if(!rvalid || {rid,rdata,rresp,rlast}!==frozen) $fatal(1,"R stall");end
                if(rid!==a[4] || rresp!==a[9] || rdata!=={96'd0,a[10]} || rlast!==(i==a[1]))
                    $fatal(1,"R op=%0d addr=%h expected=%h/%h actual=%h/%h",op,a[0],a[9],a[10],rresp,rdata);
                rready=1;@(posedge clk);@(negedge clk);rready=0;
            end
        end
    endtask
    task publish;
        begin
            input_src_addr=a[0];input_source_seq=a[1];input_generation=a[2];input_camera=a[3];
            input_camera_bank=a[4];input_lease_token={a[6],a[5]};input_raw_valid=1;input_valid=1;
            do @(posedge clk);while(!input_ready);
            @(negedge clk);input_valid=0;wait(cmd_valid);
            if(cmd_src_addr!==a[0] || cmd_frame_id!==a[1] || cmd_dst_addr!==a[7]) $fatal(1,"descriptor command");
            cmd_ready=1;@(posedge clk);@(negedge clk);cmd_ready=0;bridge_busy=1;tick(4);
            bridge_busy=0;bridge_done=1;tick(1);bridge_done=0;wait(release_valid);
            if({release_addr,release_seq,release_gen,release_camera,release_bank,release_token}!==
                {a[0],a[1],a[2],a[3][2:0],a[4][0],a[6],a[5]}) $fatal(1,"source release metadata");
            tick(3);
        end
    endtask
    initial begin
        trace=$fopen("actual.trace","w");stim=$fopen("stimulus.txt","r");
        if(!trace || !stim) $fatal(1,"files");
        while(!$feof(stim)) begin
            rc=$fscanf(stim,"%d %h %h %h %h %h %h %h %h %h %h %h %h\n",code,
                a[0],a[1],a[2],a[3],a[4],a[5],a[6],a[7],a[8],a[9],a[10],a[11]);
            if(rc!=13) $fatal(1,"stimulus");@(negedge clk);op=op+1;
            case(code)
                0: begin rst_n=0;tick(5);rst_n=1;tick(3);$fdisplay(trace,"%0d RESET",op);end
                1: fork aw_send();w_send();take_b();join
                2: read_one();
                3: publish();
                default:$fatal(1,"opcode");
            endcase
            tick(3);$fdisplay(trace,"%0d STATE %h %h %h %h",op,bank0,bank1,busy,input_ready);
        end
        $fclose(trace);$fclose(stim);
        $display("CONNECTED_MAPPING_PASS operations=%0d B=%0d R=%0d DESC=%0d CMD=%0d RELEASE=%0d cycles=%0d",op,bcount,rcount,desc_count,cmd_count,release_count,cycle);
        $finish;
    end
endmodule
