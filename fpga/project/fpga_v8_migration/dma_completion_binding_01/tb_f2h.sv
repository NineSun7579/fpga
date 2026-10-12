`timescale 1ns/1ps
module tb_f2h;
    reg pclk=0, aclk=0;
    always #4 pclk=~pclk;
    always #5 aclk=~aclk;
    reg rst=1;
    wire [3:0] arid,arlen,rid_out;
    wire [31:0] araddr;
    wire arvalid,rready;
    reg arready=0, rvalid=0, rlast=0;
    reg [3:0] rid=0;
    reg [1:0] rresp=0;
    reg [127:0] rdata=0;
`ifdef CANDIDATE
    fpga_v8_pcie_fifo_h2f_rfg01_dcb01_candidate dut (
`else
    fpga_v8_pcie_fifo_h2f_rfg01_dcb01_original dut (
`endif
        .i_admit(1'b1),.i_admit_axi(1'b1),.button_rst_n(!rst),.perst_n(!rst),
        .ref_clk_n(!pclk),.ref_clk_p(pclk),.rxn(2'b0),.rxp(2'b0),
        .axi_clk(aclk),.axi_rst(rst),.i_msi_req(4'b0),
        .axi_awready(1'b0),.axi_wready(1'b0),.axi_bid(4'b0),.axi_bresp(2'b0),.axi_bvalid(1'b0),
        .axi_arid(arid),.axi_araddr(araddr),.axi_arlen(arlen),
        .axi_arvalid(arvalid),.axi_arready(arready),
        .axi_rid(rid),.axi_rresp(rresp),.axi_rlast(rlast),.axi_rvalid(rvalid),
        .axi_rready(rready),.axi_rdata(rdata)
    );
    integer mode=0, requested=0, beats=0, accepted=0, msi_count=0;
    integer burstleft=0, response_index=0, cycles=0, stall_count=0;
    integer headers=0, expected_payload=0, payload=0, bytes=0;
    integer total_bytes=16;
    integer last_accept_cycle=-1, msi_cycle=-1;
    reg pending=0, in_packet=0, early=0;
    reg [127:0] stalled_data;
    reg stalled_last, was_stalled=0;
    function [127:0] value(input integer index);
        integer j;
        for(j=0;j<16;j=j+1) value[j*8+:8]=((index*16+j)*37+11)&255;
    endfunction
    function [127:0] endian(input [127:0] v);
        integer j;
        for(j=0;j<4;j=j+1) endian[j*32+:32]={v[j*32+:8],v[j*32+8+:8],v[j*32+16+:8],v[j*32+24+:8]};
    endfunction
    always @(negedge aclk) begin
        arready= !rst && cycles%7!=0;
        if (rst) begin rvalid=0;pending=0;end
        else if (!rvalid || rready) begin
            rvalid=pending && cycles%5!=0;
            rlast=(burstleft==1);rid=0;rresp=0;rdata=value(response_index);
            if(mode==2 && response_index==0) rresp=2'b10;
            if(mode==3 && response_index==0) rresp=2'b11;
            if(mode==4 && response_index==0) rid=1;
            if(mode==5 && response_index==0) rlast=1;
            if(mode==6 && burstleft==1) rlast=0;
        end
    end
    always @(posedge aclk) begin
        if(!rst) begin
            if(arvalid && arready) begin
                if(pending) $fatal(1,"reader overlapped bursts");
                pending=1;burstleft=arlen+1;requested=requested+arlen+1;
            end
            if(rvalid && rready) begin
                beats=beats+1;response_index=response_index+1;
                burstleft=burstleft-1;
                if(burstleft==0) pending=0;
            end
        end
    end
    always @(negedge pclk) begin
        // Hold FIRST header long enough that all 16B have been prefetched.
        // This is the actual old MSI counterexample, not a fabricated busy flag.
        if(mode==1 && dut.pango_pcie_top.valid && headers==0 && stall_count<40) begin
            dut.pango_pcie_top.ready=0;stall_count=stall_count+1;
        end else dut.pango_pcie_top.ready=(cycles%11<7);
    end
    always @(posedge pclk) begin
        cycles=cycles+1;
        if(!rst) begin
            if(was_stalled && (!dut.pango_pcie_top.valid ||
               dut.pango_pcie_top.data!==stalled_data || dut.pango_pcie_top.last!==stalled_last))
                $fatal(1,"packetizer changed held AXIS payload");
            was_stalled=dut.pango_pcie_top.valid && !dut.pango_pcie_top.ready;
            stalled_data=dut.pango_pcie_top.data;stalled_last=dut.pango_pcie_top.last;
            if(dut.pango_pcie_top.valid && dut.pango_pcie_top.ready) begin
                accepted=accepted+1;
                if(!in_packet) begin
                    headers=headers+1;in_packet=1;
                    if(dut.pango_pcie_top.data[22:20]!=0 ||
                       dut.pango_pcie_top.data[18] || dut.pango_pcie_top.data[13:12]!=0)
                        $fatal(1,"MWr TC/Attr not zero");
                    expected_payload=(dut.pango_pcie_top.data[9:0]+3)/4;
                end else begin
                    if(dut.pango_pcie_top.data!==endian(value(payload)))
                        $fatal(1,"payload mismatch index=%0d got=%h expected=%h",payload,
                            dut.pango_pcie_top.data,endian(value(payload)));
                    payload=payload+1;bytes=bytes+16;expected_payload=expected_payload-1;
                    if(dut.pango_pcie_top.last) begin
                        if(expected_payload!=0) $fatal(1,"TLP length not retired");
                        in_packet=0;last_accept_cycle=cycles;
                    end
                end
            end
            if(dut.pango_pcie_top.msi) begin
                msi_count=msi_count+1;msi_cycle=cycles;
                if(bytes!=total_bytes || in_packet) early=1;
            end
        end
    end
    initial begin
        if(!$value$plusargs("MODE=%d",mode)) mode=0;
        if(mode==5 || mode==6) total_bytes=256;
        if(mode==7) total_bytes=8192;
        if(mode==8) total_bytes=614400;
        if(mode==9) total_bytes=1228800;
        repeat(8) @(negedge pclk);rst=0;
        repeat(12) @(negedge pclk);
        dut.pango_pcie_top.f2h(32'h01800000,total_bytes,32'h01000000);
        repeat(total_bytes/2+2000) @(negedge pclk);
`ifdef CANDIDATE
        if(mode>=2 && mode<=6) begin
            if(msi_count || !dut.f2h_fault) $fatal(1,"bad AXI response must fail-stop without MSI");
        end else begin
            if(msi_count!=1 || bytes!=total_bytes || early || requested!=total_bytes/16 ||
               beats!=total_bytes/16 || msi_cycle<=last_accept_cycle)
                $fatal(1,"candidate incomplete/early: MSI=%0d bytes=%0d requested=%0d beats=%0d early=%0d",
                    msi_count,bytes,requested,beats,early);
        end
`else
        if(mode==1 && !early) $fatal(1,"did not reproduce early MSI under header stall");
        if(mode==2 || mode==3) begin
            if(msi_count!=1) $fatal(1,"did not reproduce ignored RRESP");
        end
`endif
        $display("F2H_PATH_PASS mode=%0d bytes=%0d axi=%0d MSI=%0d early=%0d last=%0d msi=%0d",
            mode,bytes,beats,msi_count,early,last_accept_cycle,msi_cycle);
        $finish;
    end
endmodule
