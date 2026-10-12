`timescale 1ns/1ps
// Simulation-only external PCIe shell. The real frozen DMA controller stays
// inside this shell. No PCIe hard-IP, TLP CRC/link or posted-write proof here.
module fpga_v8_pango_pcie_top_h2f_rfg01 #(
    parameter ADDR_WIDTH=12, MSI_NUM=5
) (
    input i_admit, input button_rst_n, perst_n, ref_clk_n, ref_clk_p,
    input [1:0] rxn,rxp, output [1:0] txn,txp,
    output ref_led,pclk_led,smlh_link_up,rdlh_link_up,
    input [MSI_NUM-2:0] i_msi_req, output [MSI_NUM-2:0] o_msi_grant,
    output [31:0] fpga_ddr3_addr,fpga_ddr3_length,fpga_ddr3_total_length,
    input fpga_tx_done, output mwr_tx_busy, input fpga_data_ready,
    output fpga_tx_clk_en, output [ADDR_WIDTH-1:0] fpga_tx_addr,
    input [127:0] fpga_tx_data,
    input fpga_rx_done, output reg mrd_rx_busy=0,
    input fpga_rx_clk_en, input [ADDR_WIDTH-1:0] fpga_rx_addr,
    output reg [127:0] fpga_rx_data=0,
    output fifo_pcie_clk,fifo_pcie_rst
);
    assign fifo_pcie_clk=ref_clk_p;
    assign fifo_pcie_rst=!(button_rst_n && perst_n);
    assign {txn,txp}=0;
    assign {ref_led,pclk_led,smlh_link_up,rdlh_link_up}=4'hf;
    assign o_msi_grant=0;
    reg public_tx_busy=0; assign mwr_tx_busy=public_tx_busy;
    assign fpga_tx_clk_en=0;
    assign fpga_tx_addr=0;
    reg bar_en=0;
    reg [ADDR_WIDTH-1:0] bar_addr=0;
    reg [127:0] bar_data=0;
    wire req32,req64,txreq32,txreq64,msi;
    reg ack32=0,ack64=0;
    wire [9:0] req_length;
    wire [63:0] req_addr;
    wire boundary_error;
    fpga_v8_pcie_dma_controller_h2f_rfg01 #(.ADDR_WIDTH(ADDR_WIDTH)) controller (
        .i_admit(i_admit),.clk(fifo_pcie_clk),.rst_n(!fifo_pcie_rst),
        // Exact frozen ips2l_pcie_dma.v controller wiring.
        .i_mwr_tx_busy(~fpga_tx_done),.i_mrd_rx_busy(~fpga_rx_done),
        .o_fpga_msi(msi),.i_bar1_wr_en(bar_en),.i_bar1_wr_addr(bar_addr),
        .i_bar1_wr_data(bar_data),.i_bar1_wr_byte_en(16'hffff),
        .i_apb_psel(1'b0),.i_apb_paddr(10'b0),.i_apb_pwdata(32'b0),
        .i_apb_pstrb(4'b0),.i_apb_pwrite(1'b0),.i_apb_penable(1'b0),
        .o_mwr32_req(txreq32),.i_mwr32_req_ack(1'b0),
        .o_mwr64_req(txreq64),.i_mwr64_req_ack(1'b0),
        .o_mrd32_req(req32),.i_mrd32_req_ack(ack32),
        .o_mrd64_req(req64),.i_mrd64_req_ack(ack64),
        .o_req_length(req_length),.o_req_addr(req_addr),
        .i_dma_check_result(64'b0),.o_cross_4kb_boundary(boundary_error),
        .o_ddr3_addr(fpga_ddr3_addr),.o_ddr3_length(fpga_ddr3_length),
        .o_ddr3_total_length(fpga_ddr3_total_length)
    );
    integer fetch_count=0,wait_count=0,fetch_bytes=0;
    reg fetching=0,wait_clear=0;
    reg [31:0] fetch_offset=0,host_base=32'h01000000,host_word=0;
    reg control_payload=1;
    // One synchronous RAM read cycle, as used by frozen fpga_rx_clk_en_d.
    function [127:0] host_beat(input [31:0] offset,input integer available);
        integer j; reg [127:0] v;
        begin
            v=0;
            for(j=0;j<16;j=j+1)
                if(j<available) v[j*8+:8]=((offset+j)*37+11)&255;
            if(control_payload && offset==0) v[31:0]=host_word;
            host_beat=v;
        end
    endfunction
    always @(posedge fifo_pcie_clk or posedge fifo_pcie_rst) begin
        if(fifo_pcie_rst) begin
            mrd_rx_busy<=0;ack32<=0;ack64<=0;fetching<=0;
            wait_count<=0;fetch_count<=0;wait_clear<=0;fpga_rx_data<=0;
        end else begin
            ack32<=0;ack64<=0;
            if(wait_clear && !(req32 || req64)) wait_clear<=0;
            if(!fetching && !wait_clear && (req32 || req64)) begin
                ack32<=req32;ack64<=req64;mrd_rx_busy<=1;
                fetching<=1;wait_clear<=1;wait_count<=4;
                fetch_count<=fetch_count+1;
                fetch_offset<=req_addr[31:0]-host_base;
                // PCIe Length field 0 means 1024 DWORDs.
                fetch_bytes<=req_length==0 ? 4096 : req_length*4;
            end else if(fetching) begin
                if(wait_count==0) begin mrd_rx_busy<=0;fetching<=0;end
                else wait_count<=wait_count-1;
            end
            if(fpga_rx_clk_en)
                fpga_rx_data<=host_beat(fetch_offset+fpga_rx_addr*16,
                                      fetch_bytes-fpga_rx_addr*16);
        end
    end
    task bar_write(input [11:0] addr,input [31:0] value);
        begin
            @(negedge fifo_pcie_clk);bar_en=1;bar_addr=addr;bar_data={96'b0,value};
            @(negedge fifo_pcie_clk);bar_en=0;
            repeat(4) @(negedge fifo_pcie_clk);
        end
    endtask
    task h2f(input [31:0] target,bytes,word,hostaddr,input bit ctl);
        integer dwords;
        begin
            host_base=hostaddr;host_word=word;control_payload=ctl;
            bar_write(12'h1e0,target);
            bar_write(12'h110,hostaddr);
            bar_write(12'h120,32'b0);
            bar_write(12'h200,bytes);
            dwords=(bytes>=4096) ? 1024 : (bytes+3)/4;
            bar_write(12'h100,32'h00010000 | (dwords&1023));
        end
    endtask

    // Models only a public shell busy level, never a hard-IP retirement receipt.
    task f2h_public(input [31:0] target);
        begin
            bar_write(12'h1e0,target);
            bar_write(12'h110,32'h01000000);
            bar_write(12'h120,0);
            bar_write(12'h200,16);
            bar_write(12'h100,32'h01010004);
            if(!(txreq32 || txreq64)) $fatal(1,"F2H STATUS request was incorrectly gated");
            public_tx_busy=1;
        end
    endtask
endmodule
