`timescale 1ns/1ps
module tb_fpga_v8_h2f_f2h_parity;
    reg clk=0;always #8 clk=!clk;
    reg rst_n=0,bar_en=0;
    reg [11:0] bar_addr=0;reg [127:0] bar_data=0;
    reg txbusy=1,ack=0;
    wire a32,a64,b32,b64,am, bm, ax,bx;
    wire [9:0] al,bl;
    wire [63:0] aa,ba;
    wire [31:0] ad,bd,an,bn,atotal,btotal;
    ips2l_pcie_dma_controller #(.ADDR_WIDTH(12)) original (
        .clk(clk),.rst_n(rst_n),.i_mwr_tx_busy(txbusy),.i_mrd_rx_busy(1'b1),.o_fpga_msi(am),
        .i_bar1_wr_en(bar_en),.i_bar1_wr_addr(bar_addr),.i_bar1_wr_data(bar_data),.i_bar1_wr_byte_en(16'hffff),
        .i_apb_psel(1'b0),.i_apb_paddr(10'b0),.i_apb_pwdata(32'b0),.i_apb_pstrb(4'b0),
        .i_apb_pwrite(1'b0),.i_apb_penable(1'b0),
        .o_mwr32_req(a32),.i_mwr32_req_ack(ack),.o_mwr64_req(a64),.i_mwr64_req_ack(ack),
        .i_mrd32_req_ack(1'b0),.i_mrd64_req_ack(1'b0),.o_req_length(al),.o_req_addr(aa),
        .i_dma_check_result(64'b0),.o_cross_4kb_boundary(ax),.o_ddr3_addr(ad),
        .o_ddr3_length(an),.o_ddr3_total_length(atotal)
    );
    fpga_v8_pcie_dma_controller_h2f #(.ADDR_WIDTH(12)) candidate (
        .clk(clk),.rst_n(rst_n),.i_mwr_tx_busy(txbusy),.i_mrd_rx_busy(1'b1),.o_fpga_msi(bm),
        .i_bar1_wr_en(bar_en),.i_bar1_wr_addr(bar_addr),.i_bar1_wr_data(bar_data),.i_bar1_wr_byte_en(16'hffff),
        .i_apb_psel(1'b0),.i_apb_paddr(10'b0),.i_apb_pwdata(32'b0),.i_apb_pstrb(4'b0),
        .i_apb_pwrite(1'b0),.i_apb_penable(1'b0),
        .o_mwr32_req(b32),.i_mwr32_req_ack(ack),.o_mwr64_req(b64),.i_mwr64_req_ack(ack),
        .i_mrd32_req_ack(1'b0),.i_mrd64_req_ack(1'b0),.o_req_length(bl),.o_req_addr(ba),
        .i_dma_check_result(64'b0),.o_cross_4kb_boundary(bx),.o_ddr3_addr(bd),
        .o_ddr3_length(bn),.o_ddr3_total_length(btotal)
    );
    integer cycle=0,transfers=0,chunks=0,msis=0,delay=0;
    reg awaiting=0,compare_active=0;
    always @(negedge clk) begin
        cycle=cycle+1;
        if(cycle>10000) $fatal(1,"F2H parity watchdog");
        // Direction is undefined while the host is programming TOTAL_LENGTH
        // before CMD. Compare continuously from the first valid F2H command,
        // including the cycles before its registered request is asserted.
        if(!rst_n) compare_active=0;
        else if(original.dma_wr_rd_cmd_flag && original.cmd_reg_cfg_done) compare_active=1;
        if(rst_n && compare_active && {a32,a64,am,al,aa,ax,ad,an,atotal} !== {b32,b64,bm,bl,ba,bx,bd,bn,btotal})
            $fatal(1,"F2H differs cycle=%0d req=%b/%b len=%0d/%0d addr=%h/%h ddr=%h/%h bytes=%0d/%0d dir=%b cmd=%b total_cfg=%b chunk=%d",
                cycle,{a32,a64},{b32,b64},al,bl,aa,ba,ad,bd,an,bn,
                original.dma_wr_rd_cmd_flag,original.cmd_reg_cfg_done,original.total_length_cfg_done,original.chunk_count);
        ack=0;
        if(rst_n) begin
            if((a32 || a64) && !awaiting) begin
                ack=1;txbusy=1;awaiting=1;delay=7;chunks=chunks+1;
            end else if(awaiting) begin
                delay=delay-1;
                if(delay==0) begin txbusy=0;awaiting=0;end
            end
            if(am) msis=msis+1;
        end
    end
    task bar(input [11:0] addr,input [31:0] value);
        begin
            @(posedge clk);#1;bar_en=1;bar_addr=addr;bar_data={96'b0,value};
            @(posedge clk);#1;bar_en=0;
            repeat(4) @(posedge clk);
        end
    endtask
    task transfer(input integer bytes,input [31:0] host);
        integer old_m;
        begin
            @(posedge clk);#1;rst_n=0;txbusy=1;awaiting=0;ack=0;
            repeat(4) @(posedge clk);#1;rst_n=1;
            bar(12'h1e0,32'h08000000);bar(12'h110,host);bar(12'h120,0);bar(12'h200,bytes);
            old_m=msis;
            bar(12'h100,32'h01010000|(((bytes>=4096)?1024:(bytes+3)/4)&1023));
            wait(msis>old_m);repeat(6) @(posedge clk);transfers=transfers+1;
        end
    endtask
    initial begin
        transfer(16,32'h01000000);
        transfer(4100,32'h01000000);
        transfer(8192,32'h01000004);
        transfer(1228800,32'h01000000);
        $display("F2H_CONTROLLER_PARITY_PASS transfers=%0d chunks=%0d",transfers,chunks);
        $finish;
    end
endmodule
