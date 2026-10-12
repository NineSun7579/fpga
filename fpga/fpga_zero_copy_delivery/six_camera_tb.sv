`timescale 1ns/1ps
// Six real admission gates compete on every VSYNC. The lease registers receive
// their real hold vector; metadata and delayed B retirement are driven as the
// writer's externally observable contract would drive them.
module tb_six_camera_ownership;
    reg clk=0, rst=1;
    always #5 clk=~clk;
    reg [31:0] awaddr,wdata,araddr;
    reg [3:0] wstrb=4'hf;
    reg awvalid=0,wvalid=0,bready=0,arvalid=0,rready=0;
    wire awready,wready,arready,bvalid,rvalid;
    wire [1:0] bresp,rresp;
    wire [31:0] rdata;
    wire [5:0] hold;
    reg [191:0] prev,bank0,bank1,seqno;
    reg [11:0] published;
    reg [5:0] writer_idle=6'h3f,pending=0,flush=0,dma_idle=6'h3f;
    wire [5:0] cmdv,awv,wv,abrt;
    assign cmdv=0; assign awv=0; assign wv=0; assign abrt=0;
    reg [5:0] vs, de;
    wire [5:0] gate_valid,gate_sof;
    integer starts[0:5]; integer i;
    generate for(genvar g=0;g<6;g=g+1) begin: gates
        wire [15:0] pixel=16'h1000+g;
        ov5640_ddr_w_en #(.DATA_WIDTH(16)) gate(
            .axi_clk(clk),.axi_rst(rst),.capture_stop(1'b0),
            .axi_cam_en(!hold[g]),.frame_pending(2'b0),.engine_busy(1'b0),
            .s_data(pixel),.s_data_valid(de[g]),.s_hsync(1'b0),.s_vsync(vs[g]),
            .m_data(),.m_data_valid(gate_valid[g]),.m_hsync(),.m_vsync(gate_sof[g]));
        always @(posedge clk) if(gate_sof[g]) starts[g]=starts[g]+1;
    end endgenerate
    delivery_regs dut(
        .clk(clk),.rst(rst),.s_awaddr(awaddr),.s_wdata(wdata),.s_araddr(araddr),
        .s_wstrb(wstrb),.s_awvalid(awvalid),.s_wvalid(wvalid),.s_bready(bready),
        .s_arvalid(arvalid),.s_rready(rready),.s_awready(awready),.s_wready(wready),
        .s_arready(arready),.s_bvalid(bvalid),.s_rvalid(rvalid),.s_bresp(bresp),
        .s_rresp(rresp),.s_rdata(rdata),.capture_hold(hold),
        .camera_prev_base(prev),.camera_bank0(bank0),.camera_bank1(bank1),
        .camera_sequence(seqno),.camera_published(published),
        .camera_writer_idle(writer_idle),.camera_pending(pending),.camera_flush(flush),
        .camera_dma_idle(dma_idle),.camera_cmd_valid(cmdv),.camera_awvalid(awv),
        .camera_wvalid(wv),.camera_abort(abrt),.cmd_valid(),.cmd_ready(1'b1),
        .cmd_src(),.cmd_dst(),.selected_mode(),.core_busy(1'b0),.core_done(1'b0),
        .core_error(1'b0),.core_config_error(1'b0));

    task write(input [31:0] off,input [31:0] value,output [1:0] response);
        begin
            $display("WRITE %h=%h t=%0t",off,value,$time);
            @(negedge clk); awaddr=32'h40020000+off; wdata=value; awvalid=1; wvalid=0;
            do @(posedge clk); while(!awready);
            @(negedge clk); awvalid=0; wvalid=1;
            do @(posedge clk); while(!wready);
            @(negedge clk); wvalid=0; wait(bvalid); response=bresp;
            bready=1; @(posedge clk); @(negedge clk); bready=0;
        end
    endtask
    task read(input [31:0] off,output [31:0] value);
        begin
            $display("READ %h t=%0t",off,$time);
            @(negedge clk); araddr=32'h40020000+off; arvalid=1;
            do @(posedge clk); while(!arready);
            @(negedge clk); arvalid=0; wait(rvalid); value=rdata;
            rready=1; @(posedge clk); @(negedge clk); rready=0;
        end
    endtask
    task boundary;
        begin
            @(negedge clk); vs=6'h3f; repeat(4) @(negedge clk);
            vs=0; repeat(4) @(negedge clk);
        end
    endtask
    reg [1:0] response; reg [31:0] value; integer old5;
    initial begin
        awaddr=0;wdata=0;araddr=0;arvalid=0;awvalid=0;wvalid=0;vs=0;de=6'h3f;
        prev=0;bank0=0;bank1=0;seqno=0;published=0;
        for(i=0;i<6;i=i+1) begin
            bank0[i*32 +: 32]=32'h00800000+i*32'h00400000;
            bank1[i*32 +: 32]=32'h00a00000+i*32'h00400000;
            prev[i*32 +: 32]=bank0[i*32 +: 32]; published[i*2 +: 2]=2'b01;
            starts[i]=0;
        end
        repeat(4) @(negedge clk); rst=0;
        boundary();
        for(i=0;i<6;i=i+1) if(starts[i]!=1) $fatal(1,"FAIL initial writer %0d",i);
        // C1 hold begins near SOF while C5 continues publishing/admitting.
        write(32'hc0,0,response); if(response!=0) $fatal(1,"FAIL C1 select");
        dma_idle[0]=0; old5=starts[4]; write(32'h20,1,response);
        boundary(); if(starts[0]!=1 || starts[4]<=old5) $fatal(1,"FAIL selective hold");
        dma_idle[0]=1; repeat(40) @(negedge clk); read(32'h10,value);
        if(!value[1]) $fatal(1,"FAIL C1 freeze after B retirement");
        write(32'hc0,5,response); if(response!=2) $fatal(1,"FAIL selector changed while held");
        write(32'h20,0,response); if(response!=0) $fatal(1,"FAIL C1 release");
        // C3 has no published bank: acquisition is held pending and cannot start.
        write(32'hc0,2,response); published[5:4]=0; write(32'h20,1,response);
        repeat(40) @(negedge clk); read(32'h120,value);
        if(!value[1]) $fatal(1,"FAIL no-frame pending status");
        // Once publication arrives, the same lease freezes and exposes exact banks.
        published[5:4]=2'b01; repeat(40) @(negedge clk); read(32'h10,value);
        if(!value[1]) $fatal(1,"FAIL C3 did not freeze after publication");
        write(32'hb0,1,response); if(response!=2) $fatal(1,"FAIL mode guard while held");
        write(32'h20,0,response);
        // Check independent output bank addressing for all six cameras.
        for(i=0;i<6;i=i+1) begin
            write(32'hc0,i,response); write(32'hd0,1,response); write(32'hb0,1,response);
            read(32'h40,value);
            if(value != (32'h0a200000 + (i==4 ? 0 : (i<4 ? i+1 : 5))*32'h00080000 + 32'h00040000))
                $fatal(1,"FAIL thumbnail bank address C%0d: %h",i+1,value);
        end
        $display("PASS six-camera ownership: selective admission, delayed B, pending frame, guards, destinations");
        $finish;
    end
    initial begin #200000; $display("TIMEOUT state b=%b r=%b hold=%b",bvalid,rvalid,hold); $fatal(1,"FAIL six-camera timeout"); end
endmodule
