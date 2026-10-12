`timescale 1ns/1ps
module tb_capture_fault;
    reg clk=0,pc=0,fc=0;
    always #7 clk=~clk;always #8 pc=~pc;always #20 fc=~fc;
    reg button=0,perst=0,ddr=0,arst=1,prst=1,link=0,local_control_reset=0;
    wire admit,ap,fault,fa,fp;
    wire cfgv,cfgr,cfga,cfge,epoch,armed,ok,pfault,block;
    wire [31:0] gen;
    wire [1:0] b0,b1;
    reg sof=0,publish=0;
    wire hv,hr,hrv,hrr,hra,hre;
    wire [31:0] hs,hl,hseq,hgen,rseq,rgen,published,failed,rejected;
    wire [2:0] hcam,rcam;wire hbank,rbank;wire [63:0] htoken,rtoken;
    fpga_v8_reset_fault_guard #(.ALIVE_LIMIT(32),.QUALIFY_CYCLES(8)) supervisor(
        .free_clk(fc),.button_rst_n(button),.perst_n(perst),.axi_clk(clk),
        .axi_rst(arst),.ddr_init_done(ddr),.startup_idle_axi(!armed && b0==0 && b1==0),
        .pcie_clk(pc),.pcie_rst(prst),.smlh_link_up(link),.rdlh_link_up(link),.startup_idle_pcie(1'b1),
        .fault(fault),.admit_axi(admit),.admit_pcie(ap),.fault_axi(fa),.fault_pcie(fp));
    fpga_v8_capture_lease manager(
        .clk(clk),.rst(arst),.config_valid(cfgv && admit),.config_ready(cfgr),
        .config_generation(gen),.config_accept(cfga),.config_reject(cfge),
        .epoch_start(epoch),.armed(armed),.config_ok(ok),.protocol_fault(pfault),
        .engine_idle(1'b1),.capture_bank(1'b0),.admitted_sof(sof && !block && admit),
        .publish(publish),.publish_seq(32'd1),.retired_error(1'b0),.lease_block(block),
        .bank0_state(b0),.bank1_state(b1),.input_ready(1'b0),
        .release_valid(1'b0),.release_camera(3'd4),.release_bank(1'b0),
        .release_seq(32'd0),.release_generation(32'd0),.release_token(64'd0),
        .host_valid(hv),.host_ready(hr),.host_src_addr(hs),.host_length(hl),
        .host_seq(hseq),.host_generation(hgen),.host_camera(hcam),.host_bank(hbank),.host_token(htoken),
        .host_release_valid(hrv),.host_release_ready(hrr),.host_release_camera(rcam),
        .host_release_bank(rbank),.host_release_seq(rseq),.host_release_generation(rgen),
        .host_release_token(rtoken),.host_release_accept(hra),.host_release_reject(hre),
        .published_count(published),.failed_count(failed),.rejected_release_count(rejected));
    reg [31:0] aw=0,wd=0,ar=0;
    reg av=0,wv=0,rv=0,br=1;
    wire awr,wr,bv,arr,rr;wire [1:0] bp,rp;wire [31:0] rd;
    fpga_v8_capture_control_axil_arm_v2 endpoint(
        .clk(clk),.rst_n(!arst && !local_control_reset),
        .config_valid(cfgv),.config_ready(cfgr && admit),.config_generation(gen),
        .config_accept(cfga),.config_reject(cfge),.epoch_start(epoch),.armed(armed),
        .config_ok(ok),.protocol_fault(pfault | fa),.bank0_state(b0),.bank1_state(b1),
        .host_valid(hv),.host_ready(hr),.host_src_addr(hs),.host_length(hl),
        .host_seq(hseq),.host_generation(hgen),.host_camera(hcam),.host_bank(hbank),.host_token(htoken),
        .host_release_valid(hrv),.host_release_ready(hrr),.host_release_camera(rcam),
        .host_release_bank(rbank),.host_release_seq(rseq),.host_release_generation(rgen),
        .host_release_token(rtoken),.host_release_accept(hra),.host_release_reject(hre),
        .published_count(published),.failed_count(failed),.rejected_release_count(rejected),
        .s_axil_awaddr(aw),.s_axil_awprot(3'b0),.s_axil_awvalid(av),.s_axil_awready(awr),
        .s_axil_wdata(wd),.s_axil_wstrb(4'hf),.s_axil_wvalid(wv),.s_axil_wready(wr),
        .s_axil_bresp(bp),.s_axil_bvalid(bv),.s_axil_bready(br),
        .s_axil_araddr(ar),.s_axil_arprot(3'b0),.s_axil_arvalid(rv),.s_axil_arready(arr),
        .s_axil_rdata(rd),.s_axil_rresp(rp),.s_axil_rvalid(rr),.s_axil_rready(1'b1));
    task write_word(input [31:0] address,value,input [1:0] expected);
        begin
            @(negedge clk);aw=address;wd=value;av=1;wv=1;
            @(posedge clk);if(!awr || !wr)$fatal(1,"write fixture not ready");
            @(negedge clk);av=0;wv=0;
            wait(bv);if(bp!=expected)$fatal(1,"BRESP address=%h got=%d expected=%d",address,bp,expected);
            @(negedge clk);@(negedge clk);
        end
    endtask
    task read_word(input [31:0] address,output [31:0] value);
        begin
            @(negedge clk);ar=address;rv=1;@(negedge clk);rv=0;
            wait(rr);value=rd;@(negedge clk);
        end
    endtask
    integer mode;reg [31:0] status,accepted;
    initial begin
        if(!$value$plusargs("MODE=%d",mode))mode=0;
        #100;button=1;perst=1;ddr=1;arst=0;prst=0;link=1;#3000;
        if(!admit || armed)$fatal(1,"startup must be qualified and disarmed");
        write_word('h10c,32'h12345678,0); // staged generation alone cannot ARM
        if(armed || fault)$fatal(1,"staging armed/faulted");
        if(mode==0)begin
            ddr=0;arst=1;#100;ddr=1;arst=0;#300;
            write_word('h10c,32'h87654321,0);
            write_word('h110,1,2);
            if(armed || admit || !fault)$fatal(1,"DDR loss allowed new ARM");
        end else begin
            br=0;write_word('h110,1,0); // keep accepted ARM B pending
            if(!armed || fault || !bv)$fatal(1,"normal ARM/epoch or pending B fixture");
            #200;if(fault)$fatal(1,"legitimate epoch_start faulted");
            if(mode==1)begin
                link=0;#100;link=1;#200;
                if(!bv || bp!=0 || !fault)$fatal(1,"accepted control B abandoned");
                br=1;#100;
            end else begin
                br=1;#100;
                @(negedge clk);sof=1;@(negedge clk);sof=0;
                @(negedge clk);publish=1;@(negedge clk);publish=0;#100;
                write_word('h114,0,0); // host claim bank0
                if(b0!=2)$fatal(1,"HELD fixture missing");
                if(mode==2)begin
                    link=0;#100;link=1;#200;
                    write_word('h10c,32'habcdef01,0);write_word('h110,1,2);
                    if(b0!=2 || admit || !fault)$fatal(1,"HELD ownership or ARM isolation");
                end else begin
                    // Deliberately unsupported hypothetical control-only reset.
                    // No such independent reset net exists in exact v2 binding.
                    local_control_reset=1;#100;local_control_reset=0;#100;
                    read_word('h104,status);
                    if(fault || (status&8) || b0!=2)$fatal(1,"control-only reset observation");
                    $display("CAPTURE_UNSUPPORTED_CONTROL_ONLY_RESET HELD_REMAINS_BOUND_LOST");
                    $finish;
                end
            end
        end
        read_word('h104,status);read_word('h174,accepted);
        if(!(status&4))$fatal(1,"RAW STATUS bit2 missing sticky fault");
        $display("CAPTURE_PASS mode=%0d status=%h accepted=%0d",mode,status,accepted);$finish;
    end
    initial begin #40000;$fatal(1,"capture watchdog");end
endmodule
