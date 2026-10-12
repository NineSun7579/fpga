`timescale 1ns/1ps
module tb_mapping_leaf;
    reg clk=0; always #5 clk=!clk;
    reg rst_n=0;
    reg [6:0] awid=0,arid=0;
    reg [31:0] awaddr=0,araddr=0;
    reg [7:0] awlen=0,arlen=0;
    reg [2:0] awsize=4,arsize=4,awprot=0,arprot=0;
    reg [1:0] awburst=1,arburst=1;
    reg awvalid=0,wvalid=0,arvalid=0,bready=0,rready=0,wlast=0;
    reg [127:0] wdata=0;
    reg [15:0] wstrb=16'hffff;
    wire awready,wready,bvalid,arready,rvalid,rlast;
    wire [6:0] bid,rid;
    wire [1:0] bresp,rresp;
    wire [127:0] rdata;
    wire [31:0] ma,md,ra;
    wire [2:0] mp,rp;
    wire [3:0] ms;
    wire mav,mwv,mbr,mrv,mrr;
    integer cycle=0,op=0,trace,stim,rc;
    wire mar=rst_n && cycle%5!=1;
    wire mwr=rst_n && cycle%7!=2;
    wire mrar=rst_n && cycle%3!=1;
    reg mbv=0,mrrv=0,seen_aw=0,seen_w=0;
    reg [31:0] mrd=0;
    integer expected_ok=0,local_aw=0,local_w=0,local_ar=0;
    integer total_aw=0,total_w=0,total_ar=0,total_b=0,total_r=0;
    reg [31:0] address;
    integer length,size_n,burst_n,id_n,mode_n,order_n,hold_n;

    fpga_v8_coop_axi128_endpoint dut (
        .clk(clk),.rst_n(rst_n),
        .s_axi_awid(awid),.s_axi_awaddr(awaddr),.s_axi_awlen(awlen),
        .s_axi_awsize(awsize),.s_axi_awburst(awburst),.s_axi_awlock(1'b0),
        .s_axi_awcache(4'hf),.s_axi_awprot(awprot),.s_axi_awqos(4'hb),.s_axi_awregion(4'h5),
        .s_axi_awvalid(awvalid),.s_axi_awready(awready),
        .s_axi_wdata(wdata),.s_axi_wstrb(wstrb),.s_axi_wlast(wlast),
        .s_axi_wvalid(wvalid),.s_axi_wready(wready),
        .s_axi_bid(bid),.s_axi_bresp(bresp),.s_axi_bvalid(bvalid),.s_axi_bready(bready),
        .s_axi_arid(arid),.s_axi_araddr(araddr),.s_axi_arlen(arlen),
        .s_axi_arsize(arsize),.s_axi_arburst(arburst),.s_axi_arlock(1'b0),
        .s_axi_arcache(4'hf),.s_axi_arprot(arprot),.s_axi_arqos(4'hc),.s_axi_arregion(4'h6),
        .s_axi_arvalid(arvalid),.s_axi_arready(arready),
        .s_axi_rid(rid),.s_axi_rdata(rdata),.s_axi_rresp(rresp),
        .s_axi_rlast(rlast),.s_axi_rvalid(rvalid),.s_axi_rready(rready),
        .m_axil_awaddr(ma),.m_axil_awprot(mp),.m_axil_awvalid(mav),.m_axil_awready(mar),
        .m_axil_wdata(md),.m_axil_wstrb(ms),.m_axil_wvalid(mwv),.m_axil_wready(mwr),
        .m_axil_bresp(2'b00),.m_axil_bvalid(mbv),.m_axil_bready(mbr),
        .m_axil_araddr(ra),.m_axil_arprot(rp),.m_axil_arvalid(mrv),.m_axil_arready(mrar),
        .m_axil_rdata(mrd),.m_axil_rresp(2'b00),.m_axil_rvalid(mrrv),.m_axil_rready(mrr)
    );
    function [31:0] reply(input [31:0] a);
        reply=32'h6a19c4e7 ^ a;
    endfunction
    always @(negedge clk) cycle=cycle+1;
    always @(posedge clk) begin
        if(cycle>2000000) $fatal(1,"watchdog op=%0d addr=%h",op,address);
        if(!rst_n) begin mbv<=0;mrrv<=0;seen_aw<=0;seen_w<=0; end
        else begin
            if(mav && mar) begin
                local_aw=local_aw+1;total_aw=total_aw+1;seen_aw<=1;
                if(!expected_ok || ma!==((address-32'h40010000)>>2) || mp!==(id_n&7))
                    $fatal(1,"local AW mismatch op=%0d addr=%h local=%h eligible=%0d",op,address,ma,expected_ok);
            end
            if(mwv && mwr) begin
                local_w=local_w+1;total_w=total_w+1;seen_w<=1;
                if(!expected_ok || md!==32'h17294351 || ms!==4'hf) $fatal(1,"local W mismatch op=%0d",op);
            end
            if(seen_aw && seen_w && !mbv) begin mbv<=1;seen_aw<=0;seen_w<=0;end
            if(mbv && mbr) mbv<=0;
            if(mrv && mrar) begin
                local_ar=local_ar+1;total_ar=total_ar+1;
                if(!expected_ok || ra!==((address-32'h40010000)>>2) || rp!==(id_n&7))
                    $fatal(1,"local AR mismatch op=%0d addr=%h local=%h eligible=%0d",op,address,ra,expected_ok);
                mrd<=reply(ra);mrrv<=1;
            end
            if(mrrv && mrr) mrrv<=0;
            if(bvalid && bready) begin
                total_b=total_b+1;
                $fdisplay(trace,"%0d B %h %h",op,bid,bresp);
            end
            if(rvalid && rready) begin
                total_r=total_r+1;
                $fdisplay(trace,"%0d R %h %h %h %h",op,rid,rdata,rresp,rlast);
            end
        end
    end
    task aw_send;
        begin
            repeat(order_n==1 ? 4 : 0) @(negedge clk);
            awaddr=address;awlen=length;awsize=size_n;awburst=burst_n;awid=id_n;awprot=id_n&7;awvalid=1;
            do @(posedge clk);while(!awready);
            @(negedge clk);awvalid=0;awaddr=32'hdeadbeef;
        end
    endtask
    task w_send;
        integer i;
        begin
            repeat(order_n==2 ? 4 : 0) @(negedge clk);
            for(i=0;i<=length;i=i+1) begin
                wdata=128'habbccdde123456789abcdef017294351;
                wlast=mode_n==0 ? i==length : (mode_n==1 ? 1'b0 : i==0);wvalid=1;
                do @(posedge clk);while(!wready);
                @(negedge clk);wvalid=0;
            end
        end
    endtask
    task take_b;
        reg [8:0] saved;
        begin
            wait(bvalid);saved={bid,bresp};
            repeat(hold_n) begin @(negedge clk);if(!bvalid || {bid,bresp}!==saved) $fatal(1,"B stall");end
            if(bid!==id_n || bresp!==(expected_ok ? 2'b00 : 2'b10)) $fatal(1,"B mismatch op=%0d addr=%h resp=%h expected=%0d",op,address,bresp,expected_ok);
            bready=1;@(posedge clk);@(negedge clk);bready=0;
        end
    endtask
    task read_one;
        integer i;
        reg [137:0] saved;
        begin
            araddr=address;arlen=length;arsize=size_n;arburst=burst_n;arid=id_n;arprot=id_n&7;arvalid=1;
            do @(posedge clk);while(!arready);
            @(negedge clk);arvalid=0;araddr=32'hbad00bad;
            for(i=0;i<=length;i=i+1) begin
                wait(rvalid);saved={rid,rdata,rresp,rlast};
                repeat(hold_n) begin @(negedge clk);if(!rvalid || {rid,rdata,rresp,rlast}!==saved) $fatal(1,"R stall");end
                if(rid!==id_n || rresp!==(expected_ok ? 2'b00 : 2'b10) || rlast!==(i==length) ||
                    rdata!==(expected_ok ? {96'd0,reply((address-32'h40010000)>>2)} : 128'd0))
                    $fatal(1,"R mismatch op=%0d addr=%h resp=%h expected=%0d",op,address,rresp,expected_ok);
                rready=1;@(posedge clk);@(negedge clk);rready=0;
            end
        end
    endtask
    initial begin
        trace=$fopen("actual.trace","w");stim=$fopen("stimulus.txt","r");
        if(!trace || !stim) $fatal(1,"files");
        repeat(5) @(negedge clk);rst_n=1;repeat(3) @(negedge clk);
        while(!$feof(stim)) begin
            rc=$fscanf(stim,"%h %d %d %d %d %d %d %d %d\n",address,length,size_n,burst_n,id_n,mode_n,order_n,hold_n,expected_ok);
            if(rc!=9) $fatal(1,"stimulus");
            op=op+1;local_aw=0;local_w=0;local_ar=0;
            fork aw_send();w_send();take_b();join
            if(local_aw!=expected_ok || local_w!=expected_ok) $fatal(1,"local write count op=%0d",op);
            // Missing/early WLAST affects writes only; Python supplies read eligibility separately.
            expected_ok=(length==0 && size_n==4 && burst_n<2 && address[3:0]==0 &&
                address>=32'h40010000 && address<=32'h40010ff0);
            read_one();
            if(local_ar!=expected_ok) $fatal(1,"local read count op=%0d",op);
            $fdisplay(trace,"%0d LOCAL %0d %0d %0d",op,local_aw,local_w,local_ar);
            repeat(2) @(negedge clk);
        end
        $fclose(trace);$fclose(stim);
        $display("MAPPING_LEAF_PASS ops=%0d local_AW=%0d local_W=%0d local_AR=%0d B=%0d R=%0d cycles=%0d",op,total_aw,total_w,total_ar,total_b,total_r,cycle);
        $finish;
    end
endmodule
